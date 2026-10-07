# Docker-Based Tasks with UV Environment

## Feature Description

Wrap the execution unit of training and inference jobs (the actual train/infer task running on a worker) inside a Docker container that carries the UV-managed environment from Feature #4 (`docs/plans/uv_envmanager.md`). Currently, jobs execute directly on the local machine or farm worker with no isolation. This feature adds a containerization layer so that each job runs in its own isolated container with a known, reproducible set of Python packages, preventing environment pollution, version conflicts, and enabling portability across different worker machines (local, cloud, on-premise render farms). The container image is built from a template `Dockerfile` that installs RMTC itself, then layers the job-specific UV environment on top at runtime by mounting or injecting the UV package directory.

## Criticality

Medium. This is not a blocker for basic training/inference on a single machine, but it is essential for render-farm deployment (Feature #2) where workers are heterogeneous and may have conflicting global Python environments. Without this, farm jobs will fail mysteriously due to version conflicts or missing dependencies.

## T-Shirt Size

L. Requires designing and building a base Dockerfile for RMTC + Python runtime, writing a container-build step into the scheduler's job submission pipeline (to construct a job-specific image), integration with the UV environment manager's output (directories of installed packages), updates to both `LocalScheduler` and `FarmScheduler` to invoke Docker, writing tests with a local Docker daemon, and documentation. A new `core/ops/scheduling/container.py` or similar module to encapsulate build/run logic. This touches multiple subsystems (schedulers, environment manager, job execution) but does not require new dependencies (Docker CLI is already present on farm workers; Python Docker SDK is optional).

## How to Implement

1. **Create a base `Dockerfile`** (in `res/docker/Dockerfile`) that:
   - Starts from a Python base image (e.g., `python:3.11-slim`).
   - Installs system dependencies (e.g., `apt-get install -y build-essential libopenblas-dev` for PyTorch).
   - Installs RMTC source (via `COPY` or `pip install` from a built wheel).
   - Defines entrypoints/CMD that the scheduler can override to execute a train/infer task.

2. **Add a container builder utility** (`core/ops/scheduling/container.py`) with a `ContainerBuilder` class:
   - `build(uv_env_dir, job_id, base_image=None)`: takes a UV environment directory from Feature #4, constructs a temporary Dockerfile that layers the UV packages on top of the base image (e.g., via `COPY src /opt/rmtc_env` and `ENV PYTHONPATH=/opt/rmtc_env:$PYTHONPATH`), builds the image, returns the image ID.
   - `run(image_id, command, volumes=None, env_vars=None)`: runs a container from that image with the given command, optional volume mounts (for I/O data), environment variables, and captures stdout/stderr.

3. **Update `LocalScheduler.start()`** (in `core/ops/scheduling/local/schedulers.py`) to optionally wrap the job execution:
   - Add a flag `use_container=False` to the scheduler constructor.
   - If `True`, call `ContainerBuilder.build()` with the active UV environment, then `ContainerBuilder.run()` with the task's executable instead of running it directly via `multiprocessing.Process`.

4. **Update `FarmScheduler.start()`** (Feature #2's implementation in `core/ops/scheduling/opencue/schedulers.py`):
   - Always build a container (farm jobs assume isolation).
   - Pass the container image ID to the farm's job submission API so the farm worker pulls and executes the image instead of running bare scripts.

5. **Integrate with UV environment manager** (`core/system/environment/uv/environments.py` from Feature #4):
   - After the UV environment is set up and packages added via `add_packages()`, the `Uv` instance tracks the environment directory (e.g., `/tmp/rmtc_uv_envs/default`).
   - When a scheduler needs to containerize a job, it retrieves the current environment directory from the `env_manager` and passes it to `ContainerBuilder.build()`.
   - The container image layers that directory's contents onto `sys.path`, making all installed packages importable inside the container.

6. **Config option** to enable/disable containerization per scheduler:
   - For `LocalScheduler`: add `container_enabled: true` to config, defaulting to `false` for backward compatibility and speed on single-machine development.
   - For `FarmScheduler`: always `true` (implicit).

## Considerations

- **Prerequisite**: Feature #4 (UV environment manager) must be completed first; this task depends on a working `Uv` class and an environment directory to layer.
- **Image size & build time (greenfield risk)**: Building a Docker image for every job adds latency and disk space overhead. Consider:
  - Caching base images (`python:3.11 + RMTC + system deps`) to avoid rebuilding.
  - Pre-building a library of job-specific images if package sets are reused across jobs.
  - Using a registry (Docker Hub, local, in-farm) to avoid rebuilding on every worker.
- **Volume mounts for I/O**: Training/inference jobs read datasets and write results. The container builder must support mounting the dataset directory and solution/results directory into the container so the job can read/write them. This is handled by the `volumes` parameter in `ContainerBuilder.run()`.
- **Nested containerization (farm context)**: If the farm itself uses containers (e.g., Kubernetes pods), running Docker-in-Docker may not be possible or desirable. This is a deployment decision, not a design issue; the scheduler should gracefully degrade or fail fast if Docker is unavailable.
- **Dockerfile customization**: Different jobs may have different system dependencies (CUDA for PyTorch, etc.). Consider allowing jobs to specify a custom base image or additional `RUN` commands to install extra packages. For now, assume a single base image covers all cases.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
