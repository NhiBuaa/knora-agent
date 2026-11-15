# ADR 0020: Supabase Auth for the public demo

Status: Proposed — implementation and cutover are not authorized by this document.
Date: 2026-11-15.

## Context

The public demo currently uses a separately hosted Keycloak service. Its observed
512 MB Render memory exhaustion interrupts authentication. The owner chose managed
Supabase Auth to remove that service's hosting requirement, prioritizing free usage.
The owner also chose re-registration, retaining existing data for a later migration.

This proposal changes the Keycloak-specific authentication rule in
[Architecture Standard](../standards/architecture.md#authentication-and-workspace-authorization)
and the OTP custody rule in
[the existing OTP design](../specs/2026-10-10-main-runtime-email-otp-gmail-smtp-design.md).
Those rules must be updated with the implementation; this draft does not silently
supersede them.

## Proposed decision

1. Select exactly one browser identity provider per deployment: Keycloak or Supabase.
   Keep the existing Keycloak local/CI path initially for compatibility and rollback.
   Never fall back from invalid Supabase authentication to another identity provider.
2. Keep browser authentication behind the existing Next.js BFF. Use server-side fetch
   to Supabase Auth REST endpoints, existing jose JWT verification and the encrypted
   HttpOnly application cookie. No browser Supabase SDK or tokens in localStorage.
3. Backend Supabase verification accepts a pinned project issuer, audience
   authenticated, an explicitly configured asymmetric signing algorithm, a valid user
   subject and session_id. It rejects anonymous, service-role and malformed tokens.
   Do not reuse Keycloak's RS256-only claims mapping or trust user_metadata.
4. Persist Knora capability grants separately from the provider. An atomic
   insert-if-absent grants the fixed demo baseline on a validated user's first use;
   subsequent reads preserve revoked or empty grants. Knora remains the authority for
   Workspace ownership, keyed by issuer and subject.
5. Read Supabase-managed auth.sessions and auth.users through a narrowly scoped,
   read-only adapter to reject revoked, deleted, banned or over-eight-hour sessions.
   No Knora migration owns, changes or deletes either managed table. Production
   preflight must prove the application DB belongs to the configured Auth project
   and the runtime DB role has the necessary SELECT privilege.
6. Supabase's rotation/reuse protocol coordinates refresh across Vercel instances.
   Any in-process deduplication is an optimization only. Revalidate the backend
   session after refresh, including when returning a still-unexpired token.
   A transient verification failure fails closed with a retryable 503.
7. Reproduce the existing branded login/registration/reset screens inside Next.js.
   Sign-in uses email/password; a supplied username is display metadata only.
   Registration remains immediately usable: email confirmation is disabled for this
   demo, matching public-demo-realm.json. Recovery proves email possession separately.
8. Supabase owns OTP generation, expiry and consumption. The browser submits OTP and
   password through the BFF transiently; neither values nor provider response bodies
   containing tokens enter logs, traces, storage or browser analytics.
9. Keep legacy identities, Workspaces, documents, objects, vectors and history intact.
   A re-registered user gets a new identity and Workspace. Never link by matching email.
   A future transfer needs explicit source/destination identity proof and approval.

## Alternatives

| Option                                 | Trade-off                                                                                                                         |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| BFF + Supabase REST, proposed          | Reuses the current cookie/API boundaries and installed libraries; requires provider-specific session and recovery code            |
| Supabase SDK-based session integration | Official helpers simplify some integration, but add dependencies and require reconciling their session ownership with Knora's BFF |
| Supabase federated through Keycloak    | Keeps the Keycloak process and its RAM requirement, so does not remove the deployment blocker                                     |

## Consequences and limits

Supabase Free currently includes 50,000 monthly active users, and free projects
can pause after a week without activity. Default SMTP cannot serve arbitrary public
users; custom SMTP is required for recovery. This change removes Keycloak compute
cost, not the limits or costs of Render, Vercel, email, storage or inference.

The auth.sessions read adds a database check to authenticated requests and couples
this deployment mode to the same Supabase project. The adapter is isolated and
tested against the deployed managed schema before cutover. If the privilege or
schema check fails, stop cutover; do not widen credentials or weaken verification.

The logout guarantee applies to requests authorized after revocation commits.
Already-running requests may finish. A failed upstream logout clears browser cookies
but does not establish provider revocation; report the retryable failure.

## Sources

Checked 2026-11-15:

- [Supabase JWTs](https://supabase.com/docs/guides/auth/jwts).
- [Sessions, rotation and checking auth.sessions after sign-out](https://supabase.com/docs/guides/auth/sessions).
- [Supabase Auth REST API](https://github.com/supabase/auth).
- [Custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp).
- [Pricing](https://supabase.com/pricing).

Product requirements: [Supabase Auth migration](../specs/supabase-auth-migration.md).
Execution steps: [implementation plan](../plans/supabase-auth-migration.md).
