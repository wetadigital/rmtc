# Comprehensive ONNX Conversion with Packagers

## Feature Description

Extend ONNX model export and packaging support to handle the full range of RMTC packagers, currently only `ProcessPackager` and `BatchedTorchTensor` are supported (lines 44-48, `builders.py:33-49`). The feature also requires fixing bugs.md #17 (hardcoded `"cuda"` device, dead CPU branch at lines 111-113), and implementing the unimplemented ONNX IO/artifact methods in `core/ops/io/onnx/models.py` (lines 26, 50, 59) and `core/ops/artifacts/onnx/models.py` (lines 84, 93). This work completes the ONNX export path for mixed packager stacks, enabling real-world artifacts with heterogeneous input/output types to export to ONNX format.

## Criticality

High. ONNX is one of two headline supported model formats per README.md and `technical_notes.md` §"Artifacts"; limiting export to only specific packagers restricts adoption. Bug #17 blocks CPU-only export entirely, and unimplemented ONNX IO methods cause crashes if exercised outside the narrow happy path of `ONNXBuilder.__call__()`.

## T-Shirt Size

M. Requires: fixing the dead CPU branch (1-line fix + test), implementing 3 unimplemented methods in IO/artifact layers (each a straightforward stub or property delegation), designing a converter/adapter strategy for non-compatible packagers (1–2 new utility classes), and integrating into the existing builder loop. ~4-5 days including integration tests.

## How to Implement

1. **Fix bug #17:** In `src/python/lib/rmtc/core/ops/pipeline/onnx/builders.py:111-113`, replace the hardcoded string with proper device resolution:
   ```python
   device = "cuda" if artifact.device == Device.GPU else "cpu"
   torch_model.to(device)
   ```
   Add a test case that exports on CPU-only machines and verifies the model lands on CPU.

2. **Implement ONNX IO methods:** In `src/python/lib/rmtc/core/ops/io/onnx/models.py`, lines 26, 50, 59:
   - `ONNXSessionFile.create_name()` (line 26): return a name like `artifact.name + ".onnx"`.
   - `ONNXSessionFile.write()` (line 50): delegate to `ONNXModelFile.write()` or raise `NotImplementedError` with a clear message if write is deferred.
   - `ONNXModelFile.read()` (line 59): likely a typo in constructor; check if `self.device` is set (it's not in `__init__`; add it as a property or parameter).

3. **Implement ONNX artifact methods:** In `src/python/lib/rmtc/core/ops/artifacts/onnx/models.py`, lines 84, 93:
   - `create_weights()` (line 84): raise `NotImplementedError("ONNX models do not have separate weights")` or document as unsupported.
   - `move()` (line 93): implement as a no-op or raise `NotImplementedError("ONNX session movement not yet supported")`.

4. **Design packager converter:** In `src/python/lib/rmtc/core/ops/pipeline/onnx/builders.py`, lines 62–71 (the TODO comment on line 62):
   - Create a new helper function `_make_onnx_compatible_packager(packager)` that inspects the input packager type.
   - For unsupported types (e.g., `DictPackager`, custom packagers), wrap them in a `ProcessPackager` that converts the output back to the `[list, list, tuple]` format ONNX expects, or raise a clear error with a fallback suggestion.
   - Update the builder's `is_supported()` method to accept packagers beyond `ProcessPackager`/`BatchedTorchTensor` after conversion.

5. **Register ONNX builder:** Ensure `ONNXBuilder` is registered in `res/modules/rmtc_core.yaml` under a new `Builder` category if not already present (check existing code for builder registration pattern).

6. **Test matrix:**
   - Unit test on CPU-only machine exporting a simple PyTorch model to ONNX.
   - Integration test with mixed packagers (e.g., `Batch` + `ToDict`) exported to ONNX and re-imported.
   - Verify ONNX session loads correctly with the `ONNXSessionFile` reader.

## Considerations

- **Bug #17 dependency:** Fixing the dead CPU branch is a prerequisite and should be rolled into this feature's test coverage.
- **Critique.md line 48:** "only some packagers are ONNX-compatible; the rest aren't converted" — this feature removes that limitation by adding a conversion layer.
- **Scope out:** ONNX export to other hardware backends (ROCm, TensorRT, etc.) is future work; CPU and CUDA remain the target devices.
- **Existing TODO at line 30:** "build input and output shape from the ONNX description" — defer this to a follow-up refinement; this feature assumes the caller has correctly set `input_types`/`output_types`.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
