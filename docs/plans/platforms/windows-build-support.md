# Windows Build Support

## Feature Description

Add native Windows build support to RMTC, including CMake configuration for Windows, environment-setup scripts (`.bat`/`.ps1` equivalents), and remediation of POSIX-specific path handling and subprocess invocations in the Python codebase. Currently, the project is Linux/macOS-only by build: `cmake/CMakeLists.txt` (the entire build system) installs Python files and resources with no Windows paths, and both `cmake/rmtc-setup.bash.in` and `cmake/rmtc-setup.csh.in` are shell-only (no `.bat` or PowerShell counterpart). At the Python level, POSIX assumptions include hardcoded `:` path separators for `$PATH` and `$PYTHONPATH` parsing in `src/python/lib/rmtc/gui/common/__init__.py` and `src/python/lib/rmtc/system/__init__.py`, and subprocess invocations (e.g., `uv`, Nuke builders) that assume POSIX shell syntax.

## Criticality

High. Windows is a primary workstation OS in VFX studios; without support, the tool is not deployable in mixed environments or studios that standardize on Windows. This is a blocking constraint for any facility adoption claim.

## T-Shirt Size

L. Requires: (1) CMake Windows-specific generator and path handling (~1–2 days), (2) Windows setup scripts in CMD/PowerShell (~1 day), (3) cross-platform path refactoring across 3–4 modules in `src/python/lib/rmtc/` (~2–3 days), (4) subprocess call audits and Windows-compatible command wrapping (~1–2 days). No new build dependencies, but touches fragile path-handling code in `system` and `gui` layers.

## How to Implement

### 1. CMake Windows Generator & Paths (Greenfield on Windows side, extend `CMakeLists.txt`)

- Extend `cmake/CMakeLists.txt` to detect Windows (`if(WIN32)`) and set install prefix paths using `\` or canonical CMake path separators (CMake normalizes these internally).
  - Define a `SCRIPT_EXT` variable: `".bat"` on Windows, `""` on POSIX.
  - Define `PATH_SEPARATOR` as `;` on Windows, `:` on POSIX (for environment variable construction in setup scripts).
- Add CMake generator selection guidance in build docs (e.g., `cmake -G "Visual Studio 17 2022"` vs. `cmake -G "Unix Makefiles"`).

### 2. Windows Environment Setup Scripts

Create `cmake/rmtc-setup.bat.in` and `cmake/rmtc-setup.ps1.in` (templated like the bash/csh variants):

- `.bat` version: `setx` or `set` commands to export `RMTC_HOME`, `RMTC_RESOURCES`, `RMTC_CONFIG`, `PATH`, `PYTHONPATH` (use `;` separator).
- `.ps1` version (optional; can target PowerShell 5.0+): `[Environment]::SetEnvironmentVariable()` or `$env:` syntax.
- Extend `cmake/CMakeLists.txt` to configure these files and install them alongside bash/csh scripts.

### 3. Cross-Platform Path Separator Fixes

- Replace hardcoded `:` with `os.pathsep` in:
  - `src/python/lib/rmtc/gui/common/__init__.py:14` (`RMTC_ICON_PATHS.split(":")` → `RMTC_ICON_PATHS.split(os.pathsep)`)
  - `src/python/lib/rmtc/system/__init__.py` (lines with `env_var_path.split(":")` and `env_var_paths.split(":")` → use `os.pathsep`)
  - Check `res/modules/rmtc_core.yaml` and resource-path construction for similar hardcoding.

### 4. Subprocess & Shell Command Audits

- Audit `src/python/lib/rmtc/core/system/environment/uv/environments.py` and `src/python/lib/rmtc/core/ops/pipeline/nuke/builders.py` for subprocess calls.
  - `nuke/builders.py` currently calls `subprocess.run([... "nuke", ...])` with bare command name — likely works on Windows if Nuke is in PATH, but validate shell escaping on both platforms.
  - `uv/environments.py` uses `uv pip install --target` — `uv` CLI is cross-platform, but test on Windows specifically.
- Ensure all `subprocess` calls use `shell=False` (already the case; confirms safety).
- Use `shutil.which()` (already used in `uv/environments.py`) to locate external binaries cross-platform.

### 5. Testing & Validation (Greenfield, CI-dependent)

- Build and install RMTC on Windows (local or CI runner) and verify:
  - Python packages install and import without POSIX-path errors.
  - Environment variables resolve correctly.
  - `uv` subprocess calls execute successfully.
  - Resource paths (icons, configs) resolve via `os.path.join()` or `pathlib.Path()`.
- Update CI/build docs to document Windows build steps (file paths, CMake generator, Python version constraint).

## Considerations

- **Dependency on CI**: Per `docs/review/critique.md`, there is "No CI pipeline of any kind." Without a Windows CI runner, Windows support cannot be continuously validated — any claim to support Windows will be aspirational, not guaranteed. Adding a Windows GitHub Actions or Azure Pipelines job is a prerequisite to making Windows support credible.
- **Python version**: `pyproject.toml` requires `>=3.9`; CMake hardcodes `PYTHON_VERSION 3.9`. Confirm that all dependencies (`PyTorch`, `OpenImageIO`, `torchvision`, etc.) publish Windows wheels for Python 3.9+, since pre-built wheel availability varies by platform.
- **Native dependencies**: `OpenImageIO` and `PyTorch` may require compiled extensions; pre-built wheels typically exist for Windows, but verify versions in `pyproject.toml` are available.
- **Path separators in YAML/config**: Check `res/modules/rmtc_core.yaml` and any user-facing config paths for hardcoded `/` path separators — these should use forward slashes everywhere (cross-platform on Windows via `pathlib` or `str.replace()` on read), or accept both.
- **Out of scope**: Native code compilation for Windows (C++ components not yet present). If C++ extensions are added later (per "Realtime C++ tensor conversion" in `docs/review/features.md`), Windows MSVC toolchain support will be required.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
