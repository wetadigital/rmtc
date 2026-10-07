# License Audit – Legal Review & License Properties

## Feature Description

Audit and document the license permissions model used by RMTC's License class, and integrate legal review to ensure licenses registered in the system are fit for purpose. Currently, per technical_notes.md §"Artifacts" / "Licenses & Guardrails": "Licenses are not vetted for fit for purpose and are only indicative." The License class (`src/python/lib/rmtc/track/entities.py`, lines 490-628) defines properties for `permits`, `excludes`, `requires`, `parties`, `jurisdictions`, plus time-based validity (`start`, `finish`, `status`). The feature is part code (extending License properties, adding validation methods) and part process (vetting licenses against legal requirements, documenting which properties are mandatory vs. optional, establishing a license registry).

## Criticality

**High** — if licenses are used for guardrails (either now or after the "stronger inference guardrails" feature), they must be vetted to be legally sound and correctly represent what they claim. Running inference under an "approved" license that is actually malformed or misapplied is a business/legal risk. The system currently admits licenses are "only indicative" — this audit moves them toward being authoritative.

## T-Shirt Size

**M** — ~3-4 days. Legal review is external (1-2 days coordination) and is mostly a process task. The code side is adding schema validation to License (optional/required properties), a license registry loader (similar to module registration in `res/modules/rmtc_core.yaml`), and test coverage. No new dependencies needed.

## How to Implement

1. **Audit License properties:** Review existing License class properties (`src/python/lib/rmtc/track/entities.py`, lines 490-628). Document which properties are mandatory (e.g., a license must always have `permits` and `excludes` sets; cannot be None) vs. optional (e.g., time bounds are optional for perpetual licenses). Design validation method `License.validate()` that checks these constraints.

2. **Add property-level documentation:** Extend License docstring and property docstrings to clarify: what does "permits" mean (operation types? artifact types? rights like "train", "infer", "distribute")? How do `requires` and `excludes` interact? Document the party/jurisdiction model and use-cases (e.g., "person", "studio", "jurisdiction").

3. **Create a license registry:** Similar to modules in `res/modules/rmtc_core.yaml`, add a `res/licenses/licenses.yaml` (or extend the core modules file) with a curated set of vetted, pre-approved licenses. Include OSS licenses (Apache-2.0, MIT, GPL), media licenses (CC-BY, CC0), and internal studio policy templates. Each license entry should include party/jurisdiction constraints and vetted permission sets.

4. **Load and cache licenses:** Add a system-level registry loader (parallel to `Factory.load_module()` in `system/__init__.py`) that reads license YAML and makes vetted licenses available via a `LicenseRegistry.get(license_name)` API. Licenses created at runtime (not from the registry) are marked as "unvetted" in a new `vetted` boolean property.

5. **Legal review process:** Coordinate with legal to review the permission taxonomy (what operations/rights exist), approve the initial set of OSS + common licenses, and document which license combinations are safe for inference/training.

## Considerations

- **Process risk:** Legal review timing and scope are external dependencies. May need to start as a stub ("sample licenses for testing") and expand incrementally.
- **Out of scope:** Integrating with external license registries (e.g., SPDX); this is a first-pass internal system.
- **Design question:** Should the system enforce that all licenses used are from the vetted registry, or only warn/flag unvetted licenses?
- **Depends on:** Indirectly on bugs.md #1/#2 (License methods must work before audit makes sense), but not directly blocking.
- **Backward compat:** Existing licenses in stores may not have all new required properties. Plan for migration/validation at load time.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
