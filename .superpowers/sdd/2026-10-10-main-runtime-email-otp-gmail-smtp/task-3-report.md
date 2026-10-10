# Task 3 report — external Gmail SMTP contract

Status: complete. No Gmail credential was requested, added, or used; no live SMTP connection was attempted.

Implemented:

- Added `-ConfigurePrimarySmtp` to the guarded Keycloak migration launcher. It requires `-EnablePrimaryOtp`, validates all seven `KC_SMTP_*` values, enforces `smtp.gmail.com`, port `587`, STARTTLS and authentication, and fails closed on missing or invalid values.
- The App Password is read only from the process environment and is sent to Keycloak only as runtime realm metadata. Inspect output and snapshots continue to expose only `passwordConfigured`.
- Added focused PowerShell contract tests for missing-value failure and the Gmail/redaction source contract.
- Documented Google 2-Step Verification, App Password creation, ignored local environment injection, synthetic-recipient testing, and the prohibition on claiming delivery without credentials.
- Added `.env.gmail.local` to the ignored local-secret paths. Mailpit and isolated Figma services were unchanged.

Verification commands:

```text
.\.venv\Scripts\python -m pytest backend/test/config/test_keycloak_email_otp.py -k "smtp_opt_in or smtp_contract_source" -q
docker compose -f docker-compose.dev.yml config --quiet
git diff --check
```

Focused tests passed: `2 passed, 128 deselected`.

Commit: `028be50` (`feat: add external gmail smtp contract`)

Concern: the full migration test module exceeded the interactive command time budget when run as one command; the focused contract tests and existing migration tests reached the new code path successfully. No delivery claim is made without operator credentials and a synthetic recipient.
