# Task 3 report — external Gmail SMTP contract

Status: complete. No Gmail credential was requested, added, or used; no live SMTP connection was attempted.

Implemented:

- Added `-ConfigurePrimarySmtp` to the guarded Keycloak migration launcher. It requires `-EnablePrimaryOtp`, validates all seven `KC_SMTP_*` values, enforces `smtp.gmail.com`, port `587`, STARTTLS and authentication, and fails closed on missing or invalid values.
- The App Password is read only from the process environment and is sent to Keycloak only as runtime realm metadata. Inspect output and snapshots continue to expose only `passwordConfigured`.
- Added focused PowerShell contract tests for missing-value failure and the Gmail/redaction source contract.
- Documented Google 2-Step Verification, App Password creation, ignored local environment injection, synthetic-recipient testing, and the prohibition on claiming delivery without credentials.
- Added `.env.gmail.local` to the ignored local-secret paths. Mailpit and isolated Figma services were unchanged.
- Hardened Keycloak 26.3.3 rollback: configured SMTP restore fails with
  `OTP_SMTP_RESTORE_SECRET_REQUIRED` unless a process-local prior secret is supplied; an empty
  SMTP map is used and verified to clear an unconfigured snapshot. SMTP `auth` and `starttls`
  values normalize the provider's string booleans.
- Primary `Bind` now applies and verifies an explicitly requested SMTP contract even when the OTP
  flow and client are already bound. The primary client contract is `http://127.0.0.1:3000`.
- Primary Compose now uses PostgreSQL JPA, a persistent Keycloak database volume, `KC_HOSTNAME`,
  file vault mode and a read-only `KNORA_PRIMARY_OTP_VAULT_PATH` mount. SMTP secrets are no longer
  passed into the Keycloak container environment.

Verification commands:

```text
.\.venv\Scripts\python -m pytest backend/test/config/test_keycloak_email_otp.py -k "smtp_opt_in or smtp_contract_source" -q
docker compose -f docker-compose.dev.yml config --quiet
git diff --check
```

Focused primary tests passed: `17 passed, 120 deselected`; the complete migration module passed
`134 passed` after updating the expected Keycloak empty-map clear semantics. Ruff, both Compose
graphs and `git diff --check` passed.

Commit range: `028be50..6c716a8` (external Gmail contract plus primary runtime/rollback hardening).

Concern: no live Gmail SMTP delivery was attempted. Operators must provide the local vault and
SMTP values to exercise the real runtime.
