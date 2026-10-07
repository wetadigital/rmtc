# Folder Structure Refactor

## Feature Description

Make the folder structure more consistent by resolving the "fuzzy" division between RMTC and RMTC Core per technical_notes.md's own admission. Currently technology-specific code is split by precedent rather than a systematic rule; the division between general abstractions (RMTC) and concrete implementations (RMTC Core) lacks a clear separation boundary that would be obvious to new contributors. This is a mostly-mechanical move-and-import-path-fix exercise.

## Criticality

Low-to-Medium. Not a blocking issue for features, but tooling clarity and onboarding will improve significantly. A well-structured codebase is easier to extend and audit for security/correctness regressions.

## T-Shirt Size

L. Touches ~50+ files and every import that references moved paths. Roughly 3-5d of work accounting for regex-based import rewrites, verification that tests still pass after each move, and update to documentation (CLAUDE.md, technical_notes.md examples).

## How to Implement

1. **Document the rule (0.5d):** Per technical_notes.md, RMTC is "general systems and abstractions," RMTC Core is "technology-specific extensions." Write a subsection in technical_notes.md defining which directories are which, with examples. Establish a naming convention (e.g., all DCC/EXR/OIIO-specific code under `rmtc_core/` only, never under `rmtc/`).

2. **Audit current structure (1d):** Map every module in `src/python/lib/rmtc/` and `src/python/lib/rmtc_core/` to the rule. Identify misplaced directories (e.g., anything ONNX/PyTorch specific that currently lives under `rmtc/` rather than under `rmtc_core/`).

3. **Create worktree (0.5d):** Use `git worktree` to work in isolation — this refactor has a high merge-conflict risk with any concurrent feature work.

4. **Move files and rewrite imports (3-4d):** Using `find` and regex-based sed/grep, systematically move misplaced modules and rewrite all import statements. Verify per-directory: `grep -r "from rmtc\." src/ tests/` to catch imports that need updating. Likely moves:
   - Confirm no AI-framework-specific code lives outside `rmtc_core/`.
   - Confirm no test code references old paths.

5. **Run test suite (1d):** After each logical chunk of moves, run tests (`pytest tests/`) to catch any import breakage immediately.

6. **Update docs and examples (0.5d):** Refresh any code snippets in `docs/technical_notes.md` and example files that reference old import paths.

## Considerations

- **Risk:** High merge-conflict potential if active feature work is in flight. Schedule this as an isolated, lower-priority branch that lands between feature releases or between major bug-fix cycles.
- **Test coverage:** Existing test suite must pass before and after every move — a regression here can be silent (wrong module being imported due to a naming collision).
- **Out of scope:** This refactor should NOT involve renaming classes or moving code from one module to a completely different subsystem (e.g., moving `Factory` from `system/` to `track/`); it's a folder-organization pass, not an architectural redesign.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
