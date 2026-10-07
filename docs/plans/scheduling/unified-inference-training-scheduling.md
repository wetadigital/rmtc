# Unified Inference & Training Scheduling System

## Feature Description

Extract the scheduling system from its current location split between `core/ops/train/local/schedulers.py` and `core/ops/infer/local/schedulers.py` into a single shared base interface. Both training and inference jobs are currently defined with separate scheduler classes (`LocalTrainScheduler` and `LocalInferScheduler`), each inheriting from a shared `LocalScheduler` in `core/ops/scheduling/local/schedulers.py`, but the entire scheduling subsystem is treated as an internal detail of each module rather than a pluggable, facility-configurable system. This task extracts scheduling to become first-class and reusable, allowing both train and infer to operate with the same backend (local, AWS, farm-based, etc.) without code duplication.

## Criticality

High. Technical Notes explicitly states "this is defined internally to the train module but should be broken out to allow the inference to run with the same architecture." Both train and infer currently hardcode their scheduler choices; unifying them prevents architectural debt and enables the third task (OpenCue/Deadline scheduling) to be implemented once for both subsystems rather than twice.

## T-Shirt Size

M. Requires moving/reorganizing existing code (`LocalScheduler` is already extracted; training and inference schedulers just need to be reregistered and decoupled from their containing modules), creating a new shared base `Scheduler` interface abstraction if one doesn't already exist, and updating YAML module registration to expose schedulers as first-class Factory types. No new dependencies; moderate refactoring of existing module boundaries.

## How to Implement

1. **Create a new `core/ops/scheduling/base.py`** (or verify it already exists in `core/ops/scheduling/__init__.py`) to hold the abstract base interface that all schedulers must implement. The interface should define lifecycle methods: `start()`, `pause()`, `resume()`, `stop()`, `join()`, and property accessors for `job`, `task`, and `results`. Verify that `LocalScheduler` in `core/ops/scheduling/local/schedulers.py` and the AWS stub in `core/ops/scheduling/aws/schedulers.py` both conform to this interface.

2. **Register schedulers in `res/modules/rmtc_core.yaml`** under a new `Scheduler` category (or an existing one if present). Add entries for `LocalTrainScheduler`, `LocalInferScheduler`, and eventually `AWSScheduler` and `AWSInferScheduler` so they can be resolved via `Factory.create(type_name)` rather than direct imports. Example entry:
   ```yaml
   Scheduler:
     LocalTrain:
       version: 1.0.0
       class_path: rmtc.core.ops.train.local.schedulers.LocalTrainScheduler
     LocalInfer:
       version: 1.0.0
       class_path: rmtc.core.ops.infer.local.schedulers.LocalInferScheduler
   ```

3. **Update `core/ops/train/local/schedulers.py` and `core/ops/infer/local/schedulers.py`** to remain as concrete implementations (no changes to the class definitions themselves), but add `__init__.py` exports so they are treated as submodules, not internal details.

4. **Update callers** in `core/ops/train/__init__.py` and `core/ops/infer/__init__.py` (and anywhere else schedulers are instantiated) to use `Factory.create()` with a type name from config instead of direct class instantiation, following the pattern already used for other pluggable components in the system (e.g., `Factory.create(rmtc_sys.config.get("trainer_type"))`).

5. **Fix the GUI** (`gui/common/widgets.py:54, 79`) to resolve schedulers through Factory instead of hardcoding `LocalTrainScheduler`/`LocalInferScheduler` imports. This unblocks the next task (pluggable farm schedulers).

## Considerations

- **Dependency on Feature #2 (OpenCue/Deadline)**: This task *enables* that task; no hard dependency, but unifying scheduling first makes plugging in new backends trivial.
- **Async/concurrency gap**: Critique.md §2 notes "make this work async" appears four times in scheduling code and the GUI. This task does not fix async execution but creates the architectural foundation for farm schedulers (which inherently require async) to be plugged in without further refactoring.
- **No changes required to `BaseScheduler` signature**: The existing `LocalScheduler` base class in `core/ops/scheduling/local/schedulers.py` already has the right shape; this is pure reorganization and registration, not redesign.
- **Risk**: GUI has a hardcoded scheduler import (critique.md §6); fixing this is essential, but requires updating two call sites.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
