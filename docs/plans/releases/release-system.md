# Release System

## Feature Description

RMTC currently has no formal release process, CI/CD pipeline, or automated versioning. A release system will enable reproducible, auditable builds and publishes to PyPI and GitHub Releases, allowing users to install stable versions and the project to graduate from prototype to production-ready. This requires three complementary pieces: CI/CD automation (GitHub Actions), versioning discipline, and a release-approval workflow tied to TSC governance.

## Criticality

Critical. RMTC is pre-Alpha with no production warranty (technical_notes.md §11.1). Establishing versioning and release hygiene now — before a wider audience adopts the project — is essential to prevent chaotic version history and broken upgrades. This also unblocks the website launch (users will have PyPI/stable-version documentation to link to). Without this, each user must build from source, limiting adoption and making dependency management fragile.

## T-Shirt Size

L. This task spans multiple areas: setting up `.github/workflows/` (build, test, publish), integrating with `pyproject.toml`/setuptools versioning, establishing a release checklist, and potentially overhauling existing test coverage. Estimated 3-4 weeks: build CI ~1 week, test expansion ~1 week, release workflow ~1 week, process documentation ~3-4 days.

## How to Implement

1. **Prerequisite: Add CI/CD for PR Builds & Tests**
   - Create `.github/workflows/ci.yml` (GitHub Actions) to run on PR/push:
     - Build with `cmake`: `cmake -B cmake/build -S . && cd cmake/build && make`.
     - Run tests: `pytest tests/` with minimal config (test discovery from existing ~25 test files in `tests/`).
     - Lint with `pylint` (already in `pyproject.toml [project.optional-dependencies] dev`).
     - Pin Python 3.9 (from `pyproject.toml requires-python`).
   - This must be done *before* automated releases, so release builds don't publish broken code.

2. **Version Management**
   - Leverage existing `pyproject.toml` already using `setuptools-scm` (fallback_version = "0.0.0").
   - Tags follow semver: `v0.1.0`, `v0.2.0`, etc. (prefix `v` for clarity).
   - `setuptools-scm` will auto-detect git tags and set version in built artifacts.

3. **Release Workflow (GitHub Actions)**
   - Create `.github/workflows/release.yml` triggered on git tag push (e.g., `git tag v0.2.0 && git push --tags`).
   - Steps:
     1. Verify CI passed on the commit (required check).
     2. Build: `pip install build && python -m build` (creates wheel + sdist in `dist/`).
     3. Publish to PyPI: Use `pypa/gh-action-pypi-publish` action (requires PyPI token in GitHub secrets).
     4. Create GitHub Release: Use `softprops/action-gh-release` to publish built artifacts and auto-generate release notes.

4. **Release Approval & Process**
   - Integrate with existing TSC governance: Tag creation must be approved via TSC vote or maintainer consensus (document in `tsc/process/`; see existing `tsc/meetings/` and `maintainers/fetch_contributors.py` for governance structure).
   - Add `RELEASE.md` at repo root with:
     - Versioning policy (semver, alpha/beta/stable tags).
     - Release checklist (update CHANGELOG, bump version in docs, confirm all tests pass).
     - Security/breaking-change review (since pre-Alpha, breaking changes are acceptable but must be documented).
     - TSC approval step.

5. **Test Coverage Expansion** (prerequisite quality gate)
   - Current test suite (~2,900 lines across ~25 files) is mostly integration-style. Before releasing, ensure:
     - Unit tests for critical paths (Environment/Store/Factory resolution).
     - Fixture/mock store tests to avoid hard dependency on Apache AGE at test time.
     - Smoke test covering a minimal example (e.g., create a license, model, dataset; push to store).
   - No need for comprehensive GUI testing yet (design review in critique.md §6 acknowledges GUI test gap).

6. **Documentation Integration**
   - Update `README.md` installation section: add "Install from PyPI: `pip install RMTC`" alongside "Build from source".
   - Add version selector/switcher to website (if deployed) so users see docs for their installed version.

## Considerations

- **Pre-Alpha Implications**: "No warranty" status (technical_notes.md) means versions can have breaking changes, no LTS. Document this clearly in release notes (e.g., "v0.2.0 is pre-Alpha; production use not recommended").
- **Test Infrastructure Gap**: Existing tests require a running Apache AGE instance. To unblock CI, either:
  - Mock the store connection (preferred for PR CI speed).
  - Docker-compose + start/stop AGE in CI (slower, more robust for integration).
  - Start with mock approach; migrate to containerized store for future releases.
- **PyPI Metadata**: Ensure `pyproject.toml` metadata is complete (authors, URLs, classifiers for "Development Status :: 3 - Alpha").
- **Dependency Pinning**: Current `pyproject.toml` allows broad version ranges (e.g., `numpy>=1.23.0`). Consider narrowing for pre-Alpha releases to avoid silent breakage. Document policy in `RELEASE.md`.
- **Rollback Plan**: Store old releases on PyPI (immutable); consider tagging branches as backups if needed (e.g., `release/0.1.x`).
- **Out of Scope**: Conda distribution, binary wheels for C++ extensions (future optimization), per-platform testing (Linux-only for now).
- **TSC Hook**: Release approval decision must be defined in `tsc/process/` docs and linked from `RELEASE.md`.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
