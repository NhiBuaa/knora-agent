# Task 2 report — guarded primary realm migration

Status: implemented. No live realm was contacted and no credentials or secrets were requested.

Changes:

- Added `-EnablePrimaryOtp` with fail-closed primary target validation for
  `http://127.0.0.1:8180`, realm `knora-dev`, and Compose project `knora-dev`.
- Kept the existing isolated Figma target and opt-in behavior unchanged.
- Added SMTP inspection and snapshot metadata with only configured/passwordConfigured booleans;
  SMTP passwords are never serialized or emitted.
- Added primary snapshot validation and restore payload generation, bound to the exact realm ID.
- Preserved the ordered REQUIRED `knora-reset-email-otp`, then `reset-password` execution contract
  and existing foreign-flow rejection.
- Documented the primary migration guard in `docs/development/keycloak-theme.md`.

Verification:

- `\.venv\Scripts\python -m pytest backend/test/config/test_keycloak_email_otp.py -q` — passed (21 tests).
- `git diff --check` — passed.

Concerns:

- Primary migration remains intentionally un-applied; an operator must run it against the owned
  runtime with explicit `-EnablePrimaryOtp -Project knora-dev` and local credentials.
- SMTP password restoration is intentionally status-only; the secret is never captured by the
  snapshot, so restoring SMTP metadata does not rotate or recover a password.
