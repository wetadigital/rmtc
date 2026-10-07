# OpenCue & Deadline Scheduling

## Feature Description

Implement a real, production-ready farm scheduler backend (OpenCue for Deadline or similar render-farm scheduling system) to replace the current AWS stub in `core/ops/scheduling/aws/schedulers.py`, which has every lifecycle method raising `NotImplementedError`. This scheduler will extend the unified base `Scheduler` interface (Feature #1) to allow training and inference jobs to be submitted to a render farm instead of running locally. The scheduler must integrate with the chosen farm system's job submission API, handle job lifecycle (submit, monitor, retrieve results), and respect the same `Job`/`Executor` contract used by the local scheduler.

## Criticality

High. Technical Notes explicitly identifies this as "an ideal first implementation task to support OpenCue for Deadline or something similar," and the current stub is a complete blocker for facility-scale training/inference. This feature is essential for any production deployment where jobs must run on shared compute resources.

## T-Shirt Size

L. Requires researching/selecting a farm backend (OpenCue, Deadline, or equivalent), implementing the full `Scheduler`/`Job`/`Executor` interface (likely 300-500 lines across three classes), adding subprocess calls to submit jobs and poll status, implementing result retrieval from farm storage, writing integration tests with a mock farm service or docker-based test harness, and updating module registration. The GUI change to use Factory instead of hardcoded imports (Feature #1's task #5) is a prerequisite, not part of this scope.

## How to Implement

1. **Finalize backend choice**: Document which farm system(s) to support. OpenCue (open-source, used by major studios) is the recommended starting point; Deadline is proprietary and less suitable for open-source RMTC. The interface should be agnostic enough that other systems can be added later (e.g., in a separate `core/ops/scheduling/deadline/` directory).

2. **Create `core/ops/scheduling/opencue/schedulers.py`** (or chosen backend path) with `FarmScheduler` (base for both train and infer), `FarmJob`, and `FarmExecutor` classes. Implementation sketch:
   - `FarmScheduler.__init__`: accept `host`, `port` (farm service endpoint), `env_manager`, `asset_manager`, `task` (run or inference).
   - `FarmScheduler.start()`: construct an OpenJD job definition, invoke the farm's Python SDK or REST API to submit, store the returned job ID, return a `FarmJob` instance.
   - `FarmJob.start()`: no-op (job already started by scheduler).
   - `FarmJob.join()`: poll the farm API until job completes, retrieve `stdout`/`stderr`/exit code.
   - `FarmExecutor.__call__()`: serialize the task (run or inference object) to a JSON/pickle representation, prepare a container image or script bundle for the farm to execute, delegate to the farm's executor.

3. **Handle environment in containerization**: The farm backend must work *with* the UV environment manager (Feature #4). When a job is submitted, the farm executor should:
   - Receive or construct a UV environment specification (paths to installed packages).
   - Either mount that environment into the job's container (if using Docker) or install/activate it in the farm job's sandbox.
   - Ensure `PYTHONPATH` includes the UV environment directory so RMTC and dependencies are importable on the farm worker.

4. **Result handling**: After the farm job completes, `FarmJob.results` should fetch the output artifacts (trained weights, inference results) from farm-accessible storage (S3, NFS, etc.) and return them to the local system in the same format as `LocalJob.results`.

5. **Register in `res/modules/rmtc_core.yaml`** under `Scheduler` (or update existing entries if Feature #1 has already added the category):
   ```yaml
   Scheduler:
     OpenCueTrain:
       version: 1.0.0
       class_path: rmtc.core.ops.scheduling.opencue.schedulers.OpenCueTrainScheduler
     OpenCueInfer:
       version: 1.0.0
       class_path: rmtc.core.ops.scheduling.opencue.schedulers.OpenCueInferScheduler
   ```

6. **Config integration**: Users select the farm scheduler via `rmtc.yaml` config (e.g., `scheduler_type: "rmtc_core.Scheduler.OpenCueTrain-1.0.0"`), resolved by Factory just like training/inference backends.

## Considerations

- **Prerequisite**: Feature #1 (unified scheduling + Factory integration) *must* be completed first; this task requires the pluggable scheduler architecture to exist.
- **Environment coupling**: Feature #4 (UV environment support) should be completed or in progress. Farm schedulers need a reliable way to ensure dependencies are available on farm workers; UV environments provide that.
- **Containerization strategy (greenfield)**: The decision of whether to containerize jobs (Docker, Apptainer) or use the farm's native sandbox is architectural and out of scope for this design. Assume for now that the farm backend handles it; the scheduler just needs to ensure environment variables and paths are correctly propagated. This is a major design question to resolve during implementation.
- **Async/concurrency**: Farm schedulers are inherently asynchronous (jobs don't complete immediately). The TODO "make this work async" (critique.md §2) will surface here; consider using `asyncio` or a thread pool for polling farm status.
- **Security**: Farm submission APIs often require authentication (API key, service account). Design the `Scheduler.__init__` to accept credentials as constructor arguments, not env vars, so tests can inject mocks.
- **Testing strategy**: Unit tests should mock the farm service API; integration tests could use a docker-based farm simulator or the farm SDK's local test harness if available.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
