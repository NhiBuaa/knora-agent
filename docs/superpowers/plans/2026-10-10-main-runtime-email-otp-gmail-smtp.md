# Main Runtime Email OTP and Gmail SMTP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bind the existing Knora email OTP provider to the primary Keycloak runtime and configure Gmail SMTP through external secrets so the Figma forgot-password flow works on port 8180.

**Architecture:** Build the primary Keycloak service from the existing provider Dockerfile. Configure the realm through an ID-bound guarded migration, with Gmail SMTP values injected at runtime and never stored in source. Keep Mailpit and the isolated OTP runtime unchanged for fixture and integration tests.

**Tech Stack:** Docker Compose, Keycloak 26.3.3, Java provider JAR, PowerShell migration scripts, Gmail SMTP with STARTTLS, Mailpit for isolated tests, Playwright and provider integration tests.

**Spec:** `docs/superpowers/specs/2026-10-10-main-runtime-email-otp-gmail-smtp-design.md`

## Global Constraints

- Never commit or print Gmail App Passwords or SMTP credentials.
- Apply realm changes only after verifying the exact `knora-dev` realm ID and owned `127.0.0.1:8180` runtime.
- Preserve and test rollback snapshots before claiming success.
- Keep OTP secrets, passwords and action URLs out of logs, screenshots and artifacts.
- Run repository verification commands and frontend formatting gates when frontend files change.

---

### Task 1: Add primary Keycloak OTP image and secret contract

**Files:**
- Modify: `docker-compose.dev.yml` primary `keycloak-dev` service.
- Modify: `docker-compose.yml` primary Keycloak service if present.
- Create: ignored local example/config documentation for SMTP variable names only.
- Test: Compose config and a source-level service graph assertion.

**Interfaces:**
- Consumes: `infra/keycloak/Dockerfile` and provider JAR build.
- Produces: primary service image with `knora-reset-email-otp.jar`, SMTP environment contract, unchanged isolated profile.

- [ ] **Step 1: Write the failing service-graph test** asserting the primary service builds from `infra/keycloak/Dockerfile`, mounts the Knora theme, exposes no secret literal, and isolated `figma-keycloak`/`figma-mail` remain unchanged.
- [ ] **Step 2: Run the graph test and confirm it fails because primary Keycloak still uses the upstream image.
- [ ] **Step 3: Change the primary service to use the existing Dockerfile build and pass SMTP settings through explicitly named environment variables or a generated realm configuration path. Keep the App Password value external and add an ignored local env example containing placeholders only.
- [ ] **Step 4: Run `docker compose config --quiet` for both production and development files and the focused graph test.
- [ ] **Step 5: Commit with `feat: package otp provider in primary keycloak runtime`.

### Task 2: Extend guarded realm migration for primary runtime

**Files:**
- Modify: `scripts/configure-keycloak-email-otp.ps1`.
- Test: `backend/test/config/test_keycloak_email_otp.py` or the existing migration test location.
- Modify: `docs/development/keycloak-theme.md`.

**Interfaces:**
- Consumes: existing `Inspect`, `Diff`, `Prepare`, `Bind`, `Restore` operations and provider metadata.
- Produces: explicit primary target mode requiring `-EnablePrimaryOtp`, exact endpoint/project checks, SMTP metadata snapshot and restore.

- [ ] **Step 1: Add RED tests for rejecting an unapproved target, refusing a mismatched realm ID, and requiring SMTP values without logging their contents.
- [ ] **Step 2: Run the focused tests and confirm the new guards fail.
- [ ] **Step 3: Implement primary target validation, snapshot fields for reset flow/email theme/SMTP settings, ordered OTP + native reset executions, and rollback that restores only the snapshot target.
- [ ] **Step 4: Add inspect/diff output that redacts SMTP passwords and marks whether the value is configured, never its value.
- [ ] **Step 5: Run focused migration tests and PowerShell script inspect/diff against a fixture realm.
- [ ] **Step 6: Commit with `feat: guard primary otp realm migration`.

### Task 3: Configure Gmail SMTP without repository secrets

**Files:**
- Modify: `docker-compose.dev.yml` and/or the runtime launcher environment contract.
- Modify: `docs/development/keycloak-theme.md`.
- Create: ignored local operator template with placeholder variables only.
- Test: secret-redaction and realm SMTP mapping tests.

**Interfaces:**
- Consumes: Task 1 environment contract and Task 2 snapshot/apply interface.
- Produces: Gmail host/port/STARTTLS/auth/from/user mapping and operator instructions.

- [ ] **Step 1: Write RED tests that detect secret literals in tracked Compose/docs and assert redacted inspect output.
- [ ] **Step 2: Run them and confirm the repository currently lacks the required contract.
- [ ] **Step 3: Add the placeholder-only configuration and document Gmail 2-Step Verification, App Password creation, TLS 587, sender address requirements, and secret storage outside Git.
- [ ] **Step 4: Add a connection check that sends only to an operator-supplied synthetic recipient and records booleans/status, never message content or credentials.
- [ ] **Step 5: Run secret scan, focused tests and Compose config.
- [ ] **Step 6: Commit with `feat: add external gmail smtp contract`.

### Task 4: Apply and verify the primary runtime

**Files:**
- Modify: `.verification` evidence only; do not commit secrets or raw email bodies.
- Test: native Keycloak browser journey and provider integration suite.
- Modify: `docs/development/figma-ui-completion-audit.md` only with fresh evidence.

**Interfaces:**
- Consumes: Tasks 1–3, operator-provided local SMTP secret, synthetic test account.
- Produces: sanitized evidence for sign-in → forgot password → email → OTP → password update → fresh sign-in and rollback.

- [ ] **Step 1: Run migration `Inspect` and `Diff`; verify target is primary `knora-dev` at `127.0.0.1:8180`.
- [ ] **Step 2: Build/restart primary Keycloak and apply the guarded OTP flow with the operator's local SMTP configuration.
- [ ] **Step 3: Verify Gmail delivery to the synthetic recipient and complete the six-digit OTP journey in desktop and mobile browser sizes.
- [ ] **Step 4: Verify malformed, wrong, expired, replayed and resend-generation cases; confirm registration and normal sign-in remain green.
- [ ] **Step 5: Restart Keycloak and repeat a fresh sign-in plus one reset continuation to verify persistence.
- [ ] **Step 6: Run rollback from the saved snapshot, verify native reset flow is restored, then re-apply only if the operator explicitly keeps the change enabled.
- [ ] **Step 7: Run `pytest`, Ruff, `docker compose config --quiet`, provider tests, and required frontend checks if any frontend files changed.
- [ ] **Step 8: Record only sanitized evidence and update Issue #157 with implementation status, tests, limitations and rollback result.
- [ ] **Step 9: Commit with `feat: enable primary keycloak email otp via gmail smtp`.
