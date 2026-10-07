# Realtime C++ Tensor Conversion

## Feature Description

Implement a high-performance C++ tensor conversion layer mirroring the semantics of RMTC's Python `Process`/`ProcessStack`/`ProcessInverse` classes (`src/python/lib/rmtc/ops/process.py` lines 157–200+, full definition in `src/python/lib/rmtc/core/ops/process/`). This is greenfield C++ code targeting real-time DCC inference (e.g., Nuke, Houdini) where Python-based tensor marshalling is a bottleneck. The target format is HWC RGBA (1HWC) per `technical_notes.md` § "Tensor Formats" and "A Note on Performance"; channels-last is intentional for memory-mapping compatibility with DCC native formats and faster inference than CHW. Process and ProcessStack must support both `run()` (forward) and `run_inverse()` (reverse) transformations in lockstep.

## Criticality

Medium. Currently, all tensor conversion happens in Python; real-time DCC integration (lines 587–591 of `technical_notes.md`) requires low-latency transforms. This doesn't block current inference/training workflows but is a prerequisite for production DCC support. Can be deferred to a future release if no real-time DCC plugin exists yet.

## T-Shirt Size

L. Requires: designing a C++ Process base class, implementing 6–10 core process types (Channel, Color, Structure, Augment, Transform per `docs/review/critique.md` § "Processors"), writing bidirectional `run()`/`run_inverse()` for each, and extensive testing on mixed tensor shapes. ~8–10 days including architecture review and test coverage (no Python dependency, pure C++).

## How to Implement

**Greenfield C++ module; no existing C++ code in this repo to extend.**

1. **Create directory structure:**
   ```
   src/cpp/
   ├── rmtc/
   │   └── process/
   │       ├── base/
   │       │   ├── process.h
   │       │   ├── process_stack.h
   │       │   └── tensor.h
   │       ├── image/
   │       │   ├── channels.h/channels.cpp
   │       │   ├── color.h/color.cpp
   │       │   └── transform.h/transform.cpp
   │       └── CMakeLists.txt
   ```

2. **Define core abstractions (`src/cpp/rmtc/process/base/process.h`):**
   - `class Tensor`: wraps shape (H, W, C), dtype, memory buffer — mirrors RMTC's internal tensor layout.
   - `class Process` (abstract base): defines `run(const Tensor&) → Tensor` and `run_inverse(const Tensor&) → Tensor`.
   - `class ProcessStack`: chains Process instances, applies forward/inverse in order/reverse-order, validates shape contracts at each step.
   - Tensor shape validation at pipeline entry/exit (per `technical_notes.md`, "Processors" section).

3. **Implement core process types:**
   - `MoveChannelsFirst` / `MoveChannelsLast`: transpose HWC ↔ CHW.
   - `ExtractChannel` / `AddChannel`: reduce/expand channel count (reference `core/ops/process/image/channels.py` for semantics).
   - `LinearToSRGB` / `SRGBToLinear`: color-space transforms (reference `core/ops/process/image/color.py`).
   - `Batch` / `Unbatch`: collate/uncollate single-tensor lists (reference `core/ops/process/tensor/structure.py`).
   - `Normalize` / `Denormalize`: stats-based color normalization.
   - Each must define both `run()` and a true `run_inverse()` (not a fabrication like bug #13 in `technical_notes.md` critique — document lossy operations clearly).

4. **Integrate with CMake:**
   - Update `cmake/CMakeLists.txt` to add a new `add_library(rmtc_process_cpp ...)` target (today it only installs Python files; this adds the first real compile step).
   - Link against a vendored or system-provided linear-algebra library (Eigen, glm, or manual SIMD for transforms).
   - Install `.h` files to a public include directory so the Python bindings (file 3) can link against it.

5. **Test matrix:**
   - Unit tests for each process type with fixed input/output shapes (HWC → CHW, etc.).
   - Round-trip tests: `run()` → `run_inverse()` → verify shape/data match (catch non-invertible operations).
   - Performance benchmark: measure latency on typical DCC tensor sizes (1920×1080×4, batches of 1–4).

## Considerations

- **Performance target:** 30 FPS on 1920×1080 batch-1 is ~33ms per frame; aim for <1ms tensor conversion (C++ overhead should be <3% of frame budget).
- **Memory model:** Use stack allocation for small tensors, pooled allocation for large ones (avoid allocator contention in frame-real-time loops).
- **Alignment:** HWC RGBA layout means channels are interleaved; SIMD kernels must respect 4-element strides.
- **Technical_notes dependency:** "A Note on Performance" section explicitly motivates HWC; honor that design in both layout and choice of operations (no unexpected transposes).
- **Future DCC bindings:** This C++ code is a building block for file 3 (C++ wrapper); do not optimize for Python API surface here, just the raw tensor contract.
- **Out of scope:** GPU acceleration (CUDA kernels) — target CPU SIMD initially; GPU can be a follow-up.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
