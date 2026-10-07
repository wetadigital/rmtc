# RMTC — Top 5 Systemic Design Flaws

Updated August 2026: `RMTC-485/QueryParameters` (commits `7e0bb28`..`c532a55`)
rewrote `CypherConnection`/`CypherQueries` to bind values as native `$param` placeholders and
added identifier validation ahead of every remaining spliced-in string, and made two related
one-line fixes elsewhere in `system/`. All five items below have been touched by that work — most
are now resolved or substantially mitigated, one fix is incomplete, and the parameterization pass
itself introduced a few small regressions that should be caught before this lands. See each
section for current status.

Scope note: this review excludes anything already flagged in code as a TODO/HACK, anything
described in `technical_notes.md` as unimplemented/a placeholder (REST interface, C2PA
watermarking, AWS scheduler, environment/dependency management), and anything that is an
intentional "light enforcement" boundary (license/permission gating, immutability, the Factory's
`rmtc`-prefix whitelisting) — RMTC is an in-process Python library used by trusted pipeline code,
so any guardrail expressed as a Python-level check is bypassable by design and isn't a hidden flaw.
What follows are defects in code that is fully implemented, used on the primary read/write path,
and does not behave the way the architecture requires.

## 1. [Largely resolved] Cypher queries are now parameterized; a few gaps and regressions remain

**Where:** `src/python/lib/rmtc/core/track/store/cypher/connection.py`.

Every property *value* write and read now goes through a `params` dict bound as native `$name`
placeholders (e.g. `_update_properties` at lines 274-356, `_sync_properties` at lines 483-491 and
543-551, and every `CypherQueries.get_*` method). The identifiers Cypher itself cannot
parameterize — node labels (`entity.class_category`) and dynamic property names (`prop.name`) —
are now validated before being spliced into a query string: `class_category.isalnum()` checks at
lines 130-131, 247-248, 459-460 and 1087-1088, and `Property.valid_name(prop_name)` checks at
lines 293-294, 372-373, 540-541, 558-559 and 638-639. This is the correct pattern (values as
parameters, identifiers as validated strings) and closes the injection risk described in the
original version of this section.

**Remaining gap:** the four lineage-traversal queries (`get_sources`, `get_related`,
`get_descendents`, `get_derivatives`, lines 861-935) and the relation-fetch query inside
`_sync_properties` (line 648-658) filter the query's entry node `a` by `_store`, but not the
returned node `b` — this is now a store-partitioning gap (see item 5) rather than an injection
risk, since `b` is never interpolated from untrusted input.

**Regressions introduced by this pass, to fix before merging:**
- `delete_entities` (line 100) is missing `AND` between its two `WHERE` clauses:
  `e._obj_id IN $obj_ids e._store=$store` — this is a Cypher syntax error, not just a style issue.
- The relation-connect query in `_update_properties` (line 389) filters on `a.store=$store`
  (no leading underscore) instead of `a._store=$store`, so it silently matches against a
  property that doesn't exist rather than applying the intended store filter — `b` on the same
  query (line 390) does use `b._store` correctly, so only the `a`-side filter is broken.
- `CypherQueries.get_best_run` (lines 1161-1164) is missing a comma between the `solution=` and
  `store=` keyword arguments — `solution=solution.obj_id` / `store=self.connection.store.name,` —
  which is a Python `SyntaxError` and would currently prevent this module from importing at all.

## 2. [Resolved] Enum property conversion no longer discards a valid value

**Why it's systemic:** the property system is the substrate almost every Entity in RMTC is built on
(status, direction, mode, category enums, etc.). This bug means any Enum property with a default
can never be set to a non-default value via a string assignment — the assignment silently
succeeds but the value silently reverts, with no exception, warning, or log line. Bugs caused by
this are exactly the kind the docs already warn `_convert()` produces, but this is a distinct,
concrete, reproducible defect rather than the generic "conversion is fragile" caveat.
**Where:** `src/python/lib/rmtc/system/objects.py:387-399` (formerly), the `ENUM` branch of
`_convert()`.

Previously, converting a string to an Enum computed the correct `index` and then unconditionally
returned `self.default` if one was set, discarding the just-computed value. The current code
returns immediately after the string-conversion branch (`return self._type_class(index)`),
matching the pattern already used by the `VERSION`/`URI`/`PACKAGE`/`TYPE` branches. This closes the
defect: an Enum property with a default can now actually be set to a non-default value via a
string assignment.

## 3. [Resolved] Write-write conflicts now raise instead of failing silently

**Where:** `src/python/lib/rmtc/core/track/store/cypher/connection.py:251-256`,
`_update_properties()`.

The stale-write check now raises `RMTCException(f"Stale {entity} is not updated, remote store is
newer")` instead of logging a warning and silently returning. Callers (`update_entities`, `push`)
will now see the conflict instead of quietly losing the write. This is exactly the "don't fail
silently" mitigation the original write-up called for; a full optimistic-locking/merge strategy is
still a separate, bigger project, but the silent-data-loss defect itself is closed.

## 4. [Partially addressed] Reverse type-name resolution now rejects re-registration — which may be too strong

**Where:** `src/python/lib/rmtc/system/__init__.py:1093-1096`, `Factory.register()`.

The fix does not key `_inverse_modules` by `(class_path, version)` as this document originally
suggested. Instead it added a guard immediately before the assignment:
```python
if class_path in self._inverse_modules:
    raise RMTCException(f"Already registered {class_path}")
```
This converts the old silent, load-order-dependent overwrite into a loud failure — which is an
improvement for catching *accidental* duplicate registration — but it now also rejects the
*legitimate* case the module system explicitly documents: the same `class_path` registered under
two different versions as part of a normal deprecation ("Type Names can be deprecated and
version-less"). As written, loading any module YAML that maps two versions to one `class_path`
will now raise during `load_module()` rather than silently mis-resolving. The underlying
reproducibility problem — `resolve_inverse()` needs a version-aware answer, not just a
duplicate-registration error — is not yet solved; this fix trades a silent correctness bug for a
hard crash on a pattern the system is supposed to support.

## 5. [Partially resolved] Store-name partitioning is enforced on some traversal paths but not others

**Where:** `src/python/lib/rmtc/core/track/store/cypher/connection.py`.

`get_runs` (line 766), `get_inferences` (line 969), `get_timestamps` (line 1049), `_get_entities`
(line 1116), and the member-cleanup query at the end of `_update_properties`'s relation handling
(line 428, filtering both `a._store` and `b._store`) now all filter by `_store`. This closes the
gap for the entity-lookup paths and for detecting/removing stale relationship members.

**Still open:** `get_sources`, `get_related`, `get_descendents`, `get_derivatives` (lines 861-935)
and the relation-fetch query inside `_sync_properties` (line 648-658) — exactly the queries behind
the headline "trace an inference back up through weights, run, model, dataset, license" feature —
still only filter the query's entry node (`a._store=$store`) and do not filter the *returned* node
`b`. An edge connecting a node in one store to a node in another therefore still lets provenance
tracing silently cross environment boundaries on these specific paths, same as the original
finding, just narrowed from "every traversal method" to "the four generic-hop methods plus one
sync query." The existing fix pattern (add `AND b._store=$store` alongside the `a` filter) still
needs to be applied to these five call sites — and separately, the `a.store` typo noted in item 1
means the relation-*connect* query in `_update_properties` isn't actually applying its intended
`a` filter either, despite appearing to.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
