# Address Cataloged Bugs

## Feature Description

Fix the 17 concrete, directly-verified logic/correctness defects catalogued in `docs/review/bugs.md` — code that crashes or silently produces the wrong result on normal use. Ranges from CRITICAL (License feature dead for 2 of 3 checks, provenance corruption, silent checkpoint data loss) through LOW (cosmetic repr() crash, dead code branch). This plan is a fix-ordering strategy using the table's own severity/fix-time estimate (4 CRITICAL / 4 HIGH / 6 MEDIUM / 3 LOW, ~8.75 dev-days total).

## Criticality

Critical. Four bugs directly undermine RMTC's core pitch (License checking, provenance accuracy, training durability). Five more are high-severity (silent data corruption, feature-blocking crashes). Shipping with these unfixed risks silent data loss and legal/compliance issues.

## T-Shirt Size

L. ~8.75 dev-days estimated (per the bugs.md table), but front-loaded on the 4 CRITICAL items (~1.5d). Individual fixes are typically 1-line changes plus verification; the time is in round-trip testing (real training runs for #10, camera math for #4, GUI click-through for #8).

## How to Implement

**Fix order (CRITICAL first, then HIGH within each region, then MEDIUM/LOW):**

### CRITICAL (must land first — ~1.5d total)

1. **bugs.md #1: License.is_active() wrong methods (0.25d)**
   - File: `track/entities.py:609,612`
   - Fix: Rename `self.with_party()` → `self.valid_party()` and `self.within_jurisdiction()` → `self.in_jurisdiction()` (the methods that actually exist). Verify both are called in the test suite before and after.

2. **bugs.md #2: License.is_compatible() self.other_license (0.25d)**
   - File: `track/entities.py:576`
   - Fix: Change `self.other_license` to `other_license` (parameter, not attribute). Verify against an explicit-license test case (create a License with `explicit=True` and call `is_compatible()`).

3. **bugs.md #3: Artifact.set_solution() self-pointer (0.25d)**
   - File: `track/entities.py:753-758`
   - Fix: Change `self.solution = self` to `self.solution = solution`. Add a round-trip test: create artifact, set to a solution, verify the artifact's `.solution` property points to the solution (not back to itself).
   - **Data migration note:** Existing persisted entities may have self-pointers; flag for manual audit or write a store cleanup query (out of scope, but document it).

4. **bugs.md #10: Checkpoint optimizer/state tuple-wrapping (1d)**
   - File: `core/ops/train/torch/trainers.py:405-406` and `checkpoints.py:65-83`
   - Fix: Remove the tuple wrapping — change `(run.optimizer,)` → `run.optimizer` and `(optimizer.state_dict(),)` → `optimizer.state_dict()`. Add/update setters to reject non-dict values with type checking if needed.
   - **Verification:** Full train → checkpoint save → resume cycle. Confirm checkpoint files load correctly and training resumes without error.

### HIGH (0.75d after CRITICAL fixes)

5. **bugs.md #4: Camera.aperture setter corrupts intrinsics (0.5d)**
   - File: `ops/assets.py:414-423`
   - Fix: Instead of writing to `self.intrinsics[0/1]`, write to `self.sensor[0/1]` (the getter reads from `.sensor`). Add a camera-math test: set aperture, read it back, verify it matches. Also verify `focal_length` and `center` still work (they index the same intrinsics matrix).

6. **bugs.md #5: Camera.translation tuple() TypeError (0.25d)**
   - File: `ops/assets.py:440-446`
   - Fix: Change `tuple(a, b, c)` to `(a, b, c)`. Add a regression test: construct a Camera, read `.translation`, verify it's a 3-tuple.

7. **bugs.md #6: FilesystemManager crash on None root (0.5d)**
   - File: `core/ops/pipeline/asset_managers/filesystem.py:26-39` (lines 39 specifically)
   - Fix: Add a guard in `is_uri_supported()`: `if self._root is None: return True` (or raise, decision needed). Document the semantics of rootless config. Test: construct manager without root, call `is_uri_supported()` on various URIs.

8. **bugs.md #13: ExtractChannel.run_inverse() fabrication (1d)**
   - File: `core/ops/process/image/channels.py:123-129`
   - Fix: This is a design decision — either (a) implement proper inverse (store discarded channels), (b) raise NotImplementedError to signal non-invertibility, or (c) document as a known lossy operation. Implement (b) or (c) conservatively (safer than silent fabrication). Test: process a 4-channel image through ExtractChannel, verify that run_inverse either fails or documents its limitation clearly.

### HIGH continued (0.75d)

9. **bugs.md #7: relocate() scalar vs list (0.5d)**
   - File: `filesystem.py:97-108`
   - Fix: Change `self.exists(uri)` → `self.exists([uri])` and `self.is_published(uri)` → `self.is_published([uri])` (wrap in lists). Or refactor `exists()`/`is_published()` to accept both singular and list. Trace all call sites. Test: call `relocate()` and verify both branches execute without TypeError.

10. **bugs.md #8: Publisher pipeline_name mismatch (0.5d)**
    - File: `gui/common/widgets.py:291` vs `ops/__init__.py:111`
    - Fix: Change `pipeline_name=pipeline_name` to `name=pipeline_name` in the GUI call. Test: manually click the Publish button with a build step selected and verify it succeeds (or test via GUI automated tests if they exist).

11. **bugs.md #11: mean_epoch_loss missing .item() (0.5d)**
    - File: `core/ops/train/torch/trainers.py:312`
    - Fix: Change `mean_epoch_loss[iteration] = loss` to `mean_epoch_loss[iteration] = loss.item()`. Verify a real training run and confirm the logged metric is a float, not a 0-d tensor object.

### MEDIUM (1.5d, can be parallel)

12. **bugs.md #9: Factory description/display_name swap (0.5d)**
    - File: `system/__init__.py:1271-1277`
    - Fix: Change `display_name = str(type_info["description"])` to `description = str(type_info["description"])`. Test: load a module YAML with a description field and verify it appears in `description`, not `display_name`.

13. **bugs.md #12: AddChannel reversed logic (1d)**
    - File: `core/ops/process/image/channels.py:132-157`
    - Fix: Design the correct expand/repeat behavior (class docstring says "Repeat the tensor over to fill RGBA" but implementation extracts a channel instead). Either (a) fix to actually expand or (b) rename to `ExtractChannel2` and fix the class. Decision needed. Test: verify round-trip if invertible.

14. **bugs.md #14: Color processors mutate in place (0.5d)**
    - File: `core/ops/process/image/color.py:178-195` (and similar in StatsNormalize)
    - Fix: Change `tensor[..., :3] = ...` to `out_tensor = tensor.copy(); out_tensor[..., :3] = ...` (create new array instead of in-place mutation). Test: process a tensor, verify the original is unchanged.

15. **bugs.md #15: Property array double-conversion (0.5d)**
    - File: `system/objects.py:597-601`
    - Fix: Remove the redundant `self._convert(v)` call — only call it once. Test: assign an enum array and verify it's correct after.

16. **bugs.md #17: ONNX builder dead CPU branch (0.5d)**
    - File: `core/ops/pipeline/onnx/builders.py:111-113`
    - Fix: Change hardcoded `device = "cuda"` to `device = str(Device.CPU)` or read it from a parameter/config. Test: run export on both CPU-only and GPU machines, verify both work.

### LOW (0.5d, low urgency)

17. **bugs.md #16: Objects.__repr__() crash (0.25d)**
    - File: `system/objects.py:1235-1237`
    - Fix: Change `len.self._objects` to `len(self._objects)`. Test: construct an Objects instance and call `repr()` on it.

## Considerations

- **Ordering:** Always fix CRITICAL first in a single batch; any one unfixed will cause regressions in the test suite (licenses fail, provenance is corrupted, checkpoints break).
- **Data integrity:** Bugs #1, #2, #3 may have left corrupted data in existing stores; flag for audit. A data migration query may be needed post-fix.
- **Testing:** Round-trip tests (full train→checkpoint→resume for #10, full camera property mutation for #4) are essential; don't rely on unit tests alone.
- **Parallelization:** After CRITICAL, bugs 4-8 can be fixed in parallel; bugs 9-17 are independent once CRITICAL is done.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
