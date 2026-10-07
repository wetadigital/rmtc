# Asset Manager Responsibility Split

## Feature Description

Better division of responsibilities for asset manager — currently `FilesystemManager` conflates read/write, URI resolution, provenance/publish state, and lineage tracing in a single class. The deeper problem is upstream of `FilesystemManager`: `rmtc.ops.pipeline.AssetManager` itself inherits `rmtc.track.asset_manager.BaseAssetManager` (provenance-shaped interface: `publish`, `unpublish`, `is_published`, `trace_sources`, `trace_derivatives`, `watermark`, `allocate_version`) *and* `BaseReaderWriter` (I/O-shaped interface: `read`, `write`, `init`, `reset`, `exists`, `relocate`) in one concrete class that lives in `ops`. Every filesystem-backed asset manager then has to either implement provenance methods it has no business answering (a filesystem has no graph) or stub them out — which is exactly what `FilesystemManager.trace_sources`/`trace_derivatives` do today (log a warning, return an empty set).

The split: move provenance/lineage/publish-state ownership into `track`, backed by the existing graph `Store`/`Connection`/`Queries` abstraction (`rmtc.track.store`, concretely `rmtc.core.track.store.cypher.*`), and narrow `ops` to pure read/write/existence mechanics against a resolved URI. This mirrors a pattern that already exists and works in the codebase: `Entity.trace_sources`/`Entity.trace_derivatives` (`rmtc/track/store.py:236-278`) already trace lineage by calling `connection.queries.get_sources([self])`/`get_derivatives([self])` against the graph — they just aren't the code path the asset manager uses. The asset manager's own `trace_sources`/`trace_derivatives` are a second, parallel, URI-based attempt at the same concept that can never succeed on a filesystem backend. Removing that duplication is the core of this refactor, and surfaces/fixes bugs.md #6 (`is_uri_supported()` returns `False` — not a crash — when `self._root is None`) and #7 (`relocate()` passes a scalar `uri`/`artifact` into `exists()`/`is_published()`, which both iterate their argument) as a natural side-effect.

## Criticality

High. Bugs #6 and #7 block real use cases (rootless config, relocation migrations). The responsibility split unblocks facility-specific asset manager implementations (e.g. an S3 or Open Asset IO-backed reader/writer) without forcing every implementation to re-decide how publish-state and lineage work, and it removes a class of bugs where "can't trace on this backend" silently returns an empty result instead of correctly delegating to the graph.

## T-Shirt Size

M/L. ~4-5 new/changed interface files across `ops` and `track`, 2-3 concrete implementations, one call-site migration (`AssetManager.trace()`). ~2,000-2,500 lines new/changed. No new dependencies — reuses the existing `Store`/`Connection`/`Queries` machinery.

## Target Class Layout

```
rmtc.ops.pipeline.BaseReaderWriter (ABC)        -- unchanged responsibility, narrowed contract
    read, write, init, reset, exists, resolve, resolve_inverse, relocate
    (relocate here means "move the physical bytes", NOT "update provenance for a move")

rmtc.core.ops.pipeline.asset_managers.filesystem.FilesystemReaderWriter(BaseReaderWriter)
    -- was FilesystemManager; publish/lineage methods removed entirely
    -- is_uri_supported / create_uri / delete_uri stay here: they are about
       filesystem path & URI-scheme mechanics, not provenance

rmtc.track.asset_manager.BaseAssetManager (ABC) -- becomes the composition root
    publish, unpublish, is_published, trace_sources, trace_derivatives, watermark,
    allocate_version
    -- gains a dependency on a `reader_writer: BaseReaderWriter` (ops) and a
       `connection: Connection` (track/graph) rather than implementing I/O itself

rmtc.core.track.asset_manager.ProvenanceAssetManager(BaseAssetManager)
    -- new concrete class, lives in track's core, not ops's core
    -- trace_sources(artifacts)   -> connection.queries.get_sources(entities_for(artifacts))
    -- trace_derivatives(...)     -> connection.queries.get_derivatives(...)
    -- is_published(artifacts)    -> graph publish-state check, falling back to
                                      reader_writer.exists([...]) only as a physical sanity check
    -- publish/unpublish          -> update graph publish-state + delegate byte writes to reader_writer
    -- delegates read/write/init/reset/exists/resolve straight through to `self._reader_writer`
```

`rmtc.ops.pipeline.AssetManager` (the current class that inherits both ABCs) goes away as a concrete base — its I/O-only methods (`init`, `read`, `write`, `reset`) move down into `FilesystemReaderWriter` (or a shared `AssetManagerReaderWriterMixin` if more than one backend needs the same generic-over-IO logic), and its provenance-shaped methods (`build`, `trace`, `watermark`, pipeline registration) move up into `ProvenanceAssetManager`.

## How to Implement

1. **Narrow `BaseReaderWriter` and confirm it has no provenance leakage (0.5d):** `rmtc/ops/pipeline.py:13-46`. Already close to correct — `is_immutable`, `init`, `read`, `write`, `reset`, `relocate`, `exists` are all I/O-shaped. No signature changes needed here, just remove the `AssetManager` class at the bottom of this file (lines 100-298) once its logic has been redistributed (steps 2 & 4).

2. **Split `FilesystemManager` into a pure reader/writer (1d):** Refactor `src/python/lib/rmtc/core/ops/pipeline/asset_managers/filesystem.py`:
   - Rename `FilesystemManager` → `FilesystemReaderWriter`, drop the `AssetManager` base class, implement `BaseReaderWriter` directly.
   - Keep: `resolve`, `resolve_inverse`, `exists`, `is_uri_supported`, `create_uri`, `delete_uri`, `relocate` (physical file move only — strip the `is_published()` check described in step 3, it doesn't belong here), `allocate_version` (arguably folder/version-numbering is filesystem-specific, keep it, but see step 3 for who calls it).
   - Remove entirely: `publish`, `unpublish`, `is_published`, `trace_sources`, `trace_derivatives`. These lines (45-76, 107, 112-113 in the current file) either duplicate what the graph store already does correctly (lineage) or conflate a physical existence check with a provenance decision (`is_published`).
   - Fix bug #6 while doing this: `is_uri_supported` line 39-40 currently returns `False` silently when `self._root is None`. Decide the semantics explicitly now that this class has a single, clear responsibility (URI-scheme validity): rootless should mean "accept all `file://localhost` URIs" (`if self._root is None: return True` before the `is_relative_to` check) since a root is described as an optional scoping mechanism, not a requirement.

3. **Build the provenance side in `track`, backed by the graph (1.5d):** New file `src/python/lib/rmtc/core/track/asset_manager.py`:
   - `ProvenanceAssetManager(rmtc.track.asset_manager.BaseAssetManager)`, constructed with `reader_writer` (an `ops.BaseReaderWriter`, e.g. `FilesystemReaderWriter`) and `connection` (a `track.store.Connection`, e.g. `AGEConnection`).
   - `trace_sources(artifacts)` / `trace_derivatives(artifacts)`: for each artifact, resolve to (or fetch) its backing `Entity` and delegate to the pattern already proven in `Entity.trace_sources`/`trace_derivatives` (`rmtc/track/store.py:236-278`) — i.e. `connection.sync([entity])` then `connection.queries.get_sources([entity])`/`get_derivatives([entity])`, falling back to `entity.properties` with `is_input()`/`is_output()` for anything not yet synced to the graph. This replaces the filesystem's dead-end stub with the query mechanism that already exists for entities, just exposed at the asset-manager level so callers don't need to know whether they're tracing an `Entity` or an on-disk `Artifact`.
   - `is_published(artifacts)`: query graph publish-state (e.g. a `published_at`/`REQUIRES_SYNC`-style flag or relationship on the `Entity` — reuse `Entity._requires_create`/timestamp machinery if a boolean property is added, see Considerations) rather than physical existence. Only call `self._reader_writer.exists([...])` as a defensive sanity check when the graph says "published" but the caller wants a hard guarantee the bytes are actually there — don't use file existence as the *source of truth* for publish state, since that's exactly what let bug #7 hide (a scalar/list mismatch went unnoticed because filesystem existence checks are rarely exercised in a way that would catch it).
   - `publish(artifacts)` / `unpublish(artifacts)`: for each artifact, delegate the actual byte write/delete to `self._reader_writer.write(...)`/equivalent, then record the publish-state transition against the graph entity. `unpublish` currently `raise NotImplementedError()` in `FilesystemManager` (line 112-113) — this is the right place to finally implement it, since unpublishing is fundamentally "flip provenance state in the graph, optionally also delete/retain bytes", not a filesystem concern.
   - `watermark(artifacts)`, pipeline registration (`add_pipeline`/`remove_pipeline`/`build`) move here from the old `ops.pipeline.AssetManager` (lines 144-165) — watermarking and builder pipelines are provenance-adjacent (they produce new tracked variants/derivatives), not raw I/O.
   - `allocate_version(path)` stays callable via the reader/writer (it's about filesystem folder/version numbering) but `ProvenanceAssetManager` is what decides *when* to bump a version (i.e. on publish), keeping the version-numbering mechanism in `ops` while the version-bump *decision* lives in `track`.

4. **Fix bug #7 as part of wiring the two sides together (0.5d):** `relocate()` (`filesystem.py:99-110`) calls `self.exists(uri)` and `self.is_published(uri)` with a scalar — both now live on different objects (`exists` on `FilesystemReaderWriter`, `is_published` on `ProvenanceAssetManager`), which forces the call site to be rewritten anyway. Rewrite `relocate` to take a list from the start: `reader_writer.relocate(artifact, uri)` should internally call `self.exists([uri])`, and any provenance-level relocate wrapper on `ProvenanceAssetManager` should call `self.is_published([artifact])`. Verify all call sites pass lists consistently now that the two concerns are physically separated — the split makes this bug impossible to reintroduce by accident, since `BaseReaderWriter.exists` and `BaseAssetManager.is_published` no longer share an implementation that could silently do the wrong thing for either scalar or list input.

5. **Update `CompoundAssetManager` (0.5d):** `src/python/lib/rmtc/core/ops/pipeline/asset_managers/utility.py`. This class currently picks among asset managers per-artifact and already refuses to `publish()` ("must use explicit manager to publish") — that instinct was correct and this split formalizes it. Rename/refactor to `CompoundReaderWriter(BaseReaderWriter)`, delegating `read`/`write`/`exists`/`resolve`/`relocate` per-artifact to whichever `FilesystemReaderWriter` (or other backend) `is_supported` picks. Drop `publish`/`unpublish`/`trace_sources`/`trace_derivatives`/`is_published` from this class entirely — a *compound* provenance manager doesn't make sense the way a compound reader/writer does, since provenance decisions (which graph, which publish policy) shouldn't be automatically inferred from which backend happens to hold the bytes. Note in passing: `_get_manager` is called but only `get_manager` is defined in the current file — fix this latent bug while touching the class.

6. **Update module registration (0.5d):** Edit `res/modules/rmtc_core.yaml` to register `FilesystemReaderWriter` and `ProvenanceAssetManager` as separate factory types. Keep a `FilesystemManager` alias/factory entry that auto-composes a `FilesystemReaderWriter` + a configured `ProvenanceAssetManager` (wired to whatever `Store`/`Connection` the environment specifies) for backward compatibility with existing YAML configs and call sites that expect one object with the old combined interface.

7. **Test round-trip (1.5d):** Create `tests/core/ops/pipeline/asset_manager_test.py` and `tests/core/track/asset_manager_test.py` covering:
   - `FilesystemReaderWriter` alone: rootless config accepts all `file://localhost` URIs (bug #6 fix), `relocate()` with list URIs only (bug #7 fix — scalar input should now be a caller error, not a silent bug).
   - `ProvenanceAssetManager.trace_sources`/`trace_derivatives` against a stub `Connection`/`Queries`, verifying it calls `get_sources`/`get_derivatives` rather than returning an empty set.
   - `ProvenanceAssetManager.publish`/`is_published`/`unpublish` round-trip against a stub graph connection + a real `FilesystemReaderWriter` for the byte side.
   - Swapping reader/writers under one `ProvenanceAssetManager` (e.g. a mock S3 reader/writer) to confirm the provenance layer has zero filesystem-specific assumptions leaking into it.

## Considerations

- **Where does "is published" actually live in the graph today?** Neither `Entity` (`rmtc/track/store.py`) nor the `Queries` ABC (`rmtc/track/store.py:765-903`) currently expose a publish-state flag or query — `get_entities`/`get_assets`/etc. don't filter or report on it. Step 3 assumes a property or relationship will need to be added to `Entity`/the graph schema (e.g. a `published_at: Datetime` property, following the same pattern as `Entity.timestamp`) — this is new graph schema, not just a code reshuffle, and should be scoped/estimated separately if the graph schema is considered frozen for this release.
- **Backward compatibility:** Keep a `FilesystemManager` factory alias that composes `FilesystemReaderWriter` + `ProvenanceAssetManager` so existing YAML-driven configs and call sites using the combined interface don't break immediately; plan a deprecation window before removing it.
- **Facility integration:** This split is what actually enables a facility to plug in a different reader/writer (e.g. Open Asset IO, S3) while keeping RMTC's own provenance/lineage logic — previously that facility would have had to reimplement `trace_sources`/`trace_derivatives`/`is_published` from scratch per backend, which is both duplicative and error-prone (as `FilesystemManager`'s stubs demonstrate).
- **`AssetManager.trace()` call site:** `rmtc/ops/pipeline.py:167-172` currently does `uris = [artifact.get_uri() for artifact in artifacts]` then calls `self.trace_sources(uris)` — once trace ownership moves to `ProvenanceAssetManager`, this needs to trace via artifacts/entities, not bare URIs, to match the `Entity.trace_sources(connection)` signature it should now be delegating to. Audit all callers of `.trace()` for this signature shift.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
