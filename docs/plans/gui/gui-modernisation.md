# GUI Modernisation

## Feature Description

Modernise the RMTC GUI's visual appearance and interaction patterns. Currently a Qt + NodeGraphQt application with dated widget styling and several undocumented workarounds (critique.md HACK list). Modernisation would update color schemes, typography, spacing, and interactive feedback to match contemporary VFX tool standards. The GUI also suffers from NodeGraphQt-specific quirks (node naming clashes, absent Qt signals from nodes, silent entity skipping) that a modernisation pass would either work around more robustly or replace.

## Criticality

Low (relative to feature-set completeness). The GUI is functionally operational; visual polish does not block core provenance, training, or inference. However, outdated appearance undermines user confidence in a pre-Alpha tool. Modernisation is worthwhile *after* the core architecture settles and the Conductor/Train Track merge concludes (both of which will reshape the GUI layout anyway).

## T-Shirt Size

XL (contingent on architectural preconditions). A pure reskin (colors, fonts, spacing) is M–L effort (2–3 weeks). However, the NodeGraphQt hacks (critique.md items 90–96) are deeply embedded: node naming mangling, boolean flags to suppress double-connection signals, three separate workarounds for silently-skipped "host" entities. Addressing these requires either: (a) a more robust Qt wrapper around NodeGraphQt (L effort, can be incremental), or (b) wholesale replacement with a custom DAG widget or an alternative graph library (XL/multi-sprint effort). A reskin alone without addressing workarounds will degrade into maintenance debt within months.

## How to Implement

1. **Prerequisite: Unify tool architecture** (from technical_notes.md):
   - Current state: "these tools are prototypes at present and likely to be unified into a more holistic solution."
   - Before modernising the UI, the Conductor/Train Track merge and the decision on whether to keep NodeGraphQt or replace it must be finalised.
   - Reskinning a prototype layout will be reworked within weeks; design first, then skin.

2. **Design system and colour palette** (if proceeding):
   - Define a consistent palette: primary, secondary, accent, greys, semantic (success/warning/error).
   - Reference `cli-docs/palette.md` (if one exists; if not, create one) with brand-neutral defaults per the dataviz skill).
   - Apply via centralized Qt stylesheets (new file `gui/common/styles.qss` or in-code via `QApplication.setStyle()` and palette setup).

3. **Widget library refresh**:
   - Update core widgets (`gui/common/widgets.py`, `gui/common/properties.py`, `gui/common/dialogs.py`) with modern spacing (8px grid), rounded corners (4–8px radius), and focus indicators.
   - Audit button/input/label styling across all tool windows (`gui/ingestion/`, `gui/training/`, `gui/traintrack/`, `gui/provenance/`).
   - Add hover states, disabled states, and loading spinners for long operations.

4. **NodeGraphQt layer improvements** (addressing critique.md HACK list):
   - **Node naming collisions** (critique.md #2): Implement a `NodeIDManager` class that maps NodeGraphQt node names to stable UUIDs and maintains a separate human-readable label. Replace all node-name lookups with UUID lookups internally.
   - **Missing Qt signals** (critique.md #3): Wrap `NodeGraphQt.BaseNode` in a thin `RMTCNode(BaseNode)` subclass that emits custom PyQt signals (`node_selected`, `node_double_clicked`, `noodle_connected`) and relays them to the graph view.
   - **Silent "host" entity skipping** (critique.md #3): Add explicit error logging in `gui/provenance/widgets.py` and `gui/ingestion/widgets.py` when entities are silently skipped; provide a "Show Warnings" button in the tool window to surface these to users.
   - **Noodle removal incomplete** (technical_notes.md): Audit the noodle-removal logic in the DAG editor; document which edge-case scenarios are not yet supported.

5. **Dark-mode support** (modern VFX standard):
   - Expose a theme toggle in the GUI menu bar (Settings → Appearance → Light/Dark).
   - Adjust all stylesheets and QPixmap loads to respect the theme (use `QApplication.palette()` to derive colors, or load separate light/dark icon sets).

6. **Incremental rollout**:
   - Phase 1: Design system + stylesheet framework (no functional changes).
   - Phase 2: Apply refresh to common widgets.
   - Phase 3: Audit and wrap NodeGraphQt layer (can be done in parallel with Phase 2).
   - Phase 4: Tool-window-specific refinements and user feedback cycles.

## Considerations

- **Architectural blocker**: Do not start visual modernisation until the Conductor/Train Track merge is decided and the GUI layout is finalized. Reskinning a layout that will change again is wasted effort.
- **NodeGraphQt viability**: Three separate HACK workarounds in `gui/provenance/` and `gui/ingestion/` suggest NodeGraphQt is at the edge of suitability for this use case. A replacement (custom Qt graphics view, or a library like `pyqtgraph` or CytoScape.js via Qt WebEngine) should be evaluated before investing in deep NodeGraphQt wrappers. This decision gates the XL estimate; if NodeGraphQt is replaced, add 2–3 weeks to the timeline.
- **Testing**: GUI testing is minimal (critique.md §6: single 116-line file, mocked NodeGraphQt). Modernisation is a good opportunity to add fixture-based Qt widget tests for the refresh changes (e.g., stylesheet application, dark-mode toggle). Not in scope for the modernisation task itself, but a follow-up.
- **Backwards compatibility**: If modernisation includes a plugin/theme system for facilities to customize colors, ensure the default theme and programmatic style API are stable enough to avoid breaking custom themes on minor updates.
- **C2PA integration placeholder**: technical_notes.md notes C2PA watermarking/signing is unimplemented. If added later, it will likely surface in the GUI as a "Signed" badge or watermark on artifacts. Leave room in the design system for such additive features without requiring a re-theme.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
