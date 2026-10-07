# Address Critique Issues

## Feature Description

Systematically remediate ~8 sections of issues catalogued in `docs/review/critique.md` — a mix of explicit TODOs (75 occurrences), HACKs (11), `NotImplementedError` stubs (28), and load-bearing concerns (concurrency, credentials, CI). These range from cosmetic (unused docstrings) to critical (unimplemented default asset manager, silently-swallowed exceptions). This is a triage plan, not a rewrite; the goal is to group by severity and effort to prioritize load-bearing TODOs first.

## Criticality

High. Many of these are on critical read/write paths (§3 stubs, §5 guardrails, §6 concurrency). Addressing them unblocks production readiness and security audits.

## T-Shirt Size

XL. Spans the entire codebase; individual fixes range from 1-line (§2 HACKs) to multi-day (§4 subsystems, §6 concurrency). Estimated 8-12 dev-days total, but parallelizable: several teams can tackle independent sections simultaneously.

## How to Implement

**Triage order (load-bearing first, then effort):**

### Tier 1: Critical path (§3 stubs + §1 TODOs on inference/training)

- **§3 stubs blocking core flows:** 
  - `track/store.py:575,586` (`get_lock`/`release_lock`) — a dead API with no implementation. Remove entirely (never called anywhere). Low effort, high clarity gain.
  - `core/ops/pipeline/asset_managers/filesystem.py:111,133` (default manager raises `NotImplementedError`) — bundle with asset-manager-split plan (separate roadmap item).
  - `ops/artifacts.py:1339,1347,1355` (`Collection.tensors` setter, `Collection.structure()`) — if Collections are "not common," document as out-of-scope or implement if in-scope; decision needed. Estimated 2d if implementing.

- **§1 TODOs on artifact tensor validation:**
  - `core/ops/artifacts/torch/models.py:112` (unclear device-move semantics) — document or implement conservatively (don't move devices implicitly). 1d.
  - `core/ops/artifacts/onnx/models.py:30,57` (input/output shape derivation) — defer to ONNX subsystem review; flag as a prerequisite for #5.

### Tier 2: Concurrency & guardrails (§5, §6)

- **§5 guardrails clarity:** 
  - License/permission checks never called from inference paths (lines 161-166) — either call them in the inference scheduler or document that this is accepted light enforcement. 1d decision + implementation.
  - Immutability only checked on `delete_all` — add a write-time check on property mutation if immutable is true, or document why this is a convention-only guardrail. 0.5d.

- **§6 concurrency:**
  - GUI shares one System instance across all tool windows (lines 179-183) — no transaction/undo boundary; document or implement per-window snapshots. 2-3d if implementing.
  - GUI hardcodes LocalScheduler by direct import (lines 184-187) — refactor to use Factory resolution like the rest of the system. 1d.
  - **No CI pipeline** — covered by testing-expansion plan (separate roadmap item).

### Tier 3: Hygiene (§7 credentials, §2 HACKs)

- **§7 credentials:**
  - Plaintext passwords in YAML (lines 195-200) — add a secrets-manager hook or document this as a facility-specific concern. 2-3d if adding hook; 0.5d if just documenting.
  - Bare `except:` on version parsing (lines 201-205) — replace with specific exception handling (e.g., `except ValueError`). 0.25d.

- **§2 HACKs (11 total, mostly undocumented workarounds):**
  - Most are 1-2 line fixes if the underlying issue is understood. Examples:
    - `torch/models.py:161` — clarify what's being removed and when.
    - `oiio/image.py:128` — document or fix the OIIO workaround.
    - `objects.py:405` (datetime upcasting via ISO string) — simpler constructor or document the conversion.
  - Effort per HACK: 0.25-0.5d.

### Tier 4: Subsystems documented as unimplemented (§4)

- REST interface, C2PA watermarking, environment/package management, wall scheduler, Nuke DCC plugin — these are legitimate roadmap items, not hidden defects. Review `technical_notes.md` and README to confirm they're listed as roadmap, not marketed as shipped. 0.5d for audit.

## Considerations

- **Parallelization:** Tier 1 and Tier 2 can run in parallel if they touch different files; Tier 3 (HACKs) are mostly file-local fixes.
- **Dependencies:** Some fixes (e.g., Collection tensor methods) require design decisions; flag those as "decision gates" before assigning dev time.
- **Out of scope:** This plan addresses critique.md only; see separate plans for systemic_design_flaws.md (flaw-fixes) and bugs.md (obvious-bugs fixes).

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
