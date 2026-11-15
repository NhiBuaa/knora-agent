# Supabase Auth migration

Status: Draft for review. The owner approved the direction and planning, not this
written revision, implementation, account configuration, spending or cutover.
Date: 2026-11-15.
Source baseline: a2e466e0699663f7db5a23113c28d9940424d428.

## Goal and owner decisions

Replace the public demo's separately hosted Keycloak with managed Supabase Auth,
preserving the Knora experience and tenant boundaries while avoiding new compute rent.

The owner explicitly selected: "Cho người dùng đăng ký lại, vẫn giữ dữ liệu cũ để
chuyển sau". Therefore old passwords/accounts are not imported in this slice.
Legacy data is retained; access transfer is a separate future task.

The parent deployment context is
[Issue #181](https://github.com/NhiBuaa/knora-agent/issues/181), currently closed.
Its current 2026-11-05 decision removed #158/#243 as prerequisites for first public
deployment. Preserve those independent evaluation tasks and existing essential
runtime/security checks; do not reopen the parent or claim broader AI quality.
A follow-up implementation issue can link this spec and its reviewed commit when
publishing implementation work is authorized.

## Proposed user behavior

### F1. Registration and sign-in

- Visitors see the existing Knora brand/layout on the application domain.
- Use email/password for sign-in. Username, if collected on registration, is only
  display metadata, not an alternate login credential or authorization claim.
- Keep password confirmation, accessible validation, password visibility controls,
  loading feedback, retry and mobile layout.
- Registration creates a Supabase user and enters a fresh private Workspace through
  the existing resolver. Keep immediate admission after normal registration,
  matching the current realm's verifyEmail=false. Do not claim the email is verified.
- The implementation target is passwords of at least 8 characters, enforced both
  in the form and Supabase project settings. Render provider errors safely.
- Reject existing-email/wrong-password cases without exposing provider internals.
  Passwords never enter URLs, telemetry or persisted application records.

### F2. Legacy users and retained data

- Explain that users must register again after the switch. Existing passwords will
  not authenticate against Supabase automatically.
- A newly registered account does not see old Workspaces, even with the same email.
- Keep old issuer/subject ownership rows and all referenced application artifacts.
  No migration rewrites owners, truncates tables or deletes old provider resources.
- Before cutover, inspect any retention/cleanup jobs that could erase retained
  legacy data. The transition must not newly expire old Workspaces or objects.
  If an existing scheduled purge conflicts with preservation, stop cutover until a
  scoped retention measure is reviewed. Do not globally disable unrelated cleanup.
- Later transfer requires a separately reviewed operation with exact old/new
  identities, selected Workspace IDs, proof of ownership and reversible audit data.
  No email-based automatic claiming or bulk grant is part of this slice.

### F3. Capabilities and Workspace isolation

- Grant only documents:read, documents:write and questions:ask on first validated
  Supabase identity enrollment. Do not grant documents:delete, operator access or
  write-tool authority.
- Enrollment is atomic and idempotent. A persisted empty grant is a revoked account
  state, not an invitation to restore defaults.
- Sign-in, token refresh and password reset never restore removed capabilities.
- Ignore capability/role/workspace values in form data, user_metadata and browser
  state. Backend ownership checks precede resource lookup and side effects.
- Keep existing API-key contracts and the Keycloak compatibility path.

### F4. Sessions and sign-out

- Keep encrypted HttpOnly cookies, Secure in production, SameSite=Lax, no-store
  responses, same-origin mutation checks and no provider tokens in browser JSON.
- A deployment accepts its configured provider only. Switching providers invalidates
  old cookies/preferences rather than reinterpreting them.
- Local application session lifetime remains eight hours. Supabase refresh tokens
  have no refresh_expires_in field; do not manufacture a provider expiry.
- Reject invalid/revoked/banned/deleted sessions on backend requests and BFF session
  reads. A session check outage returns a retryable 503 without exposing data.
- Refresh works across independent Vercel instances using Supabase's documented
  rotation/reuse behavior, with unchanged issuer, subject and session_id.
- Sign-out defaults to the current Supabase session (scope=local). Clear the
  application and Workspace preference cookies. Delayed responses cannot authorize
  a new request after provider revocation commits.
- Already-authorized in-flight requests can complete. Failed upstream revocation
  must not be reported as confirmed provider sign-out.

### F5. Forgot password with email OTP

- Preserve the existing email → six-digit code → new password → sign-in journey.
- Supabase sends the recovery email through custom SMTP using the existing provider
  if it is compatible and authorized. Do not request new paid email infrastructure.
- Configure a six-digit OTP, five-minute validity and at least 60 seconds before
  resend. Verify current provider support before changing project settings.
- Use recovery APIs only. Recovery never creates an account, auto-links identities,
  or confers extra capabilities.
- Keep recovery tokens in a separate encrypted, five-minute HttpOnly cookie bound
  to the recovery flow; never overwrite the normal application session with them.
- Known/unknown email receives the same generic application response. Handle wrong,
  expired, consumed and superseded codes without leaking account existence.
- Provider verification/send limits are enforced. A 429 displays a retry time and
  does not trigger automatic retries or switch to another email sender.
- After password update, revoke prior provider sessions, clear recovery/application
  cookies and require a fresh sign-in. Preserve existing grants and Workspace owners.
- If the provider cannot enforce required expiry/replay/resend behavior, stop the
  recovery release and resolve that contract; do not silently replace OTP with links.

## Scope and exclusions

In scope: backend identity/grant/session validation, BFF provider adaptation, branded
auth screens, SMTP/recovery configuration, additive migration, compatible test
coverage, deployment runbook, staged cutover and rollback.

Out of scope: social sign-in, SMS/MFA, SAML, username-based authentication, importing
password hashes, automatic legacy Workspace migration, deleting Keycloak or its
data, changing RAG/providers, and paid plan upgrades.

The initial implementation retains Keycloak local/CI support. Supabase is enabled
explicitly for the public deployment; removing legacy code is not a release gate.

## Acceptance

| ID  | Observable pass condition                                                              | Evidence                                                     |
| --- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| A1  | Fresh registration → new Workspace → upload PDF → question → citation/refusal          | Hosted, exact-SHA synthetic-user journey                     |
| A2  | Existing branded screens work at mobile and desktop sizes, including errors/loading    | Rendered screenshots and browser actions                     |
| A3  | User B cannot read/mutate User A's resources, including guessed legacy Workspace IDs   | HTTP negative tests + two-user runtime check                 |
| A4  | Missing/forged/wrong-project/anonymous/service-role/expired/revoked tokens fail        | Real signed-JWT tests and HTTP status assertions             |
| A5  | Initial grants are exactly the baseline; empty/revoked grants survive sign-in/reset    | Database concurrency test + runtime negative case            |
| A6  | Refresh succeeds without Keycloak response fields and across two isolated app contexts | Contract tests + hosted concurrent tabs/expiry check         |
| A7  | Successful sign-out invalidates the session on the next request across app instances   | Session-store test + stale-cookie runtime replay             |
| A8  | Real email recovery succeeds; expired/wrong/replayed/resend-invalidated codes fail     | SMTP synthetic recipient + provider-backed recovery check    |
| A9  | Old owners/data remain; matching email does not grant old data                         | Read-only before/after inventory and isolation tests         |
| A10 | Client JSON/storage/network never exposes privileged keys or provider refresh tokens   | Redacted browser/network assertions                          |
| A11 | Keycloak/API-key regressions and applicable CI required checks pass                    | Exact-head CI and selected local test reports                |
| A12 | Backend/frontend configuration can be restored with old data intact                    | Documented rollback rehearsal; no DB downgrade in production |

## Cost, access and release gates

- Reuse the existing Supabase project only after proving it matches the configured
  Knora database. Do not create a second paid project.
- Free pricing currently includes 50,000 monthly active users; inactivity can pause
  the project. This is not a guarantee of uninterrupted production service.
- The built-in sender is restricted to team addresses and 2 emails/hour. Custom
  SMTP is mandatory before public password recovery is enabled.
- No service_role/secret admin key in frontend code. Baseline design needs only a
  publishable project key on the BFF, public JWKS and backend DB privileges.
- Select an asymmetric signing key without breaking another consumer. An existing
  legacy HS256 project is a configuration gate, not permission to rotate keys blindly.
- Preserve a backup and exact candidate/configuration references before cutover.
  Preview, migration, public cutover, eventual cleanup and spending are separate gates.
- CI/fixtures prove their executed seams only. Real SMTP, hosted refresh/logout and
  end-to-end application behavior remain necessary evidence.

Architecture proposal: [ADR 0020](../adr/0020-supabase-auth-for-public-demo.md).
Execution steps: [implementation plan](../plans/supabase-auth-migration.md).
