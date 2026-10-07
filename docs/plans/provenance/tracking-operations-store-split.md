# Split the Store into Tracking & Operations Databases

## Feature Description

Split RMTC's single Cypher/AGE graph store into two cross-referenced stores: a **tracking**
store holding only immutable provenance facts (lineage, licenses, artifact identity), and an
**operations** store holding mutable runtime/job state (training progress, metrics, checkpoint
write status). Today both live in the same graph and the same `Entity` objects. For example
`Run` (`src/python/lib/rmtc/track/entities.py:341-369`) mixes immutable provenance references
(`model`, `dataset`, `validation`, `test`, `solution` — all `member=False, direction=IN`) with
mutable operational fields on the *same* entity (`metric`, `epochs`, `result_checkpoints`,
`result_weights` — all `member=True`), and `LocalTrainScheduler`
(`src/python/lib/rmtc/core/ops/train/local/schedulers.py:82-94`) writes training results
(`self.run.metric`, `self.run.result_weights`, `self.run.result_checkpoints`) back into the exact
same graph node that also carries the run's permanent provenance edges. The two concerns should
be separable: the tracking store answers "what produced what, under what license," the
operations store answers "how is this job doing right now" — each referencing the other by
entity ID rather than one duplicating the other's fields.

## Criticality

**High** — this isn't a new capability gap, it's a structural fix to the persistence layer two
of the five cataloged systemic flaws already point at. `docs/review/flaws.md` flaw #3
(write-write conflicts on entities are detected then silently dropped, `connection.py:227-235`)
and flaw #5 (store-name partitioning enforced on lookup but not relationship traversal,
`connection.py` `get_sources`/`get_related`/`get_descendents`/`get_derivatives`) are both made
worse by mixing high-frequency mutable writes (training metrics updated every epoch) with
low-frequency immutable provenance writes in the same graph and the same conflict-detection path.
A job writing its metric every epoch is far more likely to lose a race against a concurrent
writer than an artifact that's written once and never touched again — currently, losing that
race silently drops the write with only a log line. Splitting the stores turns a systemic
provenance-integrity risk into an isolated, higher-churn-tolerant operations concern.

## T-Shirt Size

**L** — ~1.5-2 weeks. Not greenfield (the `Connection`/`Queries`/`Entity` abstractions in
`track/store.py` already exist and are reused), but touches the core persistence path used by
every entity in the system. Main cost centers: (1) classifying every existing property on every
Entity subclass as tracking- or operations-owned, (2) routing property reads/writes for
split entities to the correct backing connection, (3) a cross-reference mechanism (store an
entity ID + store name pointer instead of a duplicated field), (4) a migration path for existing
single-store deployments, (5) updating every `get_*` query in `CypherConnection` that currently
assumes one graph. No new external dependency — the operations store can reuse the same Cypher
backend as a second AGE graph/Neo4j database, or move to a simpler key-value/document store
later as a follow-on (out of scope here).

## How to Implement

1. **Classify fields, not entities.** Do not split by entity *class* — a `Run` needs both halves.
   In `track/entities.py`, audit every `add_property()` call across `Run`, `Weights`,
   `Checkpoint`, `Model`, `Dataset`, `Artifact`, `Solution`, `License` and tag each as
   `tracking` (identity, lineage edges, license/version/URI — written once, read often) or
   `operations` (`metric`, `epochs`, in-progress status, any field a running job updates
   repeatedly). `Run.metric`/`Run.epochs`/`Run.result_checkpoints`/`Run.result_weights`
   (`entities.py:358-369`) are the clearest operations fields; `Run.model`/`Run.dataset`/
   `Run.solution`/`Run.version`/`Run.uri` (`entities.py:341-355`) are tracking fields.

2. **Add a second `Connection` instance, not a new abstraction.** `track/store.py` already
   defines `Connection`/`Queries`/`Proxy` as the interface `CypherConnection` implements
   (`core/track/store/cypher/connection.py:37`). Instantiate two `CypherConnection`s — one
   pointed at a `tracking` store name/graph, one at an `operations` store name/graph — reusing
   the existing `_store` partitioning mechanism (`connection.py:8-16` docstring) as the split
   boundary instead of (or in addition to) its current prod/test/examples use.

3. **Route property sync by classification, not by entity.** Extend `Entity`
   (`track/store.py:52` onward) or its `Property`/`PropertyContainer` plumbing
   (`system/objects.py`) so `sync`/`update` on a mixed entity like `Run` issues two writes: the
   tracking-classified properties go to the tracking connection, the operations-classified
   properties go to the operations connection, both keyed by the same entity ID. Reads merge the
   two results back into one `Run` object transparently to calling code (`System`, GUI,
   schedulers) — this is the "cross-reference, don't duplicate" requirement: the operations
   store holds `run_id -> {metric, epochs, ...}` and *references* the tracking store's `run_id`
   node rather than re-storing `run.model`/`run.dataset`/etc.

4. **Fix the scheduler write path.** `LocalTrainScheduler` (`train/local/schedulers.py:82-94`)
   currently writes `self.run.metric`/`result_weights`/`result_checkpoints` directly onto the
   tracked `Run` object. Once split, this write path should go through the operations connection
   only — the scheduler never needs to touch the tracking store mid-run, which also narrows the
   write-write-conflict blast radius from flaw #3 to operations data only.

5. **Update the traversal queries.** The four `get_*` methods flaws.md #5 already flags as
   missing `_store` filtering (`get_sources`, `get_related`, `get_descendents`,
   `get_derivatives`, `connection.py` lines ~811-865) must be store-scoped correctly under the
   split — a provenance trace should only ever traverse the tracking graph; it must not need to
   reach into the operations store at all, which makes flaw #5 easier to close correctly (fewer
   queries need cross-store awareness, not more).

6. **Migration:** write a one-time script that reads existing single-store entities, splits each
   into its tracking/operations halves per the field classification from step 1, and writes them
   into the two new stores preserving IDs. Existing deployments must not lose history.

7. **Tests:** unit tests for the property-routing logic (a mixed entity's tracking fields land
   in one store, operations fields in the other); an integration test that runs a full
   train → checkpoint → finish cycle and confirms the tracking store's `Run` node is never
   touched by per-epoch writes; a migration test against a small fixture single-store dataset.

## Considerations

- **Depends on / interacts with:** flaws.md #3 (write-write conflict handling) and #5 (store-name
  partitioning) — this split is a structural mitigation for both, but does not replace fixing the
  underlying conflict-signaling bug (`connection.py:227-235` still silently drops a stale write;
  it should still raise/report even after the split). Coordinate with
  `address-systemic-flaws.md`.
- **Open design question:** does the operations store need to be a graph database at all? Most
  operational fields are simple scalars keyed by entity ID with no lineage/edges of their own —
  a document or key-value store may be a better long-term fit and cheaper to scale for
  high-frequency writes (e.g. per-epoch metrics) than a graph DB. This plan scopes the initial
  split to "same Cypher backend, second store name" for minimal risk; a backend swap for the
  operations store is a natural, separately-scoped follow-on.
- **Open design question:** where does the boundary sit for entities that are *mostly*
  operational, like `Checkpoint` (metric/epoch tracked per checkpoint) — does the checkpoint
  identity (which run produced it, its URI) live in tracking while its metric lives in
  operations, splitting a single entity's fields across stores the same way `Run` does?
- **Risk:** two connections instead of one roughly doubles the persistence layer's failure
  surface (two DBs to reach, two things that can be down or slow) and introduces a new class of
  bug — a tracking-store write succeeding while its paired operations-store write fails (or vice
  versa), leaving a cross-referenced pair inconsistent. Needs an explicit decision on write
  ordering/rollback (e.g. always create the tracking entity first, since operations entities
  reference it) rather than assuming both writes succeed together.
- **Out of scope:** changing the operations store's backend technology (see design question
  above), and any change to how the GUI/System-facing API exposes entities — callers should see
  one merged `Run` object exactly as they do today; the split is purely a persistence-layer
  concern.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
