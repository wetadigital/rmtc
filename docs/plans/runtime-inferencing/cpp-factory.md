# C++ Factory to Create Equivalent Classes to Python

## Feature Description

Implement a C++ factory that mirrors RMTC's Python `Factory` class (`src/python/lib/rmtc/system/__init__.py` lines 1058–1300+), capable of resolving type names (e.g., `"rmtc_core.Process.LinearToSRGB-1.0.0"`) to C++ Process class instances. This factory is greenfield; today type resolution happens in Python only. The C++ factory will enable DCCs and real-time systems to directly instantiate C++ processes by type name (from config or YAML), bypassing Python instantiation entirely for performance-critical paths.

## Criticality

Medium. Without this factory, DCC code must hard-code C++ process types (e.g., `new LinearToSRGB()`), losing the pluggability/configuration system that makes RMTC's Factory valuable. However, if DCCs use the Python binding layer (file 3) exclusively, this can be deferred or implemented later. Use this only if C++ code must directly read module YAML and instantiate types.

## T-Shirt Size

M. Requires: parsing/loading module YAML in C++, a type-name → class-pointer map, and factory methods for each Process type. No external serialization format (YAML parsing) library is currently vendored; decide on a lightweight YAML parser (e.g., `ryml` or hand-parse a simplified YAML subset). ~3–4 days including tests and YAML parsing.

## How to Implement

**Greenfield C++ factory; mirrors Python Factory contract.**

1. **Define C++ factory interface (`src/cpp/rmtc/system/factory.h`):**
   ```cpp
   class Process;
   
   class Factory {
   public:
       // Resolve type name to a Process instance
       // e.g., "rmtc_core.Process.LinearToSRGB-1.0.0" 
       // or version-less "rmtc_core.Process.LinearToSRGB"
       static std::unique_ptr<Process> create(
           const std::string& type_name,
           const std::map<std::string, std::string>& params = {}
       );
   
       // Load module definitions from YAML file path
       static void load_modules(const std::string& yaml_path);
   
       // Query registered types
       static std::vector<std::string> registered_types(
           const std::string& category = ""
       );
   };
   ```

2. **Implement module YAML loading:**
   - Use a lightweight YAML parser (recommend `ryml` for speed, or hand-parse RMTC's simple subset: top-level category → type name → version/description/class_path).
   - Store parsed modules in a static map: `std::map<std::string, std::map<std::string, std::string>> _modules`.
   - Load from `RMTC_MODULES` env var path, mirroring Python `Factory.load_modules()` behavior (line 1211).

3. **Implement type resolution (`src/cpp/rmtc/system/factory.cpp`):**
   - Parse type name into components: module, category, name, version.
   - Look up in `_modules` map: resolve version-less names to latest version (same logic as Python, line 1239).
   - Build a class-path string; map to a registered C++ constructor function.
   - Return a `std::unique_ptr<Process>` pointing to the instantiated subclass.
   - If type not found, throw a clear exception (mirror Python's `RMTCException`).

4. **Register C++ process classes:**
   - In the same file, define a static registry:
   ```cpp
   namespace {
       std::map<std::string, std::function<std::unique_ptr<Process>()>> 
           _class_registry = {
               {"rmtc.core.ops.process.image.channels.MoveChannelsFirst", 
                []() { return std::make_unique<MoveChannelsFirst>(); }},
               {"rmtc.core.ops.process.image.color.LinearToSRGB", 
                []() { return std::make_unique<LinearToSRGB>(); }},
               // ... one entry per Process type
           };
   }
   ```
   - Use lazy registration via static initializers if classes are defined in separate headers.

5. **Parameter binding:**
   - Accept optional `params` dict to `create()` for process configuration (e.g., channel indices for `ExtractChannel`).
   - Pass params to the Process constructor if needed; document which params each type accepts (reference Python implementations in `core/ops/process/`).

6. **Integrate with module YAML:**
   - Ensure the existing `res/modules/rmtc_core.yaml` Process entries already include `class_path` (they do; verified in lines 94–149).
   - C++ factory reads the same YAML at runtime; no duplication needed.

7. **Test matrix:**
   - Unit test: Load `res/modules/rmtc_core.yaml`, call `Factory::create("rmtc_core.Process.LinearToSRGB-1.0.0")`, verify returned object is usable.
   - Version fallback: Query "rmtc_core.Process.LinearToSRGB" (no version), verify it returns the latest registered version.
   - Unregistered type: Verify clear error message, not a crash.
   - Round-trip: Create via factory, execute `run()` → `run_inverse()`, verify correctness matches direct instantiation.

## Considerations

- **YAML parser choice:** Hand-parsing RMTC's YAML subset (just categories and class_path lines) is simpler than vendoring a full YAML library; reserve full parsing for future features (configs, etc.).
- **Dependency on file 2:** Requires C++ Process implementations from `realtime-cpp-tensor-conversion.md`.
- **Type-name format:** Strictly follow `"module.category.name-version"` per `technical_notes.md` § "Factory, Type Names & Resolution" (lines 169–200). No invented shortcuts.
- **Error recovery:** If YAML loading fails, should the factory gracefully degrade to hard-coded types, or fail loudly? Recommend loud failure to catch config errors early.
- **Thread safety:** Static `_modules` map can be read concurrently; use a mutex if DCC creates processes from multiple threads.
- **Deferred parameter binding:** If a process type has complex constructor params (not just scalars), defer full implementation; document as "scalar params only" for now and revisit with a params schema.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
