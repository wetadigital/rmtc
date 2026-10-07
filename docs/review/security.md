# RMTC — CVE/CWE Security Vulnerability Review

**Scope and Disclaimer:** This is a security vulnerability audit of the RMTC pre-Alpha codebase
as of the current branch (`RMTC-485/QueryParameters`). RMTC is unreleased
and not yet publicly deployed. **No CVE IDs have been assigned** — this is an open-source project
in development. Each finding below is classified by CWE ID (Common Weakness Enumeration) for
reference. If this codebase shipped as-is without remediation, each HIGH or CRITICAL finding would
likely warrant a CVE assignment at that time.

This review complements three prior audits: [`critique.md`](critique.md) (known TODOs/stubs),
[`bugs.md`](bugs.md) (logic defects), and [`flaws.md`](flaws.md) (systemic design issues).
This document focuses on vulnerability-class security defects: injection, deserialization,
path traversal, credential exposure, and similar OWASP/CWE-categorized risks.

---

## CWE-427 Unrestricted Upload of File with Dangerous Type via PyTorch pickle

**Affected Files:**
- `src/python/lib/rmtc/core/ops/io/torch/models.py`: line 80 (`PackageImporter.load_pickle`)
- `src/python/lib/rmtc/core/ops/io/torch/checkpoints.py`: line 58 (`torch.load(..., weights_only=False)`)

**Description:**

Two PyTorch model/checkpoint loading paths use unsafe deserialization:

1. **Line 80 (TorchPackage.read):**
   ```python
   artifact.torch_model = self._model_importer.load_pickle(
       self.model_name, self.package_name
   )
   ```
   `load_pickle` deserializes a pickle blob from a `.pt` file without `weights_only=True`

2. **Line 58 (TorchCheckpointFile.read):**
   ```python
   checkpoint_state = torch.load(
       str(uri.path), weights_only=False, map_location=device
   )
   ```
   Explicitly uses `weights_only=False` — the most permissive deserialization mode.

**Why this is a vulnerability:**

Python `pickle` and PyTorch's pickle format can execute arbitrary Python code during
deserialization. An attacker can craft a `.pt` file that, when loaded, executes system commands.
Since RMTC loads artifacts ingested from external sources (foundation models, third-party
datasets), this is a direct code-execution risk.

**Exploit Scenario:**
1. Attacker uploads a poisoned checkpoint file: `model.pt` containing pickled code that runs
   `os.system("rm -rf /")`
2. User calls `asset_manager.read([checkpoint])`
3. Checkpoint is deserialized, arbitrary code executes with the user's privileges

**Severity:** **CRITICAL**

**Current Status:** Open. PyTorch does not offer a strict `weights_only=True` for `.pt` package
files (only for `.pth`), but `weights_only=False` is the least-safe choice. The fix is to validate
the source of `.pt` files and document the risk clearly.

---

## CWE-522 Plaintext Storage of Credentials in Memory and Config

**Affected Files:**
- `src/python/lib/rmtc/track/__init__.py`: lines 74–75, 163–164
- `src/python/lib/rmtc/system/__init__.py`: line 676
- `res/config/` (all YAML config files)

**Description:**

Database credentials (username/password) are stored plaintext throughout:

1. **In-memory storage (lines 74–75, Tracking.__init__):**
   ```python
   self._username = credentials[0]
   self._password = credentials[1]
   ```

2. **Passed directly to driver (lines 163–164, Tracking.open()):**
   ```python
   connection = self._store.connect(
       username=self._username,
       password=self._password,
   )
   ```

3. **Config `__str__` exposure (line 676, Config.__str__):**
   ```python
   return f"{self._config_path}, overrides: {self._overrides}"
   ```
   If `_overrides` contains database credentials, they are exposed in log output and debug strings.

4. **Config YAML files store credentials plaintext:**
   - Example (typical but not shown in this read): `res/config/*.yaml` would contain
     `username: admin` and `password: secret123`

**Exploit Scenario:**
1. Attacker gains read access to the filesystem or memory dump
2. Credentials are visible in plaintext
3. Attacker connects directly to the database, bypassing RMTC access controls

**Severity:** **HIGH**

**Current Status:** Open. There is no encryption at rest, no secrets-manager hook (Vault, AWS
Secrets Manager), and no redaction in `__str__` / logging.

---

## CWE-434 Path Traversal Risk in FilesystemManager URI Handling

**Affected File:**
- `src/python/lib/rmtc/core/ops/pipeline/asset_managers/filesystem.py`: line 39

**Description:**

The `is_uri_supported` method checks `if not uri.path.is_relative_to(self._root)` but `self._root`
can be `None` if the manager is constructed without a `root` parameter (line 28 sets `self._root = None`).
When `self._root` is `None`, `Path.is_relative_to(None)` raises `TypeError`.

This is a blocker for rootless (unscoped) FilesystemManager instances, a documented supported
configuration. While not a direct path-traversal vulnerability, it prevents safe operation of
the intended use case.

**Severity:** **HIGH** (causes immediate crash for valid configuration)

**Current Status:** Open. The bug exists but is only triggered if the manager is used without a
root (which crashes all subsequent `is_uri_supported` calls).


---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project