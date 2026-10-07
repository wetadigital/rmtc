# Rocky Linux Build Support

## Feature Description

Add explicit Rocky Linux (EL9, glibc-based) build validation to RMTC. Rocky Linux is ABI-compatible with RHEL/CentOS and shares glibc, package management (dnf), and POSIX conventions with the implicit Linux baseline the project already assumes. No code changes are anticipated; this is primarily a validation/CI task: build and test RMTC on Rocky Linux containers or runners, verify native dependencies (`OpenImageIO`, `PyTorch`, compilers) install cleanly via dnf, and document any Rocky-specific quirks or version pins in the build/install guide.

## Criticality

Medium. Rocky Linux is widely adopted in VFX pipelines (particularly at larger studios and render farms) as a free, stable, RHEL-compatible alternative. Demonstrating that RMTC builds and runs on Rocky increases credibility and accessibility; however, absence of Rocky support does not block core functionality (unlike Windows). Pre-Alpha status means no warranty is promised, so this is more about "can we claim Rocky support" than "does it have to work."

## T-Shirt Size

S. This is primarily a CI/validation task (1–2 days), not a code-change task:
- Add a Rocky Linux Docker container or CI runner to the build pipeline (~0.5 days).
- Verify dependencies install via `dnf` and run tests (~0.5 days).
- Document any Rocky-specific quirks or package names (~0.5 days).
- No new files or modules; touches only CI configuration and documentation.

## How to Implement

### 1. Rocky Linux CI Runner Setup (Greenfield)

- Add a new CI job (e.g., `.gitlab-ci.yml` stage or GitHub Actions workflow) that:
  - Spins up a Rocky Linux 9 container (e.g., `rocky:9` image).
  - Installs base build tools: `gcc`, `cmake>=3.27`, `python3-devel`, `git`.
  - Runs `cmake ..` and `cmake --install .` as on any POSIX system.
  - Executes the test suite (`pytest tests/`).
- Document in `docs/build.md` or a new `docs/platforms.md`:
  - Rocky Linux 9 is tested and supported.
  - Tested on specific Python version (e.g., Python 3.9+, which ships with Rocky 9).

### 2. Dependency Validation (Existing CI job)

- Verify that key dependencies from `pyproject.toml` install cleanly on Rocky via `pip` or `dnf`:
  - `PyTorch` (`torch>=2.1.0`) — verify that the pre-built CPU and GPU wheels work on Rocky; if not, build from source or pin a working version.
  - `OpenImageIO>=2.2.0` — check if available via `dnf` (likely not; OIIO is often compiled locally or sourced from a custom repo); document the expected build path.
  - `PySide2` — verify pre-built wheels are available; if not, may require compilation.
  - Smaller packages (`pyyaml`, `numpy`, `flask`, `requests`) typically have Rocky-ready wheels.
- If any package lacks Rocky wheels, update `pyproject.toml` or build docs to note the workaround (e.g., "install OIIO from source using the provided CMake; use `--no-binary` for PySide2").

### 3. Documentation

- Add a "Platforms" section to `docs/technical_notes.md` or create `docs/platforms.md`:
  - **Tested**: Rocky Linux 9, Python 3.9+, CMake 3.27+.
  - **Known quirks**: List any Rocky-specific package names or versions (if found).
  - **Not tested**: Older Rocky/CentOS versions, RHEL 8, other EL variants (can be added later as tested).
- Note in `README.md` or release notes that Rocky Linux is a supported platform (if CI confirms build and tests pass).

## Considerations

- **No code changes expected**: Rocky Linux is POSIX/glibc-compatible; no Python-level path handling, subprocess syntax, or build logic changes are needed (unlike Windows support).
- **Existing assumptions are sufficient**: The project already assumes POSIX (bash/csh environment setup, `:` path separator, etc.), which Rocky shares. If POSIX-specific code is audited/fixed for Windows support (see `windows-build-support.md`), those fixes will automatically benefit Rocky.
- **GPU support on Rocky**: If CUDA-enabled builds are desired (e.g., PyTorch with CUDA), verify CUDA 11.8+ (or later) is available on Rocky 9; NVIDIA provides CUDA repos for EL9. Document this as optional.
- **Dependency on Windows work**: If this plan is executed *after* the Windows support plan, cross-platform path fixes (e.g., `os.pathsep` instead of hardcoded `:`) will already be in place; no additional changes needed.
- **Out of scope**: Optimization for Rocky-specific configurations (e.g., specific compute architectures, SELinux policy tuning). This is a baseline validation, not a tuning exercise.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
