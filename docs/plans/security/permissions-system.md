# User/Context-Based Permissions System

## Feature Description

Implement a user identity and authorization system so that RMTC operations are gated by *who* is calling them (user/service context), not just *what* license a dataset/model has. Currently, **there is no user/auth/permissions concept anywhere in the codebase** (as noted in technical_notes.md's description of System as "an in-process trusted-caller library"). Every System operation is assumed to be called by trusted pipeline code. The feature is greenfield: design and implement a user identity/context system, integrate it into System operations, and allow facility operators to define role-based policies (e.g., "artists can infer, but only researchers can train"; "this user can only access show X, not show Y").

This is distinct from the "stronger inference guardrails" feature (which gates operations based on License permissions on the artifact itself, independent of who's calling). Here we're gating on the caller's identity and assigned roles.

## Criticality

**Medium** — A facility-grade system needs user/context separation for audit and access control. Without it, RMTC can only be deployed in highly trusted environments (closed studio networks with vetted users). Many facilities will require this before moving to production. However, it's not blocking core functionality — RMTC works today as a trusted-library.

## T-Shirt Size

**L** — ~4-5 days. This is greenfield (no existing hooks). The work is (a) design a user/role/policy schema, (b) integrate it into System initialization and operation gates, (c) add a policy engine for evaluating rules, (d) provide operator tools for defining policies. Scope increases if multi-tenant isolation (store partitioning per user/team) is included.

## How to Implement

1. **Design user/context schema (greenfield):** Create `src/python/lib/rmtc/system/identity.py`. Define:
   - `User`: identity with username, email, roles, groups.
   - `Role`: named set of permissions (e.g., "researcher", "artist", "admin").
   - `Permission`: fine-grained right (e.g., "train", "infer", "create_solution", "delete_artifact").
   - `Context`: runtime object representing the calling user/service, injected into System.
   - `Policy`: rules mapping (user/role + operation + resource_type) → allowed/denied.

2. **Inject context into System:** Modify `src/python/lib/rmtc/system/__init__.py`, System constructor to accept an optional `identity_context` parameter (a Context object). If provided, System stores it; if not, defaults to "admin" (trusts the caller). Add a method `System.get_context()` that returns the current context.

3. **Gate high-level operations:** Add permission checks to key System methods: `create_run()`, `create_inference()`, `build()`, `publish()`, etc. Check via a guard function like `self._require_permission(context, "train")` that raises `PermissionDenied` if the context's roles don't include the required permission.

4. **Policy engine and loader:** Create `src/python/lib/rmtc/system/policy.py` with a `PolicyEngine` that evaluates (user, operation, resource) tuples against a rule set. Rules loaded from YAML (similar to module registration). Example rule: `- role: researcher | operation: train | allow: true`.

5. **Admin/operator tools:** Add a system-level API for updating policies programmatically (e.g., `system.grant_permission(user="jane", role="trainer")`, `system.load_policy_file(path)`). Later, a GUI tool for policy management.

6. **Tests:** Unit tests for policy evaluation. Integration test: context with limited permissions, verify that calling a gated operation raises `PermissionDenied`. Test per-show/team isolation (if multi-tenant scope is included).

## Considerations

- **Greenfield risk:** This is a large design that doesn't yet exist. Need careful stakeholder input (studio ops, security) before implementation.
- **Scope creep:** Multi-tenant isolation (store partitioning per user/team) is tempting but can be a separate, larger feature. MVP should be single-tenant (one user at a time per System instance).
- **Audit logging:** Who did what when? This often goes hand-in-hand with identity. Consider where audit logs live (store? local file?) but defer detailed design to a separate feature.
- **Out of scope:** LDAP/AD integration, OAuth, SSO — these are deployment-time choices, not core RMTC. The system should have integration hooks but not implement the auth itself.
- **Design question:** Should System enforce permissions at the API level (fails at method call) or at the store level (filter results)? Recommend API-level for security, store-level for convenience (defer to implementation decision).
- **Depends on:** Indirectly on credentials (credentials authenticate the user; this system authorizes what they can do with that identity).

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
