# DCC Plugins

## Feature Description
DCC (Digital Content Creation) plugins enable real-time inference directly within tools like Nuke, Maya, or Houdini by embedding RMTC's inference engine. A DCC plugin would reference a `Solution` rather than a specific model, automatically pulling the best-performing `Run` and executing inference using the marshalling process-stack defined in the model. Current state: fully unimplemented. Differs from the existing Nuke *build* pipeline step (`core/ops/pipeline/nuke/builders.py`), which converts trained weights into Nuke-executable formats post-training; a DCC plugin would enable in-DCC inference during interactive work.

## Criticality
High. DCC plugins are a documented roadmap item (critique.md §4) essential for adoption by VFX studios; without them, the system requires external dispatch to leverage trained models, blocking the studio workflow integration that RMTC targets.

## T-Shirt Size
L. Greenfield UI in a DCC (Nuke/Maya plugin SDK, UI panels, event handling), process marshalling layer to bridge DCC tensor formats to RMTC standard HWC RGBA (or mesh format), a scheduler/launcher for background inference, and integration testing against at least one DCC. Likely 15-20 days + DCC-specific SDK learning curve.

## How to Implement
**Greenfield architecture:**

1. **Process-stack marshalling** (foundational): Extend `core/ops/process/` to add DCC-specific processors (e.g., `NukeToHWC`, `NukeFromHWC`) that convert between DCC native tensor layouts and RMTC's standardized HWC RGBA. These processors are already instantiated from type-names stored in `Model.signature` (per technical_notes.md's "DCC Inference" section), so no new mechanism is needed—just the concrete processor implementations.

2. **Plugin entry point per DCC** (greenfield):
   - Nuke: a `.py` plugin under `src/python/lib/rmtc/core/ops/dcc/nuke/` (mirroring `core/ops/pipeline/nuke/builders.py` structure).
   - Extends Nuke's Node base class, adds a panel UI for Solution/Run selection (using Nuke's Qt integration).
   - Registers callbacks on input/output knob changes to trigger inference.

3. **Thin inference wrapper** (greenfield):
   - New module `core/ops/dcc/inferer.py` with a `DCCInferer` class that:
     - Takes a Solution name, fetches the best Run via `System.get_best_run(solution_name)` (wrapping existing Run selection logic in track).
     - Reads the Run's Model and selected Weights, instantiates the process-stack from the model's signature.
     - Executes inference via existing `DatasetInferer` or a lean wrapper around `core/ops/infer/simple/inferers.py`.
   - Does NOT schedule or thread—DCC plugin owns that (likely async via DCC's job queue or a subprocess).

4. **Registration**: Add Nuke plugin to a new `DCC` category in `res/modules/rmtc_core.yaml` if multiple DCCs are implemented; otherwise inline as a non-factory helper (simpler for one plugin).

## Considerations
- **Process-stack availability**: The model's `signature` property must include the marshalling process-stack. If a model was trained without one, the DCC plugin cannot infer without manual specification—this is acceptable (the model is incomplete), but should be flagged in UI.
- **Out of scope**: Multi-threaded inference dispatch (deferred to DCC async mechanisms), Deadline/OpenCue scheduling (separate feature), C++ tensor conversion (see features.md "Runtime inferencing")—plugins should remain Python.
- **Dependencies**: Must route through existing `System.track` store to fetch Runs; if REST interface (web-rest-interface.md) is implemented first, a thin HTTP client wrapper could replace direct store access (enabling remote RMTC servers).
- **Testing**: Unit tests for process-stack marshalling; integration test with a Nuke subscription/build (or mock Nuke API for CI).

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
