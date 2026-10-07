# Environment Support – UV Specifically

## Feature Description

This design is fully detailed in `docs/plans/uv_envmanager.md`. This task is to implement a real, working UV-backed environment manager (`core/system/environment/uv/environments.py`, class `Uv(BaseEnvironmentManager)`) that installs Python packages into a dedicated directory and splices that directory onto `sys.path` immediately, making them importable in the current process without a restart. This is what allows `Factory.create()` to instantiate a class whose dependencies weren't previously installed, in the same call.

## Criticality

High. The Factory dependency-resolution system (`Factory._create_class()` in `system/__init__.py:1142-1159`) already calls `env_manager.add_packages()` when resolving classes with declared `dependencies`, but the current `PackageTracker` stub does nothing. A working environment manager is essential for any workflow where external packages (PyTorch, TensorFlow, custom libraries) must be dynamically available.

## T-Shirt Size

M. New `uv/environments.py` file (~200 lines), plus new `uv/__init__.py` (empty stub). Uses only standard library and subprocess (no new Python dependencies); requires `uv` CLI to be present on the system. Tests are straightforward (mock subprocess, assert `sys.path` is updated, verify `importlib.import_module()` finds installed packages). No changes to existing code except module YAML registration.

## How to Implement

See `docs/plans/uv_envmanager.md` for the full design, architecture, class shape, and verification steps. In brief:

- **New files**: `src/python/lib/rmtc/core/system/environment/uv/__init__.py` (empty), `src/python/lib/rmtc/core/system/environment/uv/environments.py` (contains `Uv` class with `add_packages()`, `remove_packages()`, `get_packages()`, `package_exists()`, `setup()`, `teardown()`, and private `_activate()` and `_run_uv()` helpers).
- **Class shape**: `Uv(BaseEnvironmentManager)` tracks environments in `_env_dirs` and ref-counts packages in `_package_refs`. Uses `uv pip install --target` and `importlib.invalidate_caches()` to splice packages into the current process.
- **Registration**: Add to `res/modules/rmtc_core.yaml` (already done, entry at line 367-370):
  ```yaml
  EnvManager:
    UV:
      version: 1.0.0
      class_path: rmtc.core.system.environment.uv.UV
  ```
- **Tests**: verify `add_packages()` makes packages importable in-process, ref-counting works, `setup()`/`teardown()` round-trip, and failure paths (missing `uv` binary) return `False` gracefully.

See `docs/plans/uv_envmanager.md` for details.

## Considerations

- **No venv creation**: Uses `uv pip install --target` (flat directory), not full virtualenvs, for simplicity.
- **Subprocess safety**: `uv` is invoked as an external CLI, not as a library dependency.
- **Not in scope**: Pre-existing `Pip` stub's broken import bug (`rmtc.environment` → should be `rmtc.system.environment`); noted in `uv_envmanager.md` as explicitly deferred.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
