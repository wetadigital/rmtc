# Strong Integration with CG Pipeline

## Feature Description

Deepen RMTC's integration with VFX/CG DCC pipelines beyond the current Nuke-specific builder. Currently RMTC has an ops/pipeline architecture (technical_notes.md §"Pipeline") with builder classes in `core/ops/pipeline/nuke/builders.py` and asset managers in `core/ops/pipeline/asset_managers/filesystem.py`. The Nuke builder has known HACKs (critique.md §2 lines 122) and the pipeline integration is narrowly tailored to Nuke. The feature is to generalize the builder/publisher pattern, fix existing Nuke HACKs, add builders for other DCCs (Maya, Houdini, etc.), and strengthen the artifact build→publish→import workflow for production pipelines. This includes fixing bugs.md #8 (GUI Publisher `pipeline_name` mismatch) and addressing the builder validation issues flagged in critique.md §1 lines 45-48.

## Criticality

**High** — The whole purpose of RMTC is VFX-first artifact tracking and pipeline integration (technical_notes.md §"VFX First"). Without strong DCC integration, RMTC remains a Python library for researchers, not a production pipeline tool. This unblocks real studio adoption.

## T-Shirt Size

**L** — ~4-5 days per DCC beyond Nuke, plus 1-2 days for generalizing the builder pattern and fixing existing bugs. Nuke builder fixes (~0.5d), Maya builder skeleton (~1d), Houdini builder skeleton (~1d), asset manager cleanup (~1d), integration tests (~1d). Higher cost because it requires understanding each DCC's scripting API and build/publish semantics.

## How to Implement

1. **Fix Nuke builder HACKs:** Review `core/ops/pipeline/nuke/builders.py` (lines 88, 103, 122). Line 122's `-i` vs `-t` HACK must be documented or replaced with a proper check. Lines 88/103's "weakly enforced" validation should be strengthened with explicit pre-build checks (e.g., verify model format compatibility with Nuke version before attempting build).

2. **Fix GUI Publisher bug (bugs.md #8):** In `gui/common/widgets.py` line 291, change `pipeline_name=pipeline_name` to `name=pipeline_name` to match the `System.build()` signature in `ops/__init__.py` line 111.

3. **Generalize builder interface:** Review `BaseBuilder` in `core/ops/pipeline/` (find exact path) and clarify the contract — what properties must a builder expose, what methods must be implemented. Document builder registration in `res/modules/rmtc_core.yaml` alongside the existing Nuke entry. Ensure the factory resolution of builders is correct and testable.

4. **Add Maya builder skeleton:** Create `core/ops/pipeline/maya/builders.py` with a `MayaBuilder` class that can at minimum serialize a PyTorch model to a Maya-compatible format (likely just copying to a standard path, since Maya doesn't natively run PyTorch). Register in `res/modules/rmtc_core.yaml`. Stub the publish/build workflow.

5. **Add Houdini builder skeleton:** Similar to Maya, create `core/ops/pipeline/houdini/builders.py`. Houdini has more ML integration potential (e.g., via PyTorch in Python SOP), so this is a higher-value target.

6. **Test publish→import round-trip:** Integration tests that build an artifact, publish it to an asset manager, and then import it back in the DCC. Manual smoke test: publish a PyTorch model to disk, verify it's importable in Nuke/Maya.

## Considerations

- **Risk:** DCC APIs are vendor-specific and fragile across versions. Builders will be tightly coupled to specific DCC versions (Nuke 12, 13, 14, etc.). This is inherent, not a design flaw.
- **Out of scope:** Implementing full USD/Open Asset IO interop here; that's a separate effort. This is about basic build/publish.
- **Design question:** Should builders be in `core/ops/pipeline/` (current location) or split into a separate `dcc_builders` module? Clarify the organization.
- **Depends on:** Indirectly on "license audit" (builders may want to verify license compliance of the input artifact before publishing).
- **Future:** Once the pattern is established, studios can write their own builders for internal DCCs.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
