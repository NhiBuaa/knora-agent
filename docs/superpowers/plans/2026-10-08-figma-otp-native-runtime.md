# Figma native email OTP runtime — Implementation Plan

> **For agentic workers:** use subagent-driven-development sequentially, with independent Spec and Quality review for each task.

**Goal:** Make the approved email → six-digit OTP → native password update → fresh sign-in flow work in the owned isolated Keycloak runtime, retaining essential security requirements.

**Spec:** [Approved Figma integration](../specs/2026-10-05-figma-ui-integration-design.md), [identity plan](2026-10-05-figma-ui-identity.md), [approved deferrals](../../development/figma-ui-deferred-work.md).

**Architecture:** Keycloak retains credential authority. The existing provider/service/JPA adapter owns recovery policy. A dedicated opt-in setup script prepares a new reset flow; ordinary harness, daily realm, built-in flows and production bindings remain unchanged. A separate test Compose override loads the production artifact and a stable file Vault secret.

**Tech Stack:** Keycloak 26.3.3, Java 21/Maven, PowerShell, Python/pytest, Next.js/Tailwind v4 and Playwright.

## Global Constraints

- Execute in the existing Figma worktree. One implementer at a time; no child agents.
- Do not retry the rejected database outage operation or an equivalent proxy/API/Docker workaround. No outage, crash, production rotation or daily resource mutation in this plan.
- Keep the existing provider policy, native POST actions, MFA credentials and BFF state/nonce/PKCE authority. No password or OTP logs, URLs, screenshots, exported bodies or fixture successes.
- No built-in flow deletion, realm reimport, user deletion, database reset or volume cleanup. Retain synthetic identities and evidence.
- Ordinary and production reset bindings stay unchanged. Only the exact owned `knora-figma-e2e` realm at loopback8380 may opt in after essential safety evidence and independent review.
- Preserve all historical evidence. New artifacts belong to `.superpowers/sdd/2026-10-08-figma-otp-native-runtime/` and Q1 `evidence/native-otp-runtime-2026-10-08/`.
- Do not commit keys or tokens. Vault secret values are generated once, retained in a verified Git-excluded local directory with restricted access, mounted read-only, and never fall back to an environment/plaintext provider configuration. Missing/invalid secrets fail closed.
- Maintained frontend changes require format → format:check → typecheck. No generated OpenAPI edits.

## Task 1: Implement guarded flow preparation and native runtime configuration

**Create:** `scripts/configure-keycloak-email-otp.ps1`, `scripts/prepare-figma-otp-runtime.ps1`, `docker-compose.figma-otp-runtime.yml`, `backend/test/config/test_keycloak_email_otp.py`.

**Modify:** `docs/development/keycloak-theme.md` only to document source commands and their acceptance boundary. Do not alter the ordinary configuration script/realm fixture or provider source.

**Interfaces:** Configuration consumes exact isolated realm representation, installed authenticator metadata and existing required-action metadata. It produces an unbound custom basic flow with ordered REQUIRED executions `knora-reset-email-otp` then native `reset-password`, plus inspect/diff/prepare/opt-in bind/restore operations. Runtime preparation consumes the existing guarded base Compose, production Dockerfile and operator-supplied Vault directory; it produces an owned test runtime without the storage probe artifact.

- [ ] Read the pinned research, actual provider and existing setup guard/test patterns. Verify Admin REST from pinned official `AuthenticationManagementResource.java`: create flow, add execution with provider/priority, list executions, update requirement and realm binding. No assumption that the registration/profile script already binds OTP.
- [ ] Add RED executable PowerShell tests using pytest subprocess and fake HTTP/Docker boundaries, following existing theme configuration tests. Cover rejection of wrong host/realm/project/ownership, missing provider, missing native UPDATE_PASSWORD, conflicting alias/execution order, default read-only inspect/diff, prepare without binding, repeat prepare no-op, bind opt-in required, saved prior binding/theme/settings and exact target/realm-ID restore. Assert no credentials in output and no built-in execution or user credential changes.
- [ ] Implement an exact isolated setup script with modes `Inspect`, `Diff`, `Prepare`, `Bind`, `Restore`; default `Inspect`. Use alias `knora-email-otp-reset` and an ownership description `Knora isolated email OTP recovery v1`. A conflicting existing alias fails closed; never overwrite a foreign flow. Prepare adds only the new flow/executions, validates both requirements/order, and does not change `resetCredentialsFlow`. Bind requires explicit `-EnableIsolatedOtp`, exact owner/project/worktree, registered provider and native UPDATE_PASSWORD enabled; save previous `resetCredentialsFlow`, `emailTheme`, `resetPasswordAllowed` and realm ID before changing only those fields. Use emailTheme `knora` and resetPasswordAllowed true. Restore verifies the same actual realm ID and restores only saved settings, retaining the custom unbound flow. Partial failures report safe error codes and preserve snapshots; no automatic destructive cleanup.

```powershell
# Read-only default and explicit opt-in remain separate operations.
.\scripts\configure-keycloak-email-otp.ps1 -Mode Inspect
.\scripts\configure-keycloak-email-otp.ps1 -Mode Prepare
# Bind is executed only by Task 2 after its essential-safety preflight.
.\scripts\configure-keycloak-email-otp.ps1 -Mode Bind -EnableIsolatedOtp
```

- [ ] Add the dedicated Compose override loading the existing production Dockerfile image, real file Vault at `/opt/keycloak/vault`, and existing themes. No test probe classes/JAR or proof secret in this graph. Exposed ports and database/volumes stay those of the base harness. A caller-supplied Vault directory is required; no default plaintext key in YAML. Keep the test override out of production/daily Compose.
- [ ] Implement runtime preparer with `-CheckConfigurationOnly` and required `-VaultPath`. Validate base configuration through the existing script, exact Compose project/working directory, loopback port ownership, actual isolated realm ID, expected Vault physical filename and valid Base64 ≥32 bytes without emitting content. Validate the Git exclusion/access boundary before reading key material. It must not generate or rotate an existing key implicitly. Check-only performs no mutations. Actual prepare builds/starts only owned Keycloak after guard success, checks discovery/provider availability and leaves reset binding unchanged. Do not run it live in Task 1.
- [ ] Add executable config guards for missing/invalid Vault/mount, foreign services, probe graph exclusion and ordinary base preservation. Validate actual Compose output with synthetic local test values; do not assert only strings that mirror implementation.
- [ ] Run focused new and existing Keycloak theme/harness tests with the available repository Python runtime; if dependencies are missing use the configured existing container/runtime rather than altering project dependencies. Run Ruff for changed Python and Compose config check. Record exact commands, exits and source-only limits; self-review and commit only the five scoped paths. Controller reviews original recorded BASE → final HEAD.

## Task 2: Prove essential storage and the real native journey

**Dependency:** independent Task 1 approval and clean tracked source. Reconcile previous storage evidence before binding; functional success must be proved, not assumed from deferred hardening.

**Create:** `frontend/playwright.figma-otp.config.ts`, `frontend/tests/e2e/figma-otp-native.spec.ts`.

**Modify:** `frontend/tests/e2e/support/figma-environment.test.ts` only if necessary to cover dedicated selection/runtime guards, and `docs/development/keycloak-theme.md`, `docs/development/figma-ui-implementation-record.md`, `docs/development/figma-ui-visual-coverage.md` for observed results. Any provider correction requires a diagnosed failure and a recorded exact-path amendment before editing.

**Interfaces:** Dedicated Playwright config uses existing `figmaEnvironment`, `figmaRuntimeEnvironment`, `openFigmaLogin`, registration and masked capture helpers, with no change to ordinary native tests. New suite consumes real SMTP delivery, production provider and native password forms; emits sanitized booleans/status/geometry, never codes/passwords/native action URLs.

- [ ] Recheck retained two-node storage/service approval and current artifact/source identity. Run meaningful existing relational concurrency/policy tests in the owned two-node proof runtime without opt-in outage/proxy/crash schedules. Use the test probe only for this bounded storage preflight; no flow binding or password update at this stage. Scope Maven selectors to supported relational transaction, account/IP budget, consume/rotation and expiry/cooldown proofs, excluding failed historical candidate characterization. Record selected/skipped cases explicitly. Any fail-closed/replay/concurrency gap blocks binding and requires diagnosis; deferred deployment tests do not replace these checks.
- [ ] Remove proof-only exposure through starting the separately guarded production-artifact runtime graph, keeping data intact. Provision one stable random test key in an explicitly Git-excluded owner-restricted Vault directory for the actual realm ID. Record only filename/hash of configuration metadata, not key/hash of key. Never replace an existing valid key. Confirm the probe endpoint is unavailable, discovery and provider registration work, then Prepare and Bind the isolated flow with saved prior settings. This opt-in follows the owner's approved function scope and deferral boundary; ordinary/daily/production configuration is not enabled.
- [ ] Write a native browser case using a fresh synthetic registered account and a fresh recovery browser context: Forgot Password → `#knora-reset-email-form` → real Mailpit six-digit code → wrong-code rejection → correct verify → native `#kc-passwd-update-form` → real policy/confirmation error → strong new password → completion. Inspect actual template IDs before using them. All sensitive POST destinations must remain exact Keycloak origin; API/application endpoints must never receive code/password. Clear OTP before capture; mask populated credential fields.
- [ ] Click the actual trusted completion Sign in CTA with an existing SSO context. Require native fresh credential form (`prompt=login`), new BFF state/nonce/PKCE by boolean comparison, reject old password, accept new password and land in exact owned Workspace. Never assert direct Workspace landing from OTP verification or completion CTA alone.
- [ ] Add bounded native safety cases for malformed/wrong code, replay after consume, resend before cooldown (server-side with JS bypass), allowed resend after actual cooldown and previous-generation rejection, and unknown-account uniform challenge without delivery. Use storage/service proofs for five-minute expiry/account-IP cross-session limits where waiting or faking native time would obscure the tested contract; disclose which layer proves each invariant. No production fault injection.
- [ ] Enroll a native TOTP credential only on the created synthetic identity through supported native setup; prove credential ID/type preserved after password recovery and a new login still requires TOTP. Preserve browser flow MFA requirements. If setup cannot be safely demonstrated, leave native MFA acceptance open and runtime recovery unbound after returning to saved settings; do not claim security acceptance.
- [ ] Run the exact new native suite at supplied desktop1440×960 and mobile390×844 adaptation where applicable. Capture empty email/OTP, rejected OTP, native password and detached completion states under the new evidence directory and inspect them against existing direct MCP source. Geometry differences become concrete follow-up tasks; browser success does not imply parity.
- [ ] Restore saved binding after the bounded journey while essential safety/native review is pending. Keep provider/key/data/tests intact. Record restoration read-back, successful and missing invariants, source/destination transition evidence and deployment hardening Issue #152. Record any remaining safe-use restriction explicitly.
- [ ] Run format → format:check → typecheck and affected covering journey after final edits. Update only observed ledger rows and produce sanitized report/evidence; commit exact scoped paths and request independent Spec/Quality review. Final whole-head verification and whole-design review follow after remaining desktop/function gaps are closed.

## Gate ruling after approved deferrals

The owner confirmed Issue #152's boundary: SMTP/database outage, deployment restart/rotation,
CSP and upgrade/runbook proof can follow functional acceptance. This supersedes the earlier
plan's physical-outage prerequisite **for isolated functional testing only**. The rejected
operation remains prohibited. Essential commit/consume/expiry/budget/concurrency and privacy
behavior must pass before connecting native password authority; production remains disabled.
If current evidence contradicts safety, do not bind. This is not acceptance of the whole Figma
design or authorization to deploy.
