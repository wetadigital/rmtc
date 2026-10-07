# C++ Wrapper with Python Exposure

## Feature Description

Expose the C++ tensor-conversion classes from file 2 (`realtime-cpp-tensor-conversion.md`) to Python via pybind11 (or cffi as alternative), making the high-performance C++ `Process`/`ProcessStack` implementations drop-in substitutes for their Python counterparts in DCC/real-time workflows. This is greenfield; today all Process instantiation is Python-only. The binding layer will allow `rmtc.core.ops.process` to lazily instantiate C++ processes when performance is critical, while keeping the Python fallback for development and testing.

## Criticality

Medium-High. Required to realize the performance gains of file 2 in production DCC integration. Without this binding layer, the C++ code is inert. However, the feature can be deferred if DCC real-time support is not a near-term roadmap item.

## T-Shirt Size

M. Requires: pybind11 integration, ~15–20 wrapper classes (one per Process type), parameter marshalling (shape, dtype, device), error-translation layer, and end-to-end tests calling from Python. CMake already has install targets; a compile step must be added for the first time. ~4–5 days including CI integration.

## How to Implement

**Greenfield pybind11 bindings; no existing C++ extension code in this repo.**

1. **Update CMake to compile C++ extension:**
   - In `cmake/CMakeLists.txt` (currently lines 1–59 install only), add a new section after line 59:
   ```cmake
   # Find Python and pybind11
   find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
   find_package(pybind11 REQUIRED)
   
   # Compile C++ extension
   add_library(rmtc_process_cpp SHARED src/cpp/rmtc/process/base/process.cpp ...)
   target_include_directories(rmtc_process_cpp PRIVATE src/cpp)
   
   pybind11_add_module(rmtc_cpp_process src/cpp/python/bindings.cpp)
   target_link_libraries(rmtc_cpp_process PRIVATE rmtc_process_cpp)
   
   install(TARGETS rmtc_cpp_process
       LIBRARY DESTINATION ${PYTHON_LIB_INSTALL_DIR}/rmtc/core/ops/process/_cpp)
   ```
   - Note: This is the first real C++ compile in the repo; the build system scaffold (cmake/) exists but will need actual compiler targets.

2. **Create pybind11 binding module (`src/cpp/python/bindings.cpp`):**
   - Define a Python module `rmtc._cpp_process` exposing:
     - `Tensor` class with shape, dtype, buffer access (NumPy array conversion).
     - `Process` base class and all subclasses (`MoveChannelsFirst`, `LinearToSRGB`, etc.) with `run()` and `run_inverse()`.
     - `ProcessStack` chaining and error propagation.
   - Example snippet:
   ```cpp
   pybind11::class_<Process>(m, "Process")
       .def("run", &Process::run, "Forward pass")
       .def("run_inverse", &Process::run_inverse, "Inverse pass");
   ```

3. **Create Python import layer (`src/python/lib/rmtc/core/ops/process/_wrapper.py`):**
   - Try-except block to import the C++ extension; fall back to pure-Python if unavailable.
   ```python
   try:
       from rmtc._cpp_process import Process as _CppProcess
       _use_cpp = True
   except ImportError:
       _use_cpp = False
   ```
   - Expose a factory function `new_process(typename, **kwargs)` that returns a C++ instance if available, else Python.
   - Update existing `__init__.py` to expose this factory so users (and DCC plugins) can opt into C++ via a flag or config.

4. **Update module registration in `res/modules/rmtc_core.yaml`:**
   - Optionally add a `use_cpp` flag to each Process entry, or create a new category `Process_CPP` for C++ variants.
   - Keep Python Process entries intact for backward compatibility.

5. **Test matrix:**
   - Unit test: Compare C++ and Python `run()` output on identical input; assert near-equality (allow 1e-6 float tolerance).
   - Round-trip: `run()` → `run_inverse()` on both C++ and Python; compare results.
   - Performance regression: Ensure C++ is faster than Python on typical DCC sizes; log and alert if C++ is slower (possible due to marshalling overhead).
   - Integration: Load a Nuke/DCC model with C++ Process stack; verify inference is correct and faster.

## Considerations

- **Dependency on file 2:** Requires `src/cpp/rmtc/process/` implementation from `realtime-cpp-tensor-conversion.md` to be complete.
- **pybind11 vendoring:** Decide whether to vendor pybind11 (in `src/cpp/third_party/`) or require it as a build dependency. Vendoring is simpler for CI.
- **Device parameter:** C++ `Process` will initially target CPU only; GPU (CUDA) support is future work, so do not expose a device parameter yet.
- **NumPy interop:** Use pybind11's NumPy support (`pybind11::array_t<float>`) for zero-copy tensor passing where possible.
- **Error handling:** C++ exceptions must be caught and re-raised as Python exceptions with clear messages (not raw C++ stack traces).
- **ABI stability:** C++ Process ABI is internal; use opaque pointers (`std::unique_ptr<Process>`) to allow internal refactoring without breaking Python consumers.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
