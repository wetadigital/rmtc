# Testing Expansion

## Feature Description

Expand and deepen test coverage across RMTC, particularly for VFX-specific asset handling and IO layers. Currently ~16 test files (~2,900 lines) covering basic functionality with integration-style tests against real stores; no CI pipeline exists to run them automatically. The examples (Basics, Image2Image, MNIST, Tracking, Pipeline) provide user-facing patterns but aren't directly exercised by tests. VFX-first citizens (EXR, USD, DCC integration) are under-tested relative to the critiques' IO-layer TODOs.

## Criticality

High. Catching regressions automatically prevents silent data/provenance corruption on the persistence layer; the absence of CI is a ship-blocking issue per critique.md §6. Testing underpins the project's core "trustworthy provenance" claim.

## T-Shirt Size

L. ~15-20 new test files, likely ~4,000 additional lines. Touches multiple subsystems (IO, assets, store, GUI); no new dependencies but requires setting up pytest fixtures for store backends and DCC mock pipelines.

## How to Implement

1. **Store/CI foundation (2-3d):** Set up `.github/workflows/tests.yml` to run pytest on all commits/PRs; pin to Neo4j test container for reproducibility (not AGE, for now, to keep CI simpler). Ensure `tests/` directory structure is discoverable by pytest.

2. **IO/VFX layer expansion (3-4d):** Ground in critique.md §1's IO TODOs:
   - `core/ops/io/oiio/image.py:87,100,131` — multi-part EXR and non-RGBA channels. New file: `tests/core/ops/io/oiio_test.py` with cases for 3-part EXR, single-channel gray, RGBA + extra alpha, and round-trip assertions.
   - `core/ops/io/usd/camera.py:85,91` — camera framerate and tensor loading. New file: `tests/core/ops/io/usd_test.py`.

3. **Artifact/tensor format validation (2-3d):** Per technical_notes.md's Tensor Formats section — standardize on HWC/RGBA. New file: `tests/ops/artifacts_test.py` verifying tensor layout invariants before/after read/write for Image, Mesh, Camera types. Round-trip through processors (ExtractChannel, AddChannel, etc.) to catch the channel-processor bugs (bugs.md #12-14).

4. **Store concurrency & parameterization (1-2d):** New file: `tests/track/store_concurrency_test.py` simulating two writers pushing conflicting updates (currently silently dropped per flaws.md §3); verify that this is detected and surfaced to the caller. Also add a `store_injection_test.py` injecting property values with quotes/apostrophes/Cypher symbols to confirm parameterized queries block injection (flaws.md §1).

5. **Asset manager & pipeline (2d):** New file: `tests/core/ops/pipeline/asset_manager_test.py` covering FilesystemManager's `relocate()` bug (bugs.md #7) — pass both scalar and list URIs, verify both code paths work after fix.

6. **GUI end-to-end (1-2d):** Expand `tests/gui/` from 116 lines to ~400-500 lines. Cover NodeGraphQt interaction (signal/noodle ops), Publisher's build→publish flow (bugs.md #8), and property editor for Enum properties with defaults (flaws.md §2).

## Considerations

- **Order:** flaws.md #1 (parameterized queries) is a blocker for store_injection_test; prioritize it before writing that test.
- **Fixtures:** Reuse the existing test store setup (if one exists in `tests/track/`) rather than creating new fixtures; confirm pytest discovery and module registration before adding 10+ new files.
- **Risk:** Adding tests doesn't fix bugs — group testing PRs with bug-fix PRs (e.g., test for #7 lands with the `relocate()` fix) to keep the test suite passing.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
