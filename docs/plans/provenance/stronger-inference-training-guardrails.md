# Stronger Inference & Training Guardrails

## Feature Description

Make license/permission checks load-bearing at inference and training execution time, not just at Solution-level search time. Currently `License.is_permitted()` exists (line 502 in `src/python/lib/rmtc/track/entities.py`) but is never called from the actual inference/training execution paths (`core/ops/infer/simple/inferers.py`, `core/ops/train/local/schedulers.py`). A user can find a compliant solution, but then run inference with incompatible licenses at the execution stage with no enforcement. The feature is partly runtime enforcement and partly bug-fixing: before implementing this, bugs.md #1/#2 (`License.is_active()` and `License.is_compatible()` crashes) must be fixed first.

## Criticality

**Critical** — license/permission guardrails are one of RMTC's headline "Provenance & Permissions" features (technical_notes.md §"Provenance & Permissions"). Currently the guardrails exist only at search time, not execution time. This is both a legal/IP risk (inferences can run with wrong licenses) and a core feature gap that undermines the system's stated purpose.

## T-Shirt Size

**M** — ~2-3 days. The actual runtime checks are straightforward (inject `License.is_permitted()` calls into `core/ops/infer/simple/inferers.py` and `core/ops/train/local/schedulers.py`), but requires fixing the two CRITICAL bugs first (License method crashes), comprehensive testing against all three License check types (time/party/location), and designing error messaging/fallback behavior (hard fail vs. log + skip).

## How to Implement

1. **Fix bugs.md #1/#2 first:** In `src/python/lib/rmtc/track/entities.py`, line 609 change `self.with_party(party=party)` to `self.valid_party(party=party)`, and line 612 change `self.within_jurisdiction(location=location)` to `self.in_jurisdication(location=location)`. Also fix line 576 change `self.other_license.permits` to `other_license.permits` (the method parameter, not a nonexistent attribute). Verify all three License checks (time, party, location) work correctly with a real license test case.

2. **Add permission checks to inference:** In `core/ops/infer/simple/inferers.py`, after instantiating the model and weights, call `if not model.license.is_permitted(solution.input_types + solution.output_types):` (clarify exact permission semantics during design). If check fails, either raise an exception or log and return None — decide on policy during implementation.

3. **Add permission checks to training:** In `core/ops/train/local/schedulers.py`, before training starts, check `if not (dataset.license.is_permitted(...) and model.license.is_permitted(...)):` for both the training inputs and model. Same fail-vs-log decision as inference.

4. **Add permission checks to training/inference via Solution:** Ensure `Solution.is_compliant()` (which already checks licenses at the solution level) is called before these execution paths. Make explicit whether execution-time checks are redundant safety or the primary enforcement.

5. **Tests:** Unit tests in `tests/` covering (a) inference with permitted/non-permitted licenses across all three check types (time-based, party-based, location-based), (b) training with mixed license compliance, (c) edge cases (None permissions, empty permission sets). Integration test: end-to-end workflow where an inference is blocked by a license check.

## Considerations

- **Depends on:** bugs.md #1/#2 fixes must land first (License methods are currently non-functional).
- **Design question:** Is this "hard fail" (inference/training raises) or "soft fail" (logs and returns null result)? This affects downstream code that expects a result.
- **Design question:** What does "is_permitted" mean at execution time — is it checking that the model/dataset's license permits the operation type (inference vs. training), or that all dependent licenses are compatible?
- **Out of scope:** Extending the permissions model beyond time/party/location; that's part of the "license audit" feature (separate plan).
- **Risk:** If existing workflows rely on inference with non-permitted licenses (current silent bug), this will break them visibly once fixed. May need a rollout flag or migration period.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
