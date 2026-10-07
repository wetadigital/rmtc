# Scheduler 

Scheduler defines the shared abstractions (Scheduler, Task, Job, Executor, Tracker) used by Train's scheduling of runs. RMTC Core provides a local implementation on top of this; a facility/render-farm scale wall scheduler (e.g. OpenCue, Deadline) is still outstanding and would extend the same base classes.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
