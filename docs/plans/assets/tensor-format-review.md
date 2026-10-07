# Tensor Format Review & Standardization

## Feature Description

Audit RMTC's internal tensor representations to verify they meet documented specifications, identify and fix existing shape/layout bugs, and establish a clear, enforced standard for all asset types. Currently, the Image asset claims WHC layout in `ops/assets.py:202` but does not confirm the actual layout is consistent; Camera intrinsics/translation properties exhibit clear correctness bugs (`Camera.aperture` corrupts the intrinsics matrix, `Camera.translation` has a malformed `tuple()` call per `bugs.md` #4/#5); and the stated intent to adopt "a Vulcan mappable structure" for meshes is unimplemented. This task consolidates format validation, fixes existing bugs in Camera tensor handling, and documents the precise memory layout each asset type must maintain.

## Criticality

High. Tensor format bugs silently corrupt calibration data and crash on property access, undermining asset integrity and downstream inference/training. The stated intent to enable future memory-mapping for performance depends on formats being well-defined and verified; leaving it unstandardized blocks that optimization path and allows new asset types to repeat the same mistakes.

## T-Shirt Size

M. This is primarily an audit-and-fix task: validating 3–4 asset types (Image, Mesh, Camera, Structure), fixing 2–3 concrete bugs in existing code (bugs.md #4/#5, plus the unconfirmed WHC layout in Image), adding shape-validation tests, and documenting the standard. No new modules or external dependencies; touches existing Asset subclasses in `ops/assets.py` and adds tests in `tests/`.

## How to Implement

**Phase 1: Document the Standard**
- In `docs/technical_notes.md`, expand the "Tensor Formats" section to explicitly specify:
  - Image: must be WHC (width, height, channels) RGBA, float32, derived from line 113 of `oiio/image.py` which does `np.transpose(..., (1, 0, 2))` to convert HWC→WHC on read.
  - Mesh: (N,8) vertices (x,y,z,nx,ny,nz,u,v as float32) + (M,3) faces (indices as int16), per `ops/assets.py:283–291`.
  - Camera: extrinsics as 4×4 homogenous transform (float32), intrinsics as 3×3 calibration matrix (float32).
  - Structure: placeholder, format TBD (currently stubbed per `ops/assets.py:361`).

**Phase 2: Fix Camera Property Bugs**
- In `src/python/lib/rmtc/ops/assets.py`, lines 414–423 (`aperture` setter): change `self.intrinsics[0] = value[0]; self.intrinsics[1] = value[1]` to `self.sensor[0] = value[0]; self.sensor[1] = value[1]` to match the getter (line 401).
- Lines 440–446 (`translation` getter): fix `tuple(self.extrinsics[0][3], ...)` to `tuple((self.extrinsics[0][3], self.extrinsics[1][3], self.extrinsics[2][3]))` (single iterable argument to `tuple()`).
- Add unit tests in `tests/core/` covering: setting `aperture`, reading `translation`, and confirming they round-trip without corruption of adjacent calibration properties (`focal_length`, `center`).

**Phase 3: Validate Image Layout**
- In `src/python/lib/rmtc/core/ops/io/oiio/image.py`, add a validation method or assert post-transpose that confirms `tensor.shape` matches `(W, H, C)` where C ≤ 4.
- Remove the TODO comment on `ops/assets.py:202`; confirm via test that read→write→read of an EXR yields byte-identical data (or at least pixel-identical after accounting for format coercion).

**Phase 4: Establish Shape Contract**
- Add a class method `expected_tensor_shape()` to each Asset subclass (Image, Mesh, Camera, etc.) returning a tuple of expected dimensions or a shape predicate.
- Call this in the Asset base class's `_validate_tensors()` method (add if missing) to fail fast on mismatched shapes.

## Considerations

- **Existing bugs:** This task includes fixing bugs.md #4/#5 (`Camera.aperture`/`translation`). Test these fixes against real camera workflows (e.g., the USD camera IO at `core/ops/io/usd/camera.py:85,91` which also has unimplemented tensor-loading).
- **Mesh Vulcan mapping:** The stated goal is a Vulkan-compatible layout; document whether the current (N,8) float32 vertex layout meets that requirement or if it needs refinement (e.g., padding, alignment). This is not a blocker for the review, but should be called out as out-of-scope if Vulkan integration is not ready.
- **Dependency on other formats:** If new asset types (point clouds, splats) are added in parallel, this review's standard should be applied to them on arrival, not retrofit later.
- **No deep-copy during validation:** Shape validation must not copy tensors; use `.shape` attribute only to keep memory-efficient.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
