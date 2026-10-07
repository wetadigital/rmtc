# Roadmap Plans

One plan document per feature bullet in [`docs/review/features.md`](../review/features.md), grouped
into the same categories and folders. Each plan covers: feature description, criticality,
t-shirt size estimate, how to implement, and considerations.

## Provenance

| Plan | Description | Criticality |
| --- | --- | --- |
| [Stronger Inference & Training Guardrails](provenance/stronger-inference-training-guardrails.md) | Enforce license/permission checks at inference and training execution time, not just at solution search time. | Critical |
| [License Audit](provenance/license-audit.md) | Legal review of the License model to make license properties authoritative rather than "only indicative." | High |
| [Strong Integration with CG Pipeline](provenance/cg-pipeline-integration.md) | Generalize the builder/publisher pattern beyond Nuke and harden the build→publish→import workflow. | High |
| [Watermarking Support](provenance/watermarking-support.md) | Embed tamper-evident C2PA provenance markers into exported asset data so provenance survives outside RMTC's own graph. | High |
| [Split the Store into Tracking & Operations Databases](provenance/tracking-operations-store-split.md) | Separate immutable provenance facts from mutable runtime/job state into two cross-referenced stores. | High |

## Security

| Plan | Description | Criticality |
| --- | --- | --- |
| [Credential Management](security/credential-management.md) | Remove plaintext credential storage and add a secrets-manager integration point. | High |
| [Permissions System](security/permissions-system.md) | Add a user/context identity and role-based authorization system; today System trusts every caller. | Medium |

## Scheduling

| Plan | Description | Criticality |
| --- | --- | --- |
| [Unified Inference & Training Scheduling](scheduling/unified-inference-training-scheduling.md) | Extract train/infer scheduling into one shared, pluggable base interface instead of duplicated classes. | High |
| [OpenCue/Deadline Scheduling](scheduling/opencue-deadline-scheduling.md) | Implement a real farm-scheduler backend to replace the fully-stubbed AWS scheduler. | High |
| [Docker-Based Tasks with UV Env](scheduling/docker-based-tasks-with-uv-env.md) | Containerize job execution units, layering the UV-managed environment on top for reproducible farm workers. | Medium |
| [Environment Support – UV Specifically](scheduling/uv-environment-support.md) | Implement the working UV-backed environment manager; design lives in `uv_envmanager.md`. | High |
| [UV-backed Environment Manager (design)](scheduling/uv_envmanager.md) | Design doc for the `Uv(BaseEnvironmentManager)` class that this category's UV work implements. | — |

## Frontends

| Plan | Description | Criticality |
| --- | --- | --- |
| [Web REST Interface](frontends/web-rest-interface.md) | Harden and complete the Flask REST skeleton bridging two System instances; prerequisite for the JS UI and JIRA bridge. | High |
| [DCC Plugins](frontends/dcc-plugins.md) | Enable real-time in-DCC inference (Nuke, Maya, Houdini) driven by a Solution reference. | High |
| [JavaScript UI](frontends/javascript-ui.md) | Thin browser frontend on top of the REST API for model/run browsing without direct Python access. | Medium |
| [JIRA Model Approval Frontend](frontends/jira-model-approval-frontend.md) | Webhook bridge mapping JIRA issue transitions to Run approval state in RMTC. | Medium |

## Runtime Inferencing

| Plan | Description | Criticality |
| --- | --- | --- |
| [Comprehensive ONNX Conversion with Packagers](runtime-inferencing/onnx-conversion-with-packagers.md) | Extend ONNX export beyond the two currently supported packagers and fix the CPU-export bug. | High |
| [Realtime C++ Tensor Conversion](runtime-inferencing/realtime-cpp-tensor-conversion.md) | Greenfield C++ mirror of Process/ProcessStack for low-latency DCC tensor marshalling. | Medium |
| [C++ Wrapper with Python Exposure](runtime-inferencing/cpp-wrapper-with-python-exposure.md) | pybind11 bindings making the C++ tensor layer a drop-in substitute for its Python counterpart. | Medium-High |
| [C++ Factory](runtime-inferencing/cpp-factory.md) | C++ mirror of the Python `Factory` for type-name resolution without a Python instantiation hop. | Medium |

## GUI

| Plan | Description | Criticality |
| --- | --- | --- |
| [GUI Asset Type Preview Support](gui/gui-asset-type-preview-support.md) | Add rich, type-aware preview widgets to the Junction ingestion tool and Property editor. | High |
| [Task Tracker Improvements](gui/task-tracker-improvements.md) | Unify Train Track/Conductor job monitoring and fix the build→publish status-tracking bug. | High |
| [GUI Modernisation](gui/gui-modernisation.md) | Refresh the Qt + NodeGraphQt look and work around its node-naming/signal quirks. | Low |

## Releases

| Plan | Description | Criticality |
| --- | --- | --- |
| [Release System](releases/release-system.md) | Stand up CI/CD, versioning discipline, and a TSC-governed release-approval workflow. | Critical |
| [Website](releases/website.md) | Public documentation website to replace the README as the project's entry point. | High |
| [New Logo](releases/new-logo.md) | Design-led branding initiative; a visual identity for the project. | Low |

## Assets

| Plan | Description | Criticality |
| --- | --- | --- |
| [Tensor Format Review](assets/tensor-format-review.md) | Audit and standardize internal tensor layouts; fix existing Camera tensor bugs as part of the pass. | High |
| [Extended EXR Support](assets/extended-exr-support.md) | Support multi-part EXR subimages, arbitrary channel counts, and optional deep EXR. | High |
| [Splats, PLY & Point-Cloud Support](assets/splats-ply-point-cloud-support.md) | Greenfield PointCloud asset type with PLY and Gaussian-splat IO. | Medium |

## Platforms

| Plan | Description | Criticality |
| --- | --- | --- |
| [Windows Build Support](platforms/windows-build-support.md) | Native Windows build via CMake, setup scripts, and removal of POSIX-only path/subprocess assumptions. | High |
| [Rocky Build Support](platforms/rocky-build-support.md) | Validate builds on Rocky Linux; primarily a CI/validation task, not a code change. | Medium |

## Code Quality

| Plan | Description | Criticality |
| --- | --- | --- |
| [Address Cataloged Bugs](code-quality/address-cataloged-bugs.md) | Fix-ordering strategy for the 17 defects in `bugs.md`, CRITICAL items first. | Critical |
| [Address Systemic Flaws](code-quality/address-systemic-flaws.md) | Fix the 5 systemic design defects in `flaws.md` — injection risk, silent write loss, enum corruption, and more. | Critical |
| [Address Critique Issues](code-quality/address-critique-issues.md) | Triage plan for the TODOs/HACKs/stubs catalogued in `critique.md`, load-bearing items first. | High |
| [Testing Expansion](code-quality/testing-expansion.md) | Grow test coverage and CI, with more VFX-specific (EXR/USD/DCC) examples. | High |
| [Asset Manager Responsibility Split](code-quality/asset-manager-responsibility-split.md) | Split `FilesystemManager`'s read/write, pipeline, publish, and build concerns into independent interfaces. | High |
| [Folder Structure Refactor](code-quality/folder-structure-refactor.md) | Resolve the fuzzy RMTC/RMTC-Core folder split into a systematic, documented rule. | Low-to-Medium |

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
