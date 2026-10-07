# Credential Management – No Plaintext Passwords, Better Auth Strategy

## Feature Description

Remove plaintext credential storage and implement a secrets-manager integration point. Currently, per critique.md §7, credentials are plaintext throughout: config YAML (`res/config/*.yaml`) stores DB username/password directly, `RMTC_USER`/`RMTC_PW` env vars are read with no secrets-manager hook, `Config.__str__` prints the config path with no redaction, and the store driver connection passes `(username, password)` straight through (see `src/python/lib/rmtc/system/__init__.py`). The feature is to add a secrets-manager integration point (Vault, AWS Secrets Manager, or local encrypted store), ensure credentials are never logged/printed in plaintext, and replace env-var credential passing with a token-exchange model where possible.

## Criticality

**High** — plaintext DB credentials in config files and env vars are a direct operational security risk. Any user with filesystem access to `res/config/` or log files can exfiltrate database credentials. This is table-stakes for any production deployment.

## T-Shirt Size

**M** — ~2-3 days. The actual credential refactor is straightforward (add a secrets-manager plugin point, wrap Config reads/writes, scrub logging). The main complexity is designing the fallback chain (local encrypted store, then env vars, then plaintext as a dev-only last resort) and ensuring no regressions in existing code that passes credentials around.

## How to Implement

1. **Create a secrets-manager interface:** Add `src/python/lib/rmtc/system/secrets.py` with an abstract `BaseSecretsManager` class. Methods: `get_secret(key) -> str`, `set_secret(key, value)`, `delete_secret(key)`. Implementations: `EnvSecretsManager` (reads from env), `VaultSecretsManager` (Vault HTTP API), `LocalEncryptedSecretsManager` (encrypted file store), `PlaintextSecretsManager` (existing behavior, dev-only).

2. **Inject secrets manager into Config:** In `src/python/lib/rmtc/system/__init__.py`, Config class (clarify exact line number during implementation), add a `secrets_manager` constructor parameter. When `rmtc_store.password` is accessed, check if it's a placeholder like `${VAULT:rmtc_db_password}` and resolve it via `secrets_manager.get_secret("rmtc_db_password")`, falling back to plaintext only if explicitly configured as dev-mode.

3. **Scrub credential printing:** Override `Config.__str__()` to redact all credential fields (password, token, API key) in logs. Replace `(username, password)` tuples passed to store drivers with a single session token (clarify with store layer which backends support this; may require tokenization in the driver itself).

4. **Remove plaintext from YAML/defaults:** Update `res/config/` sample configs to use secret placeholders (`${ENV:RMTC_DB_PASSWORD}` for env, `${VAULT:rmtc_db_password}` for Vault). Keep one dev-mode plaintext example for documentation.

5. **Add credential rotation helpers:** Add methods to `BaseSecretsManager` for credential rotation (update password in both secrets store and backing DB). Not required for MVP but good for future ops workflows.

6. **Tests:** Unit tests for each secrets-manager backend. Integration test: Config with Vault-backed credentials, verify password is never printed in logs. Regression test: existing plaintext flows still work in dev mode.

## Considerations

- **Backward compat:** Existing deployments with plaintext credentials in `res/config/` will break unless we detect and handle gracefully. Plan for a migration period or a dev-mode flag.
- **Vault/Secrets Manager deployment:** This is a dependency on external infrastructure. Facility must provide (or users must deploy locally, e.g., HashiCorp Vault in Docker).
- **Out of scope:** Implementing a full secrets manager (that's AWS/Vault's job); RMTC just provides the adapter.
- **Design question:** Should credentials ever be stored at all, or always be injected at runtime (fully stateless)? Clarify the security model.
- **Depends on:** Indirectly on the "permissions system" (credentials are part of auth; identity/permissions are separate but related).

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
