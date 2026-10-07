# Address Systemic Flaws

## Feature Description

Fix the 5 most severe *systemic* design defects in the persistence and type-resolution layers, catalogued in `docs/review/flaws.md`. These are bugs in fully-implemented, load-bearing code that does not behave the way the architecture requires. Unlike the separate bug-catalog (13-16 items of narrower scope), these 5 span entire subsystems and directly undermine RMTC's core pitch: trustworthy provenance. Flaw #1 is a real injection risk; flaw #3 silently drops writes; flaw #2 causes enum corruption on every default-valued enum property.

## Criticality

Critical. Flaws #1 (injection), #3 (silent write conflict loss), and #2 (enum corruption) are ship-blockers. Flaws #4 and #5 are reproducibility defects that corrupt the version/environment tracking that provenance depends on.

## T-Shirt Size

XL. Flaw #1 (parameterized queries) is a mechanical rewrite of ~500 lines in one file, but high-risk (wrong refactor breaks persistence). Flaw #3 (write conflicts) requires exception-handling changes across multiple callers. Flaws #2, #4, #5 are smaller but require careful design decisions. Estimated 3-5 dev-days + 1-2 days QA/round-trip testing.

## How to Implement

**Fix order (security-first, then severity; strict sequence dependency):**

### Flaw #1: Parameterized Queries (2d, ship-blocker security fix)

**Why first:** An injection vector that affects the persistence layer holding credentials, provenance, and the entire artifact graph. Highest risk; easiest to introduce a regression.

- **File:** `src/python/lib/rmtc/core/track/store/cypher/connection.py` (~1,500 lines, 60+ queries)
- **Fix approach:**
  1. **Audit all query patterns** (lines 74, 98, 135-141, 168, 255, 265-309, 343-345, 699-708, 813-816, 954, 1042, 1088-1090). Identify which parts are f-strings that need parameterization vs. which are category/label strings that should stay server-side-controlled.
  2. **Refactor read_query / write_query signatures** to accept `(query: str, params: dict)` instead of just the query. Update all callers in the connection.
  3. **Convert every f-string value substitution** to a `$param` placeholder. Examples:
     ```python
     # OLD: f"SET e.{prop.name} = '{prop.value}'\n"
     # NEW: f"SET e.{prop.name} = $val\n" with params={'val': prop.value}
     ```
  4. **Leave entity IDs and labels as sanitized server-side strings** (Neo4j/AGE validates these as valid identifiers before execution).
  5. **Test:** Create an injection-proof test case — a property value with quotes, apostrophes, semicolons, Cypher operators — verify it's stored and retrieved exactly (not interpreted as code).

### Flaw #2: Enum property conversion (0.5d, small but pervasive)

**Why second:** Fix is a 1-line return statement. Multiple enums throughout the system are affected; fixing this early prevents cascading corruption in later tests.

- **File:** `src/python/lib/rmtc/system/objects.py:387-399`
- **Fix:** After the string-to-enum conversion is successful, return immediately instead of falling through to the default check:
  ```python
  if isinstance(value, str):
      index = list(self._type_class).index(self._type_class[value])
      return self._type_class(index)  # return immediately
  # Fall through only for non-string assignments
  if self.default is not None:
      return self.default
  ```
- **Test:** Create an enum property with a default, assign a string value, verify it reads back as that string value (not the default).

### Flaw #3: Silent write-conflict drops (1.5d, critical for multi-writer scenarios)

**Why third (after #1, #2):** Depends on the store layer being correct (flaw #1 must be safe first); affects every `System.push()` call.

- **File:** `src/python/lib/rmtc/core/track/store/cypher/connection.py:227-235`
- **Current behavior:** Detects stale writes, logs, then returns silently. Caller has no idea its update was dropped.
- **Fix approach:**
  1. **Raise an exception instead of silent return** — create a new `RMTCConflictException` or use the existing `RMTCException`:
     ```python
     if timestamps[0] > entity.timestamp:
         raise RMTCConflictException(f"Write conflict: {entity} — remote store is newer")
     ```
  2. **Update callers** (`update_entities`, `push()`) to catch and handle the exception — either retry, merge, or surface to the user.
  3. **Test:** Simulate two writers updating the same entity in sequence, verify the second writer's `push()` raises an exception (or gets a return code indicating conflict).

### Flaw #4: Reverse type-name resolution is last-registration-wins (1d, reproducibility issue)

**Why fourth:** Affects entity versioning; once #1-3 are solid, fix the factory's version inconsistency.

- **File:** `src/python/lib/rmtc/system/__init__.py:1014-1058` (register method, _inverse_modules dict)
- **Fix approach (conservative option):** Add deterministic sorting so the behavior is predictable even if it's not perfect:
  1. Change `_inverse_modules` dict to `_inverse_modules: dict[tuple[str, str], str]` — keyed by `(class_path, version)` not just `class_path`.
  2. In `resolve_inverse()`, accept a version hint or default to the highest non-deprecated version (sorted deterministically).
  3. **OR (better, requires more design):** require `resolve_inverse()` callers to pass a version, so created entities are stamped with an *intended* version, not a load-order accident.
- **Test:** Register the same class under two versions, verify entities created via that class are consistently stamped with the highest (or a specified) version, not the last-loaded one.

### Flaw #5: Store-name partitioning not enforced in traversal (1d, environment-isolation issue)

**Why fifth (lowest priority but still critical):** Without this, prod/test/examples data can silently cross-pollinate. Fix after #1-4 so the store layer is stable.

- **File:** `src/python/lib/rmtc/core/track/store/cypher/connection.py` — compare `_get_entities` (line 1042) and `get_assets` (line 954, both have `WHERE n._store='{...}'`) against `get_sources`, `get_related`, `get_descendents`, `get_derivatives` (lines 811-865), and the relationship walks in `_sync_properties`/`_update_properties`.
- **Fix:** Add `AND b._store='{self.connection.store.name}'` (or parameterized equivalent after flaw #1 is fixed) to every `MATCH` clause in provenance-tracing queries. Copy the filter pattern from `_get_entities` already in the file.
- **Scope:** ~12-15 queries need the filter added.
- **Test:** Create entities in one store (`rmtc`), trace provenance, verify relationships don't cross into `rmtc_test` even if a malformed edge exists.

## Considerations

- **Sequence dependency:** Flaw #1 must be rock-solid before any tests of #3 (write conflicts) because the store layer is the test harness. Flaws #2, #4, #5 are independent once #1 is stable.
- **Risk:** Parameterized queries are a large refactor; strong code review and integration testing are essential. Consider pair-programming or a second set of eyes before merging.
- **Data integrity:** Once flaws are fixed, audit existing data for corruption (enum properties with wrong values due to #2, relationships crossing store boundaries due to #5, stale writes that happened to persist despite #3). Document any data migration needed.
- **Out of scope:** This plan does not address the broader "locking strategy" mentioned in critique.md §3 (Store.get_lock/release_lock are dead). That's covered in the critique-issues plan.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
