# RMTC — Critique / Known Limitations Catalog

This is an exhaustive inventory of hacks, TODOs, stubs, and other questionable practices found in
the RMTC codebase as of this review, plus additional concerns identified during review that are
**not** flagged in the code itself. It intentionally overlaps with self-admitted caveats in
`technical_notes.md` — the goal here is completeness, not novelty. For the five most severe
*systemic* defects (bugs in fully-implemented, load-bearing code), see
[`systemic_design_flaws.md`](systemic_design_flaws.md); those are cross-referenced below rather
than repeated in full.

---

## 1. Explicit `TODO` comments (75 occurrences)

By area, with a note on which look cosmetic vs. load-bearing:

**Artifacts / tensors / IO** — mostly real gaps in format coverage:
- `core/ops/artifacts/onnx/models.py:30,57` — input/output shape isn't derived from the ONNX
  description; the "valid" check is hardcoded to one runtime.
- `core/ops/artifacts/torch/models.py:112` — unclear whether weights should move devices; flagged
  as possibly too heavy an operation to do implicitly.
- `core/ops/io/oiio/image.py:87,100,131` — OIIO IO only reads/writes the *first* subimage of a
  multi-part EXR, and unconditionally assumes 4-channel (RGBA) images.
- `core/ops/io/onnx/models.py:42` — GPU support assumes CUDA specifically (no ROCm/other backends).
- `core/ops/io/usd/camera.py:85,91` — camera framerate isn't unified to the USD stage's FPS; tensor
  loading on `camera.init()` is unimplemented.
- `core/ops/process/image/color.py:13` — no shape validation on the color-normalisation processor.
- `ops/assets.py:202,361` — asset tensor layout comment says it should be WHC but doesn't confirm
  it is; `Table.structure` is described as a stub for "a collection of all members."
- `ops/artifacts.py:362,1333,1343,1350` — see §3, these back onto real `NotImplementedError`s.

**Training / scheduling**:
- `core/ops/infer/simple/inferers.py:136` — explicit race-condition acknowledgement: "race
  condition if dataset is being used in multiple places?" Never resolved.
- `core/ops/train/torch/trainers.py:120,125,137,229` — torch-specific code not yet separated from
  torch-agnostic code; `run.dataset` should be plural (i.e. multi-dataset runs aren't really
  supported); batching is described as "single batch right now"; model should be a duplicate
  rather than mutated in place but isn't.
- `ops/scheduling.py:300`, `ops/__init__.py:113,132,238,291,345` — "make this work async" repeated
  four times across the module; scheduling of build/publish steps is a known gap, not a task queue.
- `gui/common/widgets.py:62,87` — same "make this work async" gap surfaces in the GUI layer.
- `gui/training/widgets.py:290` — "Add support for other schedulers (eg. cloud or cue based
  systems)" — the GUI itself acknowledges the scheduler is hardcoded to local (see §6).

**Pipeline / builders**:
- `core/ops/pipeline/nuke/builders.py:88,103` — "this is weakly enforced, bolster" appears twice,
  about validation before a build step.
- `core/ops/pipeline/onnx/builders.py:62` — only some packagers are ONNX-compatible; the rest
  aren't converted.

**Store / interface**:
- `core/track/store/cypher/connection.py:583` — relationship ordering by index is not actually
  guaranteed by the query as written; array property order returned from Neo4j/AGE "is not
  guaranteed to be ordered" per the comment itself.
- `core/track/store/cypher/connection.py:690` — `get_runs(name=...)` "pulls all runs" instead of a
  targeted query — a documented perf shortcut.
- `core/system/interface/rest/flask.py:37,58,108,205,245`, `ops/interface.py:85,116,136`,
  `track/interface.py:85,116,136` — all three copies of the REST interface layer are marked
  "incomplete testing code only"; list ordering in JSON serialization isn't supported.

**System core**:
- `system/objects.py:143` — array-typed properties should return an immutable tuple to stop
  unmanaged in-place `append`/`remove` (the docs separately warn about this same issue).
- `system/objects.py:1282` — entity `category` should be an enum, currently a bare string (also
  flagged in `technical_notes.md`).
- `track/__init__.py:161` — store connections don't hold an auth token, credentials are re-used
  as-is rather than exchanged for a session token.
- `track/__init__.py:215` — a component "should listen to the store" but doesn't yet.
- `track/entities.py:1095` — entry lists on entities aren't "native," described as a workaround.

## 2. `HACK` comments (11 occurrences)

- `core/ops/artifacts/torch/models.py:161` — `# HACK : remove` with no further explanation of what
  it works around or when it can be removed.
- `core/ops/io/oiio/image.py:128` — `# HACK - something goes awry` immediately preceding an OIIO
  call; the workaround is undocumented and the underlying OIIO bug/behavior is unknown.
- `core/ops/pipeline/nuke/builders.py:122` — uses `-i` instead of `-t` when invoking Nuke because
  `-t` "does not actually execute the node."
- `ops/io.py:96` — "not all IOs support creation of URIs," worked around ad hoc rather than via a
  capability check on the IO interface.
- `ops/artifacts.py:349` — tensors are padded to a minimum of 1 element "otherwise tensor invalid."
- `system/objects.py:405` — Python `datetime.datetime` is upcast to RMTC's `Datetime` "via the ISO
  string" round-trip rather than a direct constructor path.
- `system/objects.py:892` — a property's value is set "at last minute — after property is created"
  specifically to dodge a notification-ordering bug rather than fixing the ordering itself.
- `system/objects.py:1015` — comment admits a failure mode "keeps failing, isn't terminal, but
  indicates a problem" — a known-broken condition that is tolerated rather than fixed.
- `system/objects.py:1109` — JIT sync deliberately suppresses notifications "as we don't want to
  pull everything," a workaround for the JIT sync approach eagerly recursing.
- `gui/common/properties.py:28` — catches `RuntimeError` broadly to swallow "C++ warnings" from Qt
  object deletion races, rather than fixing the widget lifetime issue.
- `gui/ingestion/widgets.py:32,43,91` — node names are mangled to avoid clashing with NodeGraphQt's
  own naming, and double-connection signals are suppressed with a boolean flag rather than fixed at
  the signal-connection level.
- `gui/provenance/widgets.py:97,563,636` — NodeGraphQt is worked around three separate times because
  it doesn't expose real Qt signals from nodes and sometimes silently skips "host" entities.

## 3. Stubbed / `NotImplementedError` code paths (28 occurrences)

Some of these are legitimate abstract-base-class contracts (a subclass is expected to implement
them, and at least one concrete subclass does) — those aren't listed here. The following either
have **no concrete implementation anywhere**, or sit on a **documented core code path** that will
crash if exercised:

- **`track/store.py:575,586` — `Store.get_lock()` / `Store.release_lock()`.** Not implemented by
  *any* store backend (Cypher/Neo4j/AGE), and not called anywhere else in the codebase either. This
  is a completely dead concurrency-control API: the interface exists, the docstring describes
  correct usage ("ensure the lock is released after use... handling any cases where code may error
  or exit unexpectedly"), but there is no implementation and no caller. See `systemic_design_flaws.md`
  §3 for the related, separate issue that write conflicts are also silently dropped rather than
  using any locking at all.
- **`ops/artifacts.py:1339,1347,1355` — `Collection.tensors` getter/setter and `Collection.structure()`.**
  `Collection` is one of the three documented core `Dataset` types (`technical_notes.md` §"Dataset
  Types"). Its tensor-batching methods are unconditional `raise NotImplementedError()` — any
  training/inference code path that tries to pull batched tensors from a `Collection` dataset will
  crash. The docs do note Collections are "not common," which is presumably why this has gone
  unnoticed.
- **`core/ops/scheduling/aws/schedulers.py:32,36,40,44,68`** — every lifecycle method of the AWS
  scheduler stub raises `NotImplementedError`; there is no AWS-backed scheduling despite the module
  existing and being importable.
- **`core/ops/pipeline/asset_managers/filesystem.py:111,133`** — the default (filesystem) asset
  manager itself raises `NotImplementedError` on some operations, meaning even the reference/default
  asset manager implementation is incomplete.
- **`core/ops/io/onnx/models.py:26,50,59`, `core/ops/artifacts/onnx/models.py:84,93`** — ONNX model
  IO/artifact wrapping has multiple unimplemented methods despite ONNX being one of the two headline
  supported model formats (alongside PyTorch) and a dependency listed in the top-level README.
  Whether these are hit depends on which parts of the ONNX flow a caller exercises — this is worth
  smoke-testing explicitly rather than assuming coverage from the "pipeline" example.
- **`core/track/store/cypher/neo4j.py:37,40`** — two methods on the Neo4j connection are
  unimplemented, meaning parts of the Cypher `Connection` contract are only actually satisfied by
  the AGE backend, not the Neo4j one, despite both being marketed as supported (`README.md` lists
  "Neo4j storage wrapper" as a *future* roadmap item, which is inconsistent with an existing
  `neo4j.py` file that implements most, but not all, of the interface already).
- **`core/system/interface/rest/flask.py:265` — `Server.close()`.** Unimplemented; the dev server
  has no clean shutdown path.
- **`system/__init__.py:979` — `Factory.save()`.** Module registrations loaded from
  `RMTC_MODULES` YAML can never be written back out programmatically; any registration created at
  runtime (vs. loaded from YAML) is not persistable.
- **`core/ops/io/usd/camera.py:203`** — one USD camera IO method is unimplemented.
- **`core/ops/io/filesystem/json.py:87`** — one method of the JSON filesystem IO is unimplemented.

## 4. Subsystems the project itself documents as unimplemented (not re-litigated here, but listed for completeness)

Per `technical_notes.md` and `README.md`: the **REST interface** (server/client bridge between two
`System` instances), **C2PA** watermarking/signing, **environment/package management**
(conda/pip/rez — the `PackageTracker` docstring says outright "does not perform any true
environment function"), the **wall/render-farm scheduler** (only a facility-internal, unreleased
implementation exists; the open-source repo only ships a `local` scheduler and a non-functional
`aws` stub), and a **Nuke DCC plugin**. These are legitimate roadmap items, not hidden defects — but
anyone evaluating RMTC for production should know that "the system has been designed for
delegation and abstraction" for these subsystems in principle only; no facility can currently
consume them without writing the implementation from scratch.

## 5. Guardrails that exist only as data model / convention, not runtime enforcement

RMTC is an in-process Python library used by trusted pipeline code, not a sandboxed service — any
check expressed in Python is bypassable by a caller with API access, and that's an accepted
tradeoff of the architecture, not a bug. Still, worth cataloguing exactly which of RMTC's marketed
protections fall into this "light enforcement" bucket so nobody mistakes them for hard guarantees:

- **License/Permission guardrails.** `License.is_permitted()` exists and is used for filtering
  candidate artifacts against a `Solution`'s requirements, but is never called from the actual
  inference/training execution paths (`core/ops/infer/simple/inferers.py`,
  `core/ops/infer/local/schedulers.py`, `core/ops/train/local/schedulers.py`). A restrictive license
  does not stop a training or inference job from running; it only affects what artifacts a
  `Solution`-level search surfaces.
- **Immutability.** Described as a core concept ("Artifacts in RMTC are immutable and should not be
  deleted") but enforced only by the `Store.immutable` config flag gating `delete_all`/
  `delete_entities`, and by convention around not appending/removing structural members after
  creation. Any property (including on a fully-synced entity) can be mutated and re-pushed via the
  ordinary `update` path — there is no write-time check that blocks rewriting a property on an
  entity that's supposed to represent immutable history.
- **Factory "whitelisting."** `README.md` itself calls the `rmtc`-module-prefix convention "a form
  of light whitelisting" — `class_path` in a module YAML can point at any importable symbol, so this
  was never intended as a hard security boundary; it's namespace hygiene, not access control.

## 6. Concurrency & coupling concerns

- **GUI shares one `System` instance across every tool window** (`gui/__init__.py:52` and
  onward) — `SignalBox`, `Junction`, `TrainTrack`, `Toolbar`, `Publisher`, `Scheduler`,
  `ObjectPropertyEditor`, `DatasetViewer` all hold a direct reference to the same mutable `System`.
  There's no transaction/undo boundary between windows, so one tool's uncommitted local edits are
  visible to (and mutable by) every other open tool before a `push()`.
- **The GUI's `Scheduler` widget hardcodes `LocalTrainScheduler`/`LocalInferScheduler` by direct
  import** (`gui/common/widgets.py:10-11,54,79`) rather than resolving a scheduler through RMTC's own
  Factory/type-name mechanism, the same pattern used everywhere else in the system for pluggability.
  A facility wanting to plug in a farm scheduler has to fork the GUI, not just register a new type.
- **No CI pipeline of any kind.** No `.github/workflows`, no other CI config found anywhere in the
  repo. Tests exist (~25 files / ~2,900 lines, mostly integration-style against a real store) but
  nothing runs them automatically on a PR/push. GUI test coverage is a single 116-line file using
  mocked NodeGraphQt ports — no real Qt widget interaction is tested.

## 7. Security / operational hygiene

- **Credentials are plaintext throughout.** Config YAML (`res/config/*.yaml`) stores DB
  username/password directly; `RMTC_USER`/`RMTC_PW` env vars are read with no secrets-manager hook;
  `Config.__str__` prints the config path and override dict with no redaction; the driver
  connection call passes `(username, password)` straight through. There is no encryption at rest, no
  redaction in logs/`repr`, and no integration point for a secrets manager (Vault, AWS Secrets
  Manager, etc.) — a facility wanting one has to build it themselves.
- **A bare `except:` swallows every exception when parsing `RMTC_VERSION`**
  (`system/__init__.py:79-82`, `# pylint: disable=bare-except`). This is a deliberate, linted
  exception to the project's own style rules, but it means any error in reading/parsing that env
  var — not just a malformed version string — is silently replaced with `"0.0.0"`, which could mask
  an unrelated environment misconfiguration.

## 8. Additional concerns found during this review, not marked anywhere in the code

These weren't flagged by any comment, docstring, or TODO — they were found by reading the
implementation directly. Full writeups (with evidence and an easy fix) are in
[`systemic_design_flaws.md`](systemic_design_flaws.md); summarized here for completeness of this
catalog:

- Every Cypher/AGE query in `core/track/store/cypher/connection.py` is built by raw string
  interpolation of entity IDs, labels, and property values — there is no parameterized-query usage
  anywhere in the store layer. See flaw #1.
- `Property._convert()`'s `ENUM` branch (`system/objects.py:387-399`) computes a valid converted
  value from a string assignment, then unconditionally discards it and returns the property's
  `default` instead, if one is set — silently reverting any Enum property with a default to that
  default on every string-based assignment. See flaw #2.
- Stale writes are detected (`core/track/store/cypher/connection.py:227-235`) but the response is a
  log line and a silent no-op `return` — the caller has no way to know its update was dropped. See
  flaw #3.
- `Factory._inverse_modules` (`system/__init__.py:1058`) maps `class_path -> TypeName` and is
  unconditionally overwritten on every `register()` call, so when the same class is registered
  under multiple versions (an explicitly supported deprecation pattern), newly created entities get
  stamped with whichever version was registered *last* during module loading, not a specific
  intended version. See flaw #4.
- Store-name partitioning (`rmtc` vs `rmtc_test` vs `rmtc_examples`) is enforced on direct entity
  lookup but not on any of the provenance-tracing relationship queries
  (`get_sources`/`get_related`/`get_descendents`/`get_derivatives`, and the relation-sync queries in
  `_update_properties`/`_sync_properties`) — tracing can silently cross store/environment
  boundaries. See flaw #5.
---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project