# JIRA Model Approval Frontend

## Feature Description
Integrate RMTC model approval workflows with JIRA by building a webhook/API bridge that maps JIRA issue transitions to Run approval state in RMTC. For example, when a JIRA ticket transitions from "In Review" to "Approved", a webhook fires, marking the corresponding Run's selected model/weights as "approved" in the `System`. Current state: greenfield; no JIRA integration code exists. This enables studios to gate model promotion via existing JIRA workflows, centralizing approval authority rather than managing it in separate tools.

## Criticality
Medium. Model approval is a documented roadmap item (critique.md §4, features.md "Frontends") that adds governance for production model rollout, but is not blocking inference functionality. Highly valuable for studios with established JIRA-centric workflows.

## T-Shirt Size
M. Greenfield integration: JIRA webhook listener (Flask endpoint), webhook signature validation, mapping JIRA transitions to RMTC Run/Weights approval fields, approval state tracking (add approval-related properties to Run/Weights entities if not present), and webhook retry/error logging. Likely 10-14 days; depends on web-rest-interface.md existing (for REST endpoint to accept webhooks).

## How to Implement
**Greenfield webhook architecture:**

1. **Webhook endpoint** (build on web-rest-interface.md):
   - Add Flask route `POST /jira_webhook` in `core/system/interface/rest/flask.py` (or separate module `core/system/interface/rest/jira_webhook.py`).
   - Accepts JIRA webhook payload (JSON event from JIRA server).
   - Validates webhook signature using JIRA's shared secret (per JIRA webhook docs).

2. **Webhook payload parsing** (greenfield logic):
   - Extract issue key (e.g., "PROJ-123"), transition name (e.g., "Approve"), and custom fields (e.g., RMTC Run ID or model name stored as JIRA custom field).
   - Map transition name → approval state: "Approved" → `approved=True`, "Rejected" → `approved=False`, "Pending Review" → `approved=None`.

3. **RMTC state update** (greenfield):
   - On webhook receipt, call `System.fetch(run_id)` to get the Run entity.
   - Set a new Run property `approval_status` (and optionally `approver` = JIRA user, `approval_timestamp` = now).
   - Alternatively, add a similar property to the selected Weights object if weights approval is more granular.
   - Push changes via `System.push()`.

4. **Configuration** (greenfield):
   - Store JIRA webhook secret, JIRA server URL, and RMTC System store credentials in config YAML or environment variables.
   - Flask app validates incoming webhook signatures before processing.

5. **Bidirectional notification** (optional, greenfield):
   - When a Run is approved in RMTC (via API or UI), post a comment to the corresponding JIRA issue: "Approved in RMTC by [user]" (requires JIRA API token and server URL).
   - Use Python `requests` library to call JIRA REST API.

## Considerations
- **Entity linking**: The webhook must know which Run/Weights to approve. Options:
  - Store RMTC Run ID as a JIRA custom field on the issue.
  - Use JIRA issue key as a label on the Run (add a `jira_issue_key` property to Run entity).
  - Recommend the second approach (simpler setup, no JIRA instance configuration).
- **Idempotency**: JIRA webhooks can fire multiple times; webhook endpoint should be idempotent (check if approval_status is already set before re-pushing).
- **Audit trail**: Log all webhook receipts and state changes (already handled via System.log).
- **Out of scope**: JIRA authentication/provisioning (use pre-shared webhook secret); model rollback on JIRA rejection (approval status is informational; rollback is a separate operational decision).
- **Dependencies**: Relies on web-rest-interface.md; no new Python dependencies (requests, Flask already in use).
- **Testing**: Unit tests for webhook signature validation and payload parsing; integration test with a mocked JIRA webhook payload; manual test against a real JIRA instance (or Jira Cloud sandbox).

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
