# Provenance Watermarking Support

## Feature Description

Embed traceable, tamper-evident provenance markers directly into asset data (e.g. C2PA
content-credential manifests baked into EXR/image data), so an asset's provenance survives once
it leaves RMTC's own tracking graph — exported to a client, uploaded, or consumed outside the
tracked toolchain. Today the *shape* for this exists but the *behaviour* does not: `Watermark`
(`src/python/lib/rmtc/track/entities.py:1084-1116`) is a fully-implemented metadata container
(dynamic POD entries via `add_entry()`, tracked in `entry_names`), and `Asset.watermarks`
(`entities.py:1159`) already exposes an `OUT`-directed array of them. `AssetManager` already has
a `Watermarker` plugin interface and registration hooks
(`src/python/lib/rmtc/track/asset_manager.py:103-149` — `add_watermarker()`, `watermark()`), and
there is one concrete implementation stub, `C2PAImageWatermarker`
(`src/python/lib/rmtc/core/ops/pipeline/c2pa/watermarker.py`) — but it is an empty `pass`, has a
broken import (`from rmtc.ops.pipeline import Watermarker`, which is not the interface's actual
module path — the real `Watermarker` ABC lives in `rmtc.track.asset_manager`, so this file cannot
currently even import successfully), and does none of the three things its own comments describe:
build a C2PA manifest, run a crypto signer, or embed the result into image data.

## Criticality

**High** — provenance is RMTC's core value proposition, but right now that provenance only
exists *inside* RMTC's graph store. The moment an asset is exported, published to a DCC, or
handed to a downstream consumer, nothing travels with the pixels themselves — there is no way to
answer "where did this specific file come from" without a live connection back to the RMTC store
that produced it. Embedded watermarking is what makes provenance durable outside the tool, which
several of the roadmap's other provenance/compliance features (license guardrails,
`stronger-inference-training-guardrails.md`) implicitly assume is possible.

## T-Shirt Size

**M-L** — the scaffolding already exists (`Watermark` entity, `Watermarker` ABC, `AssetManager`
registration hooks), which is most of the plumbing. The remaining work is concentrated in: (1)
fixing the broken import so the existing stub can load at all, (2) implementing one real,
end-to-end watermarker (C2PA manifest generation + crypto signing + pixel/metadata embedding) for
RMTC's native asset format, and (3) two small existing bugs in `AssetManager` that would break
watermarking even once a real implementation exists (see Considerations). No new architectural
abstractions are needed — this is filling in an interface that's already been designed.

## How to Implement

1. **Fix the import in `C2PAImageWatermarker`.** `core/ops/pipeline/c2pa/watermarker.py:4`
   imports `Watermarker` from `rmtc.ops.pipeline`, which does not match where the class is
   actually defined (`rmtc.track.asset_manager.Watermarker`). This must be corrected before
   anything else in this file can run.

2. **Implement the C2PA manifest step.** Build a manifest describing the asset's provenance —
   sourced from the `Artifact`'s existing tracked fields (`ancestors`, `origin`, `author`,
   `licenses`, `version` — `entities.py:679-758`) rather than inventing a parallel provenance
   representation. This keeps the watermark manifest as a *projection* of data RMTC already
   tracks, not a second source of truth.

3. **Implement crypto signing.** Sign the manifest so tampering is detectable — this needs a
   pluggable signing backend (local keypair for dev/test, HSM/KMS-backed for production), which
   should be scoped as its own small interface rather than hardcoded, since production signing
   key custody is an infra decision each facility will make differently. Coordinate with
   `security/credential-management.md` if the signing key itself needs secret storage.

4. **Implement embedding for one format first.** RMTC's own comment in the stub
   ("IO will embed in EXR etc.") already identifies the intended integration point — RMTC's
   `core/ops/io/torch` and image IO layers (see `docs/structure/modules.md`'s IO section) are
   where format-specific embedding belongs, not inside the watermarker itself. The watermarker
   should produce a manifest payload and hand it to the existing IO layer to embed as an EXR
   attribute/metadata block; scope the first implementation to EXR only, since that's RMTC's
   VFX-native format, and treat other formats as follow-on work.

5. **Wire the `Watermark` entity to the embedded result.** After embedding, populate a
   `Watermark` entity (via `add_entry()`) with the manifest's key fields (signer, timestamp,
   content hash) and attach it to the asset's `watermarks` property
   (`entities.py:1159`), so the embedded watermark's contents are also queryable through the
   normal tracking graph without needing to re-read the asset file.

6. **Tests:** a round-trip test (embed → re-read the file → recover the same manifest fields),
   a tamper test (mutate the asset after embedding, confirm signature verification fails), and a
   unit test for the `AssetManager.watermark()` fix in Considerations below.

## Considerations

- **Two existing bugs block this even with a correct watermarker implementation:**
  `AssetManager.watermark()` (`asset_manager.py:146-149`) iterates `self._watermarkers`, which is
  a dict keyed by watermarker name (`asset_manager.py:132,141`) — iterating a dict yields its
  *keys* (strings), so `watermarker(entity)` currently calls a string, not a registered
  `Watermarker` instance; it should iterate `self._watermarkers.values()`. Similarly
  `remove_watermarker()` (`asset_manager.py:143-144`) calls `.remove()` on a dict, which dicts
  don't support — it should be `del self._watermarkers[watermarker.name]`. Both should be fixed
  as part of this work, not left for `address-cataloged-bugs.md` to pick up separately, since
  they sit directly in this feature's critical path.
- **Open design question:** should the signing-backend interface support multiple concurrent
  watermarking schemes (C2PA plus a facility-proprietary scheme) simultaneously on the same
  asset? The `Watermarker` ABC and `add_watermarker()`/`watermark()` already support registering
  multiple watermarkers, so this is more a policy question (what runs by default) than an
  architecture question.
- **Risk:** embedded watermarks can be stripped by any tool that resaves the asset without
  preserving the metadata block (a plain re-export from a DCC, for instance) — this feature makes
  provenance *more* durable, not tamper-proof against a determined bad actor; that expectation
  should be explicit in any user-facing documentation of this feature.
- **Out of scope:** watermarking non-image assets (audio, video, 3D geometry, point clouds) —
  scope the first pass to image/EXR only and treat other formats as separately-sized follow-ons.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
