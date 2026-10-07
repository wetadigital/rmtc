# Task Tracker Improvements

## Feature Description

Enhance the Train Track and Conductor tools (currently prototype-stage "likely to be merged," per technical_notes.md) to provide a unified task-tracking interface for monitoring and controlling training/inference job pipelines. Additionally, fix the GUI Publisher's build-then-publish flow to correctly track and report the status of intermediate build steps. Current state: Train Track monitors runs and can tie into TensorBoard; Conductor is an upstream job-kick-off tool; both are incomplete stubs for controlling job restarts and tweaking parameters on the render farm.

## Criticality

High. The GUI Publisher's build-publish mismatch (bugs.md #8) is an immediate blocker that breaks asset publishing whenever a build step is included. Beyond that, unified task tracking is essential for VFX pipelines where artists need to monitor multi-stage jobs (training → checkpoint write → build → publish) without dropping to the API layer. Training jobs are long-lived and GPU-expensive; poor visibility into job status and inability to restart/tweak mid-execution undermines production adoption.

## T-Shirt Size

XL. Requires: (1) fixing the Publisher's `pipeline_name` kwarg mismatch (`gui/common/widgets.py:291` vs `ops/__init__.py:111`), a 1-line fix but must verify build-publish round-trip; (2) merging/reconciling Conductor and Train Track UI into one coherent workflow (`gui/traintrack/widgets.py`, `gui/training/widgets.py`); (3) implementing job-state persistence to track build/publish steps across system restarts (new lightweight job-log schema, likely in `ops/scheduling.py`); (4) replacing the hardcoded `LocalTrainScheduler` import in the GUI (critique.md §6) with Factory-resolved scheduler instances. Spans multiple GUI modules, crosses into `ops/scheduling.py` and `ops/__init__.py` core logic, and has dependencies on the eventual merge of Conductor/Train Track that is not yet architecturally decided.

## How to Implement

1. **Fix the immediate Publisher bug** (bug.md #8):
   - Change `gui/common/widgets.py:291` from `pipeline_name=pipeline_name` to `name=pipeline_name`.
   - Add a manual round-trip test: ingest an artifact via Junction, select a build pipeline, hit "Publish," verify the build step completes and artifact URI is updated in the store.

2. **Decouple scheduler from GUI hardcoding** (critique.md §6 concern):
   - Replace direct imports of `LocalTrainScheduler`/`LocalInferScheduler` in `gui/common/widgets.py:10-11` with Factory resolution.
   - Add a `Scheduler` type to `res/modules/rmtc_core.yaml` (currently missing; only `Trainer` and `Inferer` types exist).
   - Modify `gui/training/widgets.py` and `gui/traintrack/widgets.py` to resolve the scheduler via `Factory.create()` using a config-driven type name, allowing facilities to plug in farm schedulers without forking the GUI.

3. **Unify Conductor + Train Track** (greenfield architecture):
   - Design a single "Job Manager" widget (call it `TrainTrackWidget`, consolidating `gui/training/widgets.py` and `gui/traintrack/widgets.py`).
   - Expose two modes: "Launch" (formerly Conductor, for kicking off new runs with parameter tweaks) and "Monitor" (formerly Train Track, for tracking existing runs).
   - The widget listens to the System object for run updates and displays a table: `[Run ID | Status | Metric | Elapsed | Actions (Restart/Cancel/Export Logs)]`.

4. **Implement job-step tracking** (greenfield):
   - Extend `Run` entity with a `job_steps` property (array of `{step_name: "build", status: "pending"|"running"|"done", error_msg: "...", timestamp}` dicts).
   - In `ops/__init__.py:build()` and `ops/__init__.py:publish()`, wrap each step with status updates pushed to the store (via `system.push()` on each step completion).
   - In the GUI, display a nested tree: `Run → [Train Step | Build Step | Publish Step]`, each with a progress indicator.

5. **Scheduler resolution in System/GUI**:
   - Add a `get_scheduler()` factory method to `system/__init__.py:System` class that resolves the configured scheduler type (currently hardcoded defaults in `ops/scheduling.py:1-50`).
   - Update `ops/__init__.py:train()` / `ops/__init__.py:infer()` to use this factory method instead of direct instantiation.
   - Ensure `gui/training/widgets.py` and `gui/traintrack/widgets.py` call the same factory method when launching jobs.

## Considerations

- **Concurrency risk**: GUI shares one `System` instance across all tools (critique.md §6). Job-step updates must use proper broadcast messages (via `system.broadcaster`) rather than direct property mutation to avoid races between Conductor (launching), Train Track (monitoring), and the main UI thread.
- **Incomplete scheduling**: Only `LocalTrainScheduler` and `LocalInferScheduler` are implemented. Wall-based/farm schedulers are facility-specific and not included. The Factory pattern allows these to be plugged in without GUI code changes, but no farm scheduler implementation exists in the open repo. Document this as a future facility integration point.
- **Already-corrupted checkpoints** (bugs.md #10): Checkpoint resume is broken; any job that was checkpointed before this fix will fail on resume. Job Manager should catch checkpoint load errors and surface them clearly ("Checkpoint corrupted or from incompatible version — retrain from scratch or from an earlier checkpoint").
- **Publisher failure modes**: Build/publish can fail at various stages (build fails, URI not resolvable, asset manager unreachable). Job-step tracking must log error messages to help users diagnose. Integrate with the logging system (`system/__init__.py:Log`) to make build/publish logs queryable from the GUI.
- **Schema migration**: Adding `job_steps` to `Run` is a schema change. Existing stored Runs will need a migration. Plan a compatibility shim: if `job_steps` is not present on load, default to an empty list.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
