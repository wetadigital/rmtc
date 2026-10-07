# Splats, PLY & Point-Cloud Support

## Feature Description

Add greenfield support for point-cloud assets to RMTC, including PLY (Polygon File Format) and splat (3D Gaussian splatting) representations. Currently, RMTC has Image, Mesh, and Camera asset types; there is no Point Cloud or PLY IO anywhere in `src/python/lib/rmtc/core/ops/io/` or `core/ops/artifacts/`. This feature adds a new asset class, IO handlers for PLY and splat formats, and a Processor-compatible tensor representation that integrates with the training/inference pipeline.

## Criticality

Medium. Point clouds and splat representations are emerging as important for 3D reconstruction and novel-view synthesis workloads, especially in VFX for motion capture and 3D generative models. However, there are no current models/solutions in RMTC using them, so this is a capability unlock rather than a blocker. Adding it early prevents the pattern of "bolt-on after the fact" that has created format inconsistencies elsewhere.

## T-Shirt Size

XL. This is a complete greenfield addition: new asset class (PointCloud / Splat in `ops/assets.py`), new IO modules (`core/ops/io/ply/`, `core/ops/io/splat/`), new artifact wrappers in `core/ops/artifacts/`, registration in `res/modules/rmtc_core.yaml`, definition of tensor format per "Tensor Formats" section of `technical_notes.md`, Processor chain to convert to/from model formats, plus comprehensive tests. Requires a design decision on tensor layout and coordinate system. No new external dependencies if using existing NumPy/libraries; PLY can use Python's built-in `struct` module or a lightweight parser; splatting support likely needs `plyfile` or similar (one additional dep).

## How to Implement

**Phase 0: Define Tensor Format (Prerequisite)**
- In `docs/technical_notes.md` "Tensor Formats" section, define PointCloud tensor layout:
  - Recommended: **(N, 3+K)** where N = number of points, first 3 columns are [x, y, z] positions (float32), remaining K columns are feature dimensions (normals, colors, radii, SH coefficients for splats, etc., float32).
  - For splats specifically: (N, 3+3+4+16) = (N, 26): [x,y,z, scale_x/y/z, rotation_quat, SH_coefficients] per standard Gaussian splatting (compute all 48 SH coefficients and store first 16, or store full 48 in extended format).
  - Document the coordinate system (e.g., OpenGL-style Y-up or Y-down) to prevent silent incompatibilities with DCC tools.

**Phase 1: Create PointCloud Asset Class (Pattern: Mesh)**
- In `src/python/lib/rmtc/ops/assets.py`, add:
  ```python
  class PointCloud(Asset):
      """N-dimensional point cloud with optional features."""
      def __init__(self, name=None, context=None, uri=URI(), io=None, ...):
          super().__init__(...)
          # store feature_names (list of strings: ["position", "normal", "color", ...])
          self.add_property("feature_names", [str], ...)
          
      @property
      def point_count(self):
          return self.tensors[0].shape[0]
      
      def structure(self):
          # return schema describing N, feature dimensions, data types
          return ...
  ```
  - Similar pattern to `Mesh` (lines 274–339): store vertex/point data in tensors, expose counts/accessors.

**Phase 2: Create IO for PLY**
- New directory: `src/python/lib/rmtc/core/ops/io/ply/`
  - `__init__.py` (empty, mirrors sibling convention).
  - `pointclouds.py` with `class PLYPointCloudIO(BaseIO)`:
    - `read(uri, artifact)`: parse PLY header, extract vertex/point data, populate `artifact.tensors = (numpy_array,)`, store feature names from PLY header.
    - `write(uri, artifact)`: write tensor back to PLY format, preserving feature names in header comments or property annotations.
    - Use Python's `struct` module or `plyfile` library to parse/write PLY (recommend `plyfile` for correctness if it's a lightweight dep, else hand-parse).
  - Handle both ASCII and binary PLY formats for reading; write ASCII or binary per a config option.

**Phase 3: Create IO for Splatting (Greenfield)**
- New directory: `src/python/lib/rmtc/core/ops/io/splat/`
  - `__init__.py` (empty).
  - `models.py` with `class SplatIO(BaseIO)`:
    - `read(uri, artifact)`: read from `.splat` or `.ply` (splatting often stored as PLY with SH coefficients in properties).
    - `write(uri, artifact)`: write Gaussian parameters in a standard format (`.splat` or splatting-optimized PLY).
    - Document the tensor layout expected (N, 26 per Phase 0 spec, or N, 48 for full SH).

**Phase 4: Create Artifact Wrappers**
- New directory: `src/python/lib/rmtc/core/ops/artifacts/pointcloud/` (or `splat/`).
  - `__init__.py` (empty).
  - `models.py` with `class SplatModel(Artifact)` or similar, wrapping the IO and adding any domain-specific methods.
  - Register in `res/modules/rmtc_core.yaml` under a new category (or extend `Model`):
    ```yaml
    PointCloud:  # or embed in Artifact category
      SplatModel:
        version:      1.0.0
        description:  3D Gaussian Splat
        class_path:   rmtc.core.ops.artifacts.pointcloud.models.SplatModel
      PLYPointCloud:
        version:      1.0.0
        description:  PLY Point Cloud
        class_path:   rmtc.core.ops.artifacts.pointcloud.models.PLYPointCloud
    ```

**Phase 5: Processors for Model Conversion**
- Add Processors in `src/python/lib/rmtc/core/ops/process/pointcloud/` (new directory):
  - `format_conversion.py` with:
    - `ReshapeForModel`: convert (N, 26) tensor to model-expected format (e.g., separate tensors for position, rotation, scale if the model wants that).
    - `NormalizePositions`: center/scale point cloud to [-1, 1] or similar.
  - Register these in `rmtc_core.yaml` under `Process:`.

**Phase 6: Tests**
- New test file: `tests/core/ops/io/ply/test_ply_io.py`
  - Create a small test point cloud (10 points, 3+3 dims: position + normal).
  - Write to PLY, read back, assert tensor matches.
  - Test both ASCII and binary formats.
- `tests/core/ops/io/splat/test_splat_io.py` (once splat format is decided):
  - Write a tiny splat cloud (3 Gaussians), round-trip, verify SH coefficients preserved.

## Considerations

- **Coordinate system alignment:** Point clouds from different tools (e.g., COLMAP, NeRF outputs) may use different coordinate conventions (Y-up vs Y-down, left-handed vs right-handed). Document the RMTC canonical choice and provide a Processor to convert if needed.
- **No existing splat format standard:** ".splat" binary format exists but is not universally standardized. Starting with PLY as the canonical interchange format and supporting ".splat" as an export option is safer than committing to ".splat" format first.
- **Dependency on tensor-format-review:** This task should *start* with Phase 0 (format definition) but *cannot complete* until the tensor-format-review task has finalized the standard approach (so PointCloud fits the pattern).
- **Out of scope:** Splat rendering/visualization (that's a frontend/GUI concern). Point-cloud segmentation, sampling, or upsampling Processors are deferred.
- **Performance note:** N-point clouds can be large (millions of points); validate that NumPy tensor representation is memory-efficient for at least N up to 10M.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
