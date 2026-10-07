# JavaScript UI

## Feature Description
Build a thin web frontend (HTML/CSS/JavaScript or React) that sits on top of the REST API from web-rest-interface.md, enabling web-browser-based access to RMTC system operations (model browsing, Run inspection, solution/inference creation). Current state: greenfield; no existing web code anywhere in the repo. The UI would mirror the property-browsing and provenance-tracing features of the existing Qt GUI (gui/common/properties.py, gui/provenance/widgets.py) but in a browser, consuming REST endpoints instead of direct Python System access.

## Criticality
Medium. A web frontend is a convenience feature for facility staff and external stakeholders to inspect models and training progress without Python/Qt dependencies. Unblocks remote access but is not required for core system function (the existing Python API and Qt GUI still work).

## T-Shirt Size
L. Greenfield frontend: UI scaffolding (React or vanilla JS), REST client integration, entity property renderer, provenance DAG visualization (requires a graph library like Cytoscape or D3), solution/Run search and filtering, form builders for model/dataset creation, and styling. Likely 20-25 days; adds a JavaScript build step (webpack/Vite) and a node_modules dependency tree.

## How to Implement
**Greenfield web architecture:**

1. **Frontend scaffold** (greenfield):
   - Create `web/frontend/` with standard structure: `src/`, `public/`, `package.json`.
   - Choose framework: React for component reusability and ecosystem maturity, or vanilla JS for minimal dependencies (recommend React).
   - Build tooling: Vite (faster than webpack for dev iteration).

2. **REST client layer** (`web/frontend/src/api/rmtcClient.js` or similar):
   - Thin wrapper around `fetch()` that calls the Flask server endpoints from web-rest-interface.md.
   - Base URL from environment variable or config (so frontend can point to different servers: local dev, staging, prod).
   - Handles authentication tokens (reads from localStorage or session storage, attaches to requests).

3. **Data shape** (per technical_notes.md "Object Properties" section):
   - Frontend receives and renders RMTC's property model: Object, Bool, Number, Integer, String, Datetime, URI, Version, Type, Enum.
   - Serializes them back via REST client using the same structure as `JSONSerializer` in flask.py.
   - No new data model needed—reuse existing property type definitions via REST JSON schema.

4. **Core components** (`web/frontend/src/components/`):
   - `EntityBrowser`: Lists and filters models/datasets/solutions by name/type.
   - `PropertyEditor`: Renders editable form from entity properties (maps PropertyType to HTML input/select).
   - `ProvDAG`: Graph visualization of IN/OUT provenance relationships (use Cytoscape.js; show sources/derivatives for selected entity).
   - `RunSelector`: Dropdowns to choose Solution and display best Run auto-selected.
   - `InferenceForm`: Simple form to select a Solution and trigger inference (POST to `/get_best_run` and then launch inference).

5. **Server-side hosting** (greenfield):
   - Flask server can serve the frontend static build via `Flask.static_folder` (optional; alternatively, host separately on nginx/Apache).
   - Or use a separate Node.js express server if tight Flask integration is undesirable.

## Considerations
- **Provenance visualization**: A full DAG can be deep/wide for complex projects. Implement interactive zoom/pan and lazy-load derivatives (don't fetch entire tree upfront).
- **Authentication**: Inherit token handling from REST API; frontend stores token in localStorage (consider CSRF/XSS mitigations if adding forms).
- **Out of scope**: Real-time WebSocket updates (poll REST endpoints instead); offline mode; advanced training job scheduling UI (defer to CLI or future specialized tool).
- **Dependencies**: React (or framework), Cytoscape.js or D3 for DAG rendering, axios or fetch for HTTP (recommend fetch + wrapper). No heavy dependencies on RMTC Python code (clean separation).
- **Testing**: Component unit tests (Jest + React Testing Library), integration tests with mocked REST API, E2E tests with Playwright pointing to a test server.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
