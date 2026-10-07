# RMTC — Obvious Bugs

Concrete, directly-verified logic/correctness defects — code that crashes or silently produces the
wrong result on normal, non-adversarial use. This is distinct from the other two review docs:
[`systemic_design_flaws.md`](systemic_design_flaws.md) covers architectural defects in the
persistence/type-resolution layers, and [`critique.md`](critique.md) catalogs every TODO/HACK/stub
already flagged in the code. Everything below was found by reading the implementation and confirmed
directly against source (not just reported by a search pass) — nothing here duplicates those two
docs, except item 13, which the source already flags inline but which neither prior doc captured.

| # | Bug | Severity | Fix time | Why |
|---|-----|----------|----------|-----|
| 1 | `License.is_active()` wrong methods | **CRITICAL** | 0.25d | Headline compliance feature dead for 2 of 3 checks — legal/IP risk if unnoticed; fix is a 1-line rename ×2 but must verify all 3 check paths |
| 2 | `License.is_compatible()` `self.other_license` | **CRITICAL** | 0.25d | Same feature family as #1 — crashes for every explicit license; 1-line fix, verify against an explicit-license test case |
| 3 | `Artifact.set_solution()` self-pointer | **CRITICAL** | 0.25d | Silent provenance-graph corruption with no error — bad links may already be persisted, needing a data migration; fix itself is 1 line but needs a real round-trip check |
| 4 | `Camera.aperture` setter corrupts `intrinsics` | **HIGH** | 0.5d | Silent corruption of calibration data shared with focal_length/center, propagates undetected downstream; fix must avoid regressing those neighboring properties, plus a camera-math test |
| 5 | `Camera.translation` malformed `tuple()` | **HIGH** | 0.25d | Hard crash on every access of a fundamental, widely-used Camera property; 1-line fix, add a regression test |
| 6 | `FilesystemManager` crash on `None` root | **HIGH** | 0.5d | Blocks the default/rootless config of the primary reference AssetManager entirely; fix needs a design decision on what "rootless" should mean, then multi-config testing |
| 7 | `relocate()` scalar vs list | **MEDIUM** | 0.5d | Feature fully broken (hard crash) but scoped to relocation/migration, not the core publish/read/write path; fix requires tracing every call site of `exists()`/`is_published()` first |
| 8 | GUI Publisher `pipeline_name` mismatch | **MEDIUM** | 0.5d | Loud, immediate failure confined to the GUI build→publish button; underlying API works when called correctly; fix plus a manual GUI click-through |
| 9 | Factory description/display_name swap | **LOW** | 0.5d | Cosmetic/metadata only, no functional or data-integrity impact; 1-line fix, but every existing module's displayed description needs re-checking since it's been silently wrong |
| 10 | Checkpoint optimizer/state tuple-wrapping | **CRITICAL** | 1d | Silent — save "succeeds", failure only surfaces on resume, potentially after losing GPU-hours with no earlier good checkpoint; fix needs a full train→checkpoint→resume round trip plus a plan for already-corrupted checkpoints on disk |
| 11 | `mean_epoch_loss` missing `.item()` | **MEDIUM** | 0.5d | Self-flagged; likely corrupts a training metric used for checkpoint ordering/selection, exact failure mode less certain than the CRITICAL items; 1-line fix but needs a real training run to confirm |
| 12 | `AddChannel` reversed logic | **MEDIUM** | 1d | Function inverted from its documented purpose, blast radius depends on real-world usage frequency; fix requires designing correct expand/repeat behavior, not just a typo correction |
| 13 | `ExtractChannel.run_inverse()` fabrication | **HIGH** | 1d | Silent pixel-data fabrication with a plausible-looking (wrong) result, no error to catch it; fix requires a real design decision (store discarded channels, or formally document as non-invertible) |
| 14 | Color processors mutate in place | **MEDIUM** | 0.5d | Silent, but only manifests if a caller retains a reference to the pre-processed tensor — conditional, not guaranteed; fix plus an audit of every caller relying on current aliasing |
| 15 | Property array double-conversion | **LOW** | 0.5d | Mostly harmless waste, only a real defect combined with the separate ENUM flaw; fix plus an enum-array regression test |
| 16 | `Objects.__repr__()` crash | **LOW** | 0.25d | Only breaks debugging/logging output, never actual data or pipeline operation; trivial 1-line fix |
| 17 | ONNX builder dead CPU branch | **MEDIUM** | 0.5d | Loud crash, bounded blast radius (CPU-only export) with an easy workaround (use a CUDA machine); fix plus a real export test on both CPU-only and GPU machines |

Totals to surface near the top of the doc: **4 CRITICAL / 4 HIGH / 6 MEDIUM / 3 LOW**, and
**~8.75 developer-days** total hand-fix time (quarter-day granularity, includes
review/rollout/verification, not just typing the fix).

## Licensing / provenance (`track/entities.py`) — `License` is unusable for two of its three checks

### 1. `License.is_active()` calls two methods that don't exist
**Where:** `track/entities.py:609,612`
```python
if party is not None:
    if not self.with_party(party=party):        # no such method
        return False
if location is not None:
    if not self.within_jurisdiction(location=location):   # no such method
        return False
```
The methods that actually exist are `valid_party()` (line 599) and `in_jurisdication()` (line 596,
itself a typo). Any call to `is_active(party=...)` or `is_active(location=...)` — which is how
`is_compatible()` calls it (see #2) — raises `AttributeError`, not a graceful False.

**Confidence:** Certain.

### 2. `License.is_compatible()` references a nonexistent `self.other_license`
**Where:** `track/entities.py:576`
```python
if self.explicit:
    if not set(self.other_license.permits).issubset(set(self.permits)):
```
`other_license` is the method's *parameter*, not an attribute of `self`. Every call to
`is_compatible()` on an explicit license raises `AttributeError: 'License' object has no attribute
'other_license'`.

**Confidence:** Certain.

**Combined impact:** between #1 and #2, `License.is_active()` crashes whenever a caller checks party
or location (not just time), and `License.is_compatible()` crashes for every `explicit` license.
License compatibility/activity checking is one of RMTC's headline "Provenance & Permissions"
features — as currently written it only works for the narrowest case (time-only, non-explicit
licenses).

---

## Provenance linkage

### 3. `Artifact.set_solution()` points the artifact at itself, not at the solution
**Where:** `track/entities.py:753-758`
```python
def set_solution(self, solution):
    """Add artifacts only if is_compliant"""
    if solution.is_compliant(self):
        self.solution = self  # it points backward for scaling
        return True
    return False
```
Should be `self.solution = solution`. As written, calling `artifact.set_solution(some_solution)`
silently makes the artifact its own solution, breaking the "owning solution" relationship the
`solution` property (line 734) exists to represent.

**Confidence:** Certain.

---

## Camera asset (`ops/assets.py`)

### 4. `Camera.aperture` setter writes into the intrinsics matrix instead of the sensor
**Where:** `ops/assets.py:414-423`
```python
@property
def aperture(self):
    """aperature size in mm"""
    return (self.sensor[0], self.sensor[1])

@aperture.setter
def aperture(self, value):
    self.init()
    self.intrinsics[0] = value[0]
    self.intrinsics[1] = value[1]
```
The getter reads `self.sensor`; the setter overwrites entire rows of `self.intrinsics` (the camera
matrix), which also holds focal length and principal point (see `focal_length`/`center` just above
and below it, which index into the very same rows). `camera.aperture = (35.0, 24.0)` corrupts focal
length/center and has no effect on what `aperture` reads back.

**Confidence:** Certain.

### 5. `Camera.translation` getter calls `tuple()` with three positional arguments
**Where:** `ops/assets.py:440-446`
```python
@property
def translation(self):
    """translation in mm"""
    return tuple(
        self.extrinsics[0][3],
        self.extrinsics[1][3],
        self.extrinsics[2][3],
    )
```
`tuple()` takes at most one iterable argument, not three positional values — this is a
`tuple(a, b, c)` call, not `tuple((a, b, c))`. Every read of `camera.translation` raises
`TypeError: tuple expected at most 1 argument, got 3`.

**Confidence:** Certain.

---

## Filesystem asset manager (`core/ops/pipeline/asset_managers/filesystem.py`)

### 6. `is_uri_supported()` crashes whenever the manager is constructed without a `root`
**Where:** `filesystem.py:26-39`
```python
self._root = None
if root is not None:
    self._root = Path(root)
...
def is_uri_supported(self, uri):
    ...
    if not uri.path.is_relative_to(self._root):   # self._root may be None
```
`root` is an optional constructor argument; if omitted, `self._root` stays `None`, and
`Path.is_relative_to(None)` raises `TypeError`. Any facility using a rootless (unscoped)
`FilesystemManager` — a supported configuration per the constructor's own default — crashes on the
very first URI check.

**Confidence:** Certain.

### 7. `relocate()` passes a single URI where `is_published()`/`exists()` expect an artifact/URI list
**Where:** `filesystem.py:97-108`
```python
def relocate(self, artifact, uri):
    if uri is None:
        raise RMTCException("Invalid uri")
    if self.exists(uri):                 # exists() iterates `for uri in uris`
        ...
    if self.is_published(uri):           # is_published() iterates `for artifact in artifacts`
```
Both `exists()` (line 87) and `is_published()` (line 43) are written to take an iterable of
URIs/artifacts and loop over it. `relocate()` passes a single `FileURI` object to each. `FileURI` is
not iterable, so both calls raise `TypeError: 'FileURI' object is not iterable` — `relocate()` cannot
currently run at all.

**Confidence:** Certain.

---

## GUI → System call mismatch

### 8. Publisher's "Build" step passes a keyword argument `System.build()` doesn't accept
**Where:** `gui/common/widgets.py:291` vs `ops/__init__.py:111`
```python
# widgets.py:291
result = self._system.build(entities, pipeline_name=pipeline_name)

# ops/__init__.py:111
def build(self, artifacts, name):
```
`build()`'s second parameter is named `name`, not `pipeline_name`. Clicking "Publish" with any build
pipeline selected raises `TypeError: build() got an unexpected keyword argument 'pipeline_name'`,
so the GUI's build-then-publish flow is currently non-functional whenever a build step is involved.

**Confidence:** Certain.

---

## Module/type registration

### 9. `Factory.load_module()` writes a module's `description` field into `display_name`
**Where:** `system/__init__.py:1271-1277`
```python
display_name = name
if "display_name" in type_info:
    display_name = str(type_info["display_name"])
description = ""
if "description" in type_info:
    display_name = str(type_info["description"])   # should assign to `description`
```
`description` is declared, defaulted to `""`, and then never assigned — every registered type's
`description` is permanently empty, and if a module YAML sets `description` (without also setting
`display_name`), the description text silently ends up as the displayed name instead.

**Confidence:** Certain.

---

## Training / checkpointing (`core/ops/train/torch/trainers.py`, `core/ops/artifacts/torch/checkpoints.py`)

### 10. Checkpointed optimizer and optimizer state are wrapped in a 1-tuple before being stored
**Where:** `core/ops/train/torch/trainers.py:405-406`
```python
checkpoint.torch_optimizer = (run.optimizer,)
checkpoint.torch_optimizer_state = (optimizer.state_dict(),)
```
`TorchCheckpoint.torch_optimizer`/`torch_optimizer_state` (`checkpoints.py:65-83`) are plain Python
properties with setters that store whatever they're given verbatim — no type checking or
conversion:
```python
@torch_optimizer_state.setter
def torch_optimizer_state(self, value):
    self._optimizer_state = value
```
So `_optimizer_state` ends up holding a 1-element tuple *containing* the real state dict, not the
state dict itself. `is_valid()` (line 52-53) still returns `True` (a tuple is not `None`), so the
corruption isn't caught before write. Any later `optimizer.load_state_dict(checkpoint.torch_optimizer_state)`
during checkpoint resume receives a tuple where a dict is required and raises — checkpoint-based
training resume is broken on every checkpoint this code path writes.

**Confidence:** Certain.

### 11. Epoch loss is accumulated as a live tensor, not a scalar — flagged by the code itself
**Where:** `core/ops/train/torch/trainers.py:312`
```python
running_loss += loss.item()
mean_epoch_loss[iteration] = loss  # BUG: unexpected behavior
```
The very next line correctly extracts a Python scalar via `.item()`; this line stores the raw
tensor into a (presumably pre-allocated numeric) array instead, and is already marked with an
unresolved `# BUG` comment in the source — this review is the first place it's been written up
rather than left as a stray comment. `mean_loss.append(mean_epoch_loss.mean())` (line 336) then
takes `.mean()` of an array of tensors rather than floats, so the metric that gets logged and
compared via `ORDER BY r.metric ASC` in the store is a 0-d tensor object, not the plain float the
rest of the system assumes.

**Confidence:** Certain (self-flagged in source; behavior confirmed by reading the surrounding code).

---

## Image channel processors (`core/ops/process/image/channels.py`)

### 12. `AddChannel` does the opposite of what its name, docstring, and class purpose claim
**Where:** `core/ops/process/image/channels.py:132-157`
```python
class AddChannel(Process):
    """
    [WH] -> [WHC]
    Repeat the tensor over to fill RGBA
    """
    def run(self, tensors):
        out = []
        for tensor in tensors:
            tensor = tensor[:, :, self.channel]   # extracts a channel, doesn't add one
            out.append(tensor)
        return out

    def run_inverse(self, tensors):
        out = []
        for tensor in tensors:
            tensor = tensor.squeeze(self.channel) # also reduces dims, doesn't expand
            out.append(tensor)
        return out
```
Both `run()` and `run_inverse()` reduce dimensionality; neither ever adds a channel. The class can
never do what its docstring says in either direction — it looks like the implementation was
copy-pasted from `ExtractChannel` (which does correctly reduce `[WH4] -> [WH1]`) and never adapted.

**Confidence:** Certain.

### 13. `ExtractChannel.run_inverse()` fabricates the 3 discarded channels instead of restoring them
**Where:** `core/ops/process/image/channels.py:123-129`
```python
def run_inverse(self, tensors):
    out = []
    for tensor in tensors:
        h, w, c = tensor.shape
        alpha = np.ones((w, h, 1), dtype=np.float32)
        out.append(np.concatenate([tensor, tensor, tensor, alpha], axis=2))
    return out
```
`run()` keeps exactly 1 of 4 channels and discards the other 3. `run_inverse()` can't recover them
(they're gone), but instead of raising or documenting that this is a lossy, non-invertible operation,
it silently triplicates the single retained channel into R/G/B and sets alpha to 1 — producing a
plausible-looking image that is not the original data. Any pipeline that round-trips through
`ExtractChannel` expecting `run_inverse` to be an actual inverse gets fabricated pixel data with no
warning.

**Confidence:** Likely (behavior is clearly non-invertible; whether this specific fabrication is a
"bug" vs. an undocumented deliberate simplification is judgment, but it will surprise any caller).

---

## Minor / lower-severity

### 14. Color processors mutate their input tensors in place
**Where:** `core/ops/process/image/color.py:178-195` (`LinearToSRGB.run`/`run_inverse`, and the
similar pattern in `StatsNormalize` just above it)
```python
def run(self, tensors):
    out = []
    for tensor in tensors:
        tensor[..., :3] = np.power(tensor[..., :3], self.CONVERSION_EXPONENT)
        out.append(tensor)
    return out
```
Every other processor in this module (`TrimAlpha`, `ExtractChannel`, `AddChannel`, `Shuffle`, etc.)
returns newly constructed arrays. These two mutate the caller's tensor in place and return the same
object. Any caller that keeps a reference to the pre-processed tensor (e.g. a cached "original"
asset, or a second processor branch reading the same tensor) sees it silently altered.

**Confidence:** Likely.

### 15. Array-typed property assignment converts each element twice
**Where:** `system/objects.py:597-601`
```python
for v in value:
    v = self._convert(v)
    self._array.append(self._convert(v))
```
The first conversion's result is only used as the input to a second, redundant conversion — the
computed `v` is never appended; `self._convert(v)` is called again on the already-converted value.
Mostly harmless for idempotent converters, but wasteful, and compounds the separate `ENUM`
default-collapse bug documented in `systemic_design_flaws.md` §2 for every element of an enum array.

**Confidence:** Certain (redundant call confirmed), Possible (as a behavioral defect beyond waste).

### 16. `Objects.__repr__()` cannot be called
**Where:** `system/objects.py:1235-1237`
```python
def __repr__(self):
    name = f"{self.__class__.__module__}.{self.__class__.__name__}"
    return f"{name} - ({len.self._objects})"
```
`len.self._objects` is parsed as attribute access on the `len` builtin (`len.self`), not a call to
`len(self._objects)`. Any `repr()`, log statement, or debugger inspection of an `Objects` DOM manager
raises `AttributeError: 'builtin_function_or_method' object has no attribute 'self'`.

**Confidence:** Certain.

### 17. ONNX export always targets CUDA — the CPU branch can never trigger
**Where:** `core/ops/pipeline/onnx/builders.py:111-113`
```python
device = "cuda"
if device == Device.CPU:
    device = "cpu"
torch_model.to(device)
```
`device` is hardcoded to the string `"cuda"` one line before being compared to the `Device.CPU`
enum member — a string can never equal an `IntEnum` value, so the comparison is always `False` and
the `"cpu"` branch is dead code. On a machine without CUDA, `torch_model.to("cuda")` raises; ONNX
export cannot currently be forced onto CPU through this path regardless of what device the caller
actually wants.

**Confidence:** Certain.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project