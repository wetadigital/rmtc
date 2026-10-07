# Web REST Interface

## Feature Description
Harden and complete the existing Flask REST skeleton in `core/system/interface/rest/flask.py` to provide a full REST API bridge between two RMTC `System` instances (server holding the store, client submitting requests). Current state: incomplete testing code (marked in flask.py:37, 58, 108, 205, 245); stubs exist (`ops/interface.py`, `track/interface.py`) but cover only abstract base classes. This feature completes the working implementation, fixing the `Server.close()` unimplemented gap (critique.md §3), handling JSON list-ordering (critique.md §1), and enabling remote System-to-System communication.

## Criticality
High. The REST interface is a documented unimplemented subsystem (critique.md §4) and a prerequisite for both the JavaScript UI (javascript-ui.md) and JIRA integration (jira-model-approval-frontend.md). Without it, all remote access requires direct Python imports, blocking web-frontend and webhook-based integrations.

## T-Shirt Size
M. The skeleton exists; work is completing the Flask routes, fixing JSON serialization order guarantees, implementing `Server.close()`, adding authentication/token lifecycle, and comprehensive REST endpoint coverage (entity CRUD, Run selection, push/pull, sync). Likely 8-12 days; no new dependencies (Flask and requests already in use).

## How to Implement
**Build on existing stubs:**

1. **Extend `core/system/interface/rest/flask.py`**:
   - Implement `Server.close()` (currently raises `NotImplementedError` at line 265): shut down Flask app, close store connection held in `self.system.track`, clean up resource pools.
   - Expand `_setup()` to add full REST endpoint suite: `/create_model`, `/create_dataset`, `/create_solution`, `/create_run`, `/fetch_entity`, `/sync_entity`, `/push`, `/get_runs` (Run selection by Solution), `/get_best_run` (automation hook for DCC plugins).
   - Add Flask request/response middleware for authentication (JWT tokens or API keys stored in `self._tokens` set already initialized but unused at line 252).

2. **Fix JSON serialization order** (critique.md §1: "list ordering in JSON serialization isn't supported"):
   - In `JSONSerializer.serialize_object()` (flask.py:53-97), array properties currently serialize as plain JSON lists; lists in JSON are ordered, but the comment at line 58 flags a concern.
   - Implement explicit order preservation: wrap array properties in `{"__order__": [ids], "__values__": [...]}` if strict positional fidelity is required, or document and accept JSON array ordering as sufficient (simpler if store queries already preserve order).

3. **Per-request connection pooling** (already partially done):
   - `Server.open()` (line 267-275) already uses Flask's `g` context; verify connection lifecycle in teardown handler (line 292-298) properly closes connections and handles exceptions without leaking.
   - Add connection timeout and retry logic for transient store failures.

4. **Client-side enhancements** in `core/system/interface/rest/flask.py:192-229`:
   - `Client.get_entities()` exists; add `Client.fetch_entity(id)`, `Client.sync_entity(id)`, `Client.create_model(...)`, `Client.push()`, `Client.get_best_run(solution_name)`.
   - Implement request retry on 5xx errors.

5. **Registration** (optional): If multiple interface implementations are envisioned, add to `res/modules/rmtc_core.yaml` under a new `Interface` category; for now, the Flask server is instantiated directly by client code.

## Considerations
- **Authentication design**: Current stub uses tokens (line 252) but doesn't validate them. Choose between simple API-key validation (hardcoded in config), JWT (more complex but production-ready), or OAuth (deferred to facility). Document the chosen approach.
- **Connection semantics**: The server's store connection is per-request; verify this matches the store's transaction model (AGE/Neo4j may pool connections—check `core/track/store/cypher/connection.py`).
- **Serialization roundtrip**: `JSONSerializer` currently handles type names but may miss custom properties added after object creation. Verify alignment with `system/objects.py` property system.
- **Out of scope**: WebSocket support (for long-lived inference streaming); async/await refactoring (Flask is sync-only; use Gunicorn or similar for production concurrency).
- **Testing**: Unit tests for each endpoint; integration test with a real store (or mocked) to verify push/sync/fetch round-trips.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
