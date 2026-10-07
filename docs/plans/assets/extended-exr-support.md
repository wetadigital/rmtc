# Extended EXR Support — Multi-Subimage & Arbitrary Channels

## Feature Description

Extend RMTC's OIIO-backed EXR IO to support reading/writing multi-part EXR files (multiple subimages), arbitrary channel counts (not just hardcoded RGBA), and optional deep EXR support. Currently, `core/ops/io/oiio/image.py` only reads and writes the first subimage unconditionally (lines 87, 131 per `critique.md`), and always assumes 4-channel RGBA output (line 100), forcibly converting 1-channel or 3-channel images by padding or triplicating channels. This blocks workflows requiring layered EXR or custom channel sets, common in VFX asset pipelines.

## Criticality

High. Multi-layer EXR is a standard in VFX pipelines; inability to preserve layer structure forces artists to split/rejoin files manually, losing metadata and complicating provenance. Arbitrary-channel support unblocks use of custom AOV (arbitrary output variable) layers. This is not blocking core inference (single-image workflows work), but is a major gap for production asset management.

## T-Shirt Size

L. This requires refactoring the read/write path to iterate over multiple subimages, parameterizing channel handling, adding subimage metadata tracking to the Image asset (or creating a new multi-layer asset type), comprehensive tests for multi-layer round-trip, and optional deep-EXR support (potentially XL if included). Does not need new external dependencies beyond OIIO (already a hard dependency).

## How to Implement

**Phase 1: Parameterize Single-Subimage Read/Write**
- Modify `src/python/lib/rmtc/core/ops/io/oiio/image.py` signature: instead of `read(uri, artifact)` which reads a single subimage, add an optional `subimage_index` parameter (default 0 for backward compat).
- Update line 87–88 to accept a specific subimage index rather than always selecting index 0.
- Likewise, update `write()` (line 120ff) to accept a `subimage_index` parameter to write to a specific layer slot.
- Remove the hardcoded RGBA assumption (line 100): instead of unconditionally adding/trimming channels, preserve the channel count as-is and store it in the Image asset's `channels` property.

**Phase 2: Multi-Subimage Support (Greenfield)**
- Design a new container type or extend Image to hold multiple tensors with metadata:
  - Option A: Create a new `MultiLayerImage` asset type in `ops/assets.py` holding a list of (name, tensor, channels, colorspace, data_type) tuples.
  - Option B: Extend Image to hold multiple tensors in `self.tensors` (currently assumes a single-element tuple) plus a `layer_names` property listing subimage names.
  - Recommended: Option B for simpler backward compat (existing code reading `self.tensors[0]` still works; new code can iterate over all layers).
- Add class methods to Image: `add_layer(name, tensor)`, `layer_count()`, `get_layer_by_name(name)`.
- Register the extended Image in `res/modules/rmtc_core.yaml` with a version bump (e.g., `Image: {version: 2.0.0}`) if backward-incompatible, or use the existing Image entry if the tensors tuple can be transparent.

**Phase 3: IO Refactor**
- In `oiio/image.py`, add a new method `read_all_subimages(uri, artifact)` that:
  - Loops over all subimages in the EXR (use OIIO's subimage iteration API).
  - For each, reads the tensor, stores name/channels/colorspace/data_type in metadata.
  - Calls `artifact.add_layer(...)` for each (or appends to a list).
- Existing `read(uri, artifact)` continues to read only the first subimage (default behavior, no breaking change).
- Add `write_all_subimages(uri, artifact)` to write all layers back to a multi-part EXR.

**Phase 4: Deep EXR (Optional / Out of Scope)**
- Deep EXR support (depth + coverage per pixel, variable samples per pixel) is a larger lift: requires a different tensor structure (not rectangular), different OIIO API calls, and new Asset subclass(es).
- **Flag this as a separate, future task.** Include a stub in the design doc noting deep EXR is out of scope for this phase but the layering foundation enables it.

**Phase 5: Tests**
- Add `tests/core/ops/io/oiio/test_multipart_exr.py`:
  - Write a multi-layer test EXR (3 subimages, varied channel counts: 1, 3, 4).
  - Call `read_all_subimages()`; assert all layers are loaded with correct names/shapes/colorspaces.
  - Call `write_all_subimages()` to a new file; read it back and confirm byte-identical layer structure.
  - Backward-compat test: call old `read(uri, artifact)` on a multi-layer EXR, confirm it reads only subimage 0.

## Considerations

- **Backward compatibility:** Existing code calling `read(uri, artifact)` expects a single Image with one tensor. Preserve this by keeping the default behavior (read first subimage only). New code can explicitly opt into `read_all_subimages()`.
- **Metadata retention:** OIIO provides subimage names via `spec.attribute(OIIO_SUBIMAGE_NAME_ATTR)`. Store these so round-tripping preserves layer identity.
- **Deep EXR:** Explicitly defer to a separate task; note the limitation in docstrings to avoid user confusion.
- **Channel count flexibility:** Once arbitrary channels are supported, the comment on line 100 in `image.py` ("TODO: Do we always enforce a 4 channel image?") can be resolved: answer is "no, preserve what the file has."
- **Dependency on tensor-format-review:** This task assumes Image tensor format (WHC) is finalized by the tensor-format-review task.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
