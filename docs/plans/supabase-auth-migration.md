# Supabase Auth Migration Implementation Plan

> **For agentic workers:** Use the executing-plans skill to implement task by task.
> Use subagent-driven-development only when delegation is separately selected.
> Steps use checkbox syntax for tracking; keep actual progress/evidence in the Issue/PR.

**Goal:** Replace public-demo Keycloak hosting with Supabase Auth while retaining the
Knora UI, least-privilege access and all legacy application data.

**Architecture:** The existing Next.js BFF calls hosted Supabase Auth through REST
and keeps tokens in encrypted HttpOnly cookies. FastAPI verifies Supabase JWTs,
reads provider session status and resolves Knora-owned grants and Workspace ownership.
Provider selection is explicit and supports restoring the existing Keycloak path.

**Tech Stack:** Existing Next.js 15, React 18, jose 5, FastAPI, PyJWT[crypto],
SQLAlchemy, PostgreSQL/Alembic, Vitest, pytest and Playwright. No new authentication
framework, browser SDK, Redis service or third Compose source.

**Spec:** [Supabase Auth migration](../specs/supabase-auth-migration.md).
**Decision:** [ADR 0020, proposed](../adr/0020-supabase-auth-for-public-demo.md).

## Global constraints

- Draft written 2026-11-15 against a2e466e0699663f7db5a23113c28d9940424d428.
  Approval of the migration direction is not approval of this exact file revision.
- The owner chose re-registration with legacy data retained for later transfer.
- Keep immediate demo registration, email/password sign-in, six-digit recovery OTP,
  five-minute recovery lifetime, 60-second resend minimum and eight-hour app sessions.
- Baseline grants are exactly documents:read, documents:write and questions:ask.
- No automatic email matching, owner rewrites, password import or restoration of
  revoked capabilities. No operator/delete/tool-write grant by default.
- No implementation or provider changes during this planning task. Before execution,
  record the approved plan commit/reference in a follow-up Issue/PR when publication
  is authorized. Do not reopen closed #181 or revive superseded evaluation gates.
- Use a task-owned worktree under C:\Developer\Projects\knora-agent-worktree.
  The primary checkout contains unrelated UI/theme edits and is not the edit target.
- Preserve backend 401 UNAUTHENTICATED and 403 WORKSPACE_ACCESS_DENIED /
  CAPABILITY_ACCESS_DENIED behavior; return a sanitized 503 on unavailable auth state.
- Secrets and OTP/password values never enter Git, logs, URLs or browser JSON.

## Execution sequence and review boundaries

Tasks 1–3 deliver backend identity support without enabling Supabase publicly.
Tasks 4–6 deliver the BFF/UI/recovery and verification. Task 7 performs a separately
authorized staged cutover. Review each deliverable before the next dependent task.

### Task 1: Add Knora grant persistence and read-only provider session checks

**Files**

- Create backend/src/knora/access/identity_access.py.
- Create backend/src/knora/adapters/postgres/identity_access_store.py.
- Create backend/src/knora/adapters/postgres/supabase_session_reader.py.
- Modify backend/src/knora/adapters/postgres/tables.py.
- Create backend/migrations/versions/20261115_supabase_identity_access.py.
- Create backend/test/adapters/postgres/test_identity_access_store.py.
- Create backend/test/adapters/postgres/test_supabase_session_reader.py.

**Interfaces**

```python
class IdentityAccessStore(Protocol):
    def get_or_create_baseline(self, issuer: str, subject: str) -> tuple[str, ...]: ...

class SupabaseSessionReader(Protocol):
    def is_active(self, subject: str, session_id: str) -> bool: ...
```

- [ ] Add failing real-Postgres tests: first access grants exactly the baseline;
      concurrent enrollments create one row; an existing empty/changed grant is retained.
      Use a dedicated disposable database for migration/managed-schema fixtures.
      Never create/drop synthetic auth tables in the daily or hosted database.
- [ ] Assert the essential replay contract with the public store interface:

```python
def test_existing_empty_grant_is_not_reenrolled(store, connection):
    issuer, subject = "https://demo.supabase.co/auth/v1", "test-user"
    assert set(store.get_or_create_baseline(issuer, subject)) == {
        "documents:read", "documents:write", "questions:ask"
    }
    connection.execute(
        text("UPDATE identity_access SET capabilities = '[]'::jsonb "
             "WHERE issuer = :issuer AND subject = :subject"),
        {"issuer": issuer, "subject": subject},
    )
    connection.commit()
    assert store.get_or_create_baseline(issuer, subject) == ()
```

The test fixtures instantiate PostgresIdentityAccessStore from an isolated
session_factory and a separately committed connection to that same disposable DB.

- [ ] Run that new file and inspect the failure before adding the implementation.
- [ ] Create identity_access with composite primary key (issuer, subject),
      capabilities JSONB array and created_at. INSERT ON CONFLICT DO NOTHING followed
      by a read implements enrollment; never replace existing capability values.
- [ ] Enable RLS on identity_access, add no browser policies, and revoke access from
      anon/authenticated when those roles exist. Grant the backend runtime role only
      what its application operations need. Do not assume RLS restricts the DB owner.
- [ ] The new Alembic revision initially follows 20261016_0153; recheck alembic heads
      before generation to avoid a second head if main advanced. It creates only
      Knora-owned objects. Production rollback leaves this additive table in place.
- [ ] Implement parameterized read-only checks of auth.sessions joined to auth.users:
      session ID/user ID match, nondeleted user, no current ban, session age below eight
      hours. Reject missing rows. DB errors propagate as unavailable, never as active.
      Do not register managed auth tables in Base.metadata or Alembic ownership.
- [ ] Test active, missing, wrong-user, expired, deleted and banned cases, schema/
      privilege errors, and no writes to the managed tables.
- [ ] Run the two files again and inspect executed counts and assertions.

**Check**

```powershell
python -m pytest -p no:deepeval backend/test/adapters/postgres/test_identity_access_store.py backend/test/adapters/postgres/test_supabase_session_reader.py -q
```

The command requires the disposable database binding and the existing checkout/
fixture guards. A missing schema or early return is not passing database evidence.

### Task 2: Add Supabase JWT verification through the existing identity seam

**Files**

- Modify backend/src/knora/access/identity.py to declare the small bearer protocol.
- Create backend/src/knora/access/supabase.py.
- Modify backend/src/knora/access/keycloak.py only to satisfy the shared contract.
- Modify backend/src/knora/infrastructure/settings.py and backend/src/knora/main.py.
- Modify backend/src/knora/adapters/http/routes.py and workspaces.py.
- Create backend/src/knora/adapters/http/auth.py and
  backend/test/adapters/http/test_auth_session.py.
- Create backend/test/access/test_supabase.py.
- Extend backend/test/adapters/http/test_authentication.py, test_workspaces.py,
  backend/test/access/test_workspace_identity.py and backend/test/test_settings_dotenv.py.

**Interfaces**

```python
@runtime_checkable
class BearerIdentityAuthenticator(Protocol):
    def authenticate_identity(self, authorization_header: str | None) -> Identity: ...

# SupabaseAuthenticator returns the existing Identity value object.
# Construction consumes a pinned issuer/audience/algorithm/JWKS configuration,
# IdentityAccessStore and SupabaseSessionReader from Task 1.
```

- [ ] Write failing tests with a locally generated asymmetric key and signed JWTs,
      not only a token_validator that accepts fake signatures. Mock the JWKS HTTP
      boundary. Cover wrong signature, alg, issuer, aud, exp, missing sub/session_id,
      service-role/anonymous tokens and managed-session rejection.
- [ ] Prove metadata cannot grant rights with a fake access store returning ():

```python
def test_user_metadata_cannot_grant_operator(auth_with_empty_grants, signed_token):
    raw = signed_token({
        "user_metadata": {"capabilities": ["operator:read"]},
        "capabilities": ["operator:read"],
    })
    identity = auth_with_empty_grants.authenticate_identity("Bearer " + raw)
    assert identity.capabilities == ()
```

signed_token supplies standard valid issuer/aud/exp/sub/session_id/role and signs
with the test key. auth_with_empty_grants uses that JWKS and an active session
reader; its grant store returns () regardless of the token metadata.

- [ ] Implement KNORA_AUTH_PROVIDER with keycloak as the compatibility default and
      supabase as an explicit mode. Supabase configuration is all-or-nothing:
      KNORA_SUPABASE_ISSUER, KNORA_SUPABASE_AUDIENCE=authenticated,
      KNORA_SUPABASE_JWKS_URL and KNORA_SUPABASE_JWT_ALGORITHM.
- [ ] Pin ES256 or RS256 to the verified project signing key. Never allow HS256
      using the publishable key, trust a token-supplied algorithm, or fetch a
      token-supplied JWKS URL.
- [ ] Authenticate before session/grant lookup. Then read current grants from Task 1;
      derive no Workspace authority from JWT workspace_ids or email.
- [ ] Replace all four Keycloak-only isinstance branches in routes.py and the one
      in workspaces.py with the identity seam. Keep API-key behavior, and the existing
      keycloak_authenticator create_app injection compatibility for owning tests.
      Add a clearly named bearer-authenticator injection for the new provider.
      authenticate_principal currently has no production callers; preserve its tested
      Keycloak/API-key behavior and reject its unsupported Supabase bearer use rather
      than fabricating a WorkspacePrincipal from a missing Workspace claim.
- [ ] An explicitly supplied invalid Supabase bearer fails 401; a valid API key in
      the same request must not turn it into a successful Supabase authentication.
- [ ] Add GET /v1/auth/session in a focused backend/src/knora/adapters/http/auth.py.
      It uses the same authenticate_identity path and returns issuer, subject,
      capabilities and session_id with no-store, never provider tokens.
      Add backend/test/adapters/http/test_auth_session.py.
- [ ] Regenerate the OpenAPI TypeScript client after adding this route, using the
      repository exporter. Do not edit frontend/generated/knora-openapi.ts manually.
      Run python scripts/export_openapi.py, then its --check command.
- [ ] Run the new and owning regression tests; verify unchanged 401/403 distinctions
      and authorization before any resource-store lookup.

**Checks**

```powershell
python -m pytest -p no:deepeval backend/test/access backend/test/adapters/http/test_authentication.py backend/test/adapters/http/test_auth_session.py backend/test/adapters/http/test_workspaces.py backend/test/api/test_m5_authorization_matrix.py backend/test/test_settings_dotenv.py -q
python scripts/export_openapi.py --check
```

### Task 3: Adapt BFF cookies, login, refresh and logout

**Files**

- Create frontend/lib/auth/provider.ts and frontend/lib/auth/supabase.ts.
- Modify frontend/lib/auth/session.ts and session-refresh.ts.
- Modify frontend/app/api/auth/login/route.ts, logout/route.ts, session/route.ts.
- Modify frontend/middleware.ts and frontend/app/api/auth/callback/route.ts.
- Extend frontend/tests/auth-session.test.ts, auth-refresh.test.ts,
  auth-logout-origin.test.ts and auth-callback-resolver.test.ts.
- Create frontend/tests/supabase-auth.test.ts.

**Interfaces and provider calls**

```typescript
type SupabaseTokens = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};
// New server-only module; existing KnoraSession remains the BFF return shape.
export declare function signInWithPassword(
  email: string,
  password: string,
): Promise<KnoraSession>;
export declare function registerWithPassword(
  email: string,
  password: string,
  displayName?: string,
): Promise<KnoraSession>;
export declare function refreshSupabaseSession(
  session: KnoraSession,
): Promise<KnoraSession | null>;
export declare function signOutSupabaseSession(
  session: KnoraSession,
  scope: "local" | "global",
): Promise<void>;
```

All provider calls use fixed SUPABASE_URL + /auth/v1, SUPABASE_PUBLISHABLE_KEY
in the apikey header, JSON bodies, no-store and bounded timeouts. No admin key.

| Operation    | Provider REST endpoint                           |
| ------------ | ------------------------------------------------ |
| Registration | POST /signup                                     |
| Sign-in      | POST /token?grant_type=password                  |
| Refresh      | POST /token?grant_type=refresh_token             |
| Sign-out     | POST /logout?scope=local, with user access token |

- [ ] Start with a failing response-shape test:

```typescript
import { generateKeyPair, exportJWK, SignJWT } from "jose";
import { expect, it, vi } from "vitest";
import { refreshSupabaseSession } from "@/lib/auth/supabase";
import type { KnoraSession } from "@/lib/auth/session";

async function validSupabaseRefreshFixture() {
  const now = Math.floor(Date.now() / 1000);
  const issuer = "https://auth.example.test/auth/v1";
  const subject = "ca0af038-9a87-4e0c-9dd3-2f3d47fc6bf1";
  const providerSessionId = "06f727d9-702c-426b-aabb-89c823f7d01c";
  const { publicKey, privateKey } = await generateKeyPair("ES256");
  const jwk = {
    ...(await exportJWK(publicKey)),
    kid: "auth-test",
    alg: "ES256",
  };
  const accessToken = await new SignJWT({
    role: "authenticated",
    is_anonymous: false,
    session_id: providerSessionId,
  })
    .setProtectedHeader({ alg: "ES256", kid: "auth-test" })
    .setIssuer(issuer)
    .setAudience("authenticated")
    .setSubject(subject)
    .setIssuedAt(now)
    .setExpirationTime(now + 300)
    .sign(privateKey);
  const previous: KnoraSession = {
    provider: "supabase",
    providerSessionId,
    issuer,
    subject,
    accessToken: "expired-access-token",
    refreshToken: "old-refresh-token",
    expiresAt: now - 1,
    sessionExpiresAt: now + 8 * 3600,
    sessionId: "application-session",
    capabilities: [],
    workspaceIds: [],
  };
  const tokens = {
    access_token: accessToken,
    refresh_token: "new-refresh-token",
    expires_in: 300,
  };
  vi.stubEnv("KNORA_AUTH_PROVIDER", "supabase");
  vi.stubEnv("SUPABASE_URL", "https://auth.example.test");
  vi.stubEnv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key");
  vi.stubEnv("SUPABASE_JWT_ALGORITHM", "ES256");
  vi.stubEnv("KNORA_API_URL", "https://api.example.test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      if (url.endsWith("/.well-known/jwks.json"))
        return Response.json({ keys: [jwk] });
      if (url.endsWith("/token?grant_type=refresh_token"))
        return Response.json(tokens);
      if (url.endsWith("/v1/auth/session"))
        return Response.json({
          issuer,
          subject,
          session_id: providerSessionId,
          capabilities: [],
        });
      throw new Error("Unexpected HTTP call in refresh test");
    }),
  );
  return { previous, tokens };
}

it("accepts Supabase refresh without Keycloak-only fields", async () => {
  try {
    const fixture = await validSupabaseRefreshFixture();
    const renewed = await refreshSupabaseSession(fixture.previous);
    expect(renewed?.subject).toBe(fixture.previous.subject);
    expect(renewed?.accessToken).toBe(fixture.tokens.access_token);
    expect(renewed?.sessionExpiresAt).toBe(fixture.previous.sessionExpiresAt);
  } finally {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  }
});
```

The three-field response intentionally omits id_token and refresh_expires_in.
Add a separate test where a valid-looking replacement JWT has a changed subject
or session_id; it must fail without issuing a cookie.

- [ ] Add provider?: "keycloak" | "supabase" and providerSessionId?: string to
      KnoraSession. providerSessionId holds the JWT session_id; the existing sessionId
      retains its application-cookie meaning. Existing cookies
      without provider mean keycloak only. In Supabase mode, clear legacy sessions and
      issuer-bound Workspace preferences; do not carry legacy workspaceIds forward.
- [ ] GET /api/auth/login redirects to /auth/login in Supabase mode. POST accepts
      email/password only after same-origin and request-size validation, signs in,
      validates the JWT/session, sets the existing cookie and resolves the Workspace
      through the existing resolveCurrentWorkspace helper.
- [ ] Add POST /api/auth/register/route.ts for registration. Preserve the session
      when a valid login succeeds but Workspace resolution has a transient error;
      use the existing retry surface instead of consuming credentials again.
- [ ] Bind sessionExpiresAt to the original login + 8 hours. Supabase cookies use
      this cap as max-age; do not depend on absent id_token/refresh_expires_in fields.
- [ ] Supabase getSession(true) validates the backend session even for an unexpired
      JWT. Refresh first when needed; on refresh verify issuer/subject/session_id and
      recheck backend state. Never forward an expired token.
- [ ] Exercise two independent module/app contexts using the same old refresh token,
      a late response, an invalid/revoked token, 429 and upstream timeout. Preserve the
      provider's default reuse interval; an unrecoverable stale chain requires sign-in.
      Do not invent cross-instance guarantees from the current process-local Map.
- [ ] After a successful local provider logout, clear both cookies and redirect to
      the local signed-out page. Check the next backend call is rejected even if a
      delayed response restores an old cookie. On upstream logout failure clear cookies
      but display a safe retryable failure; do not claim provider revocation.
- [ ] Reject OIDC callbacks in Supabase mode; keep the existing Keycloak callback/
      nonce/PKCE behavior covered in Keycloak mode.

**Check**

```powershell
npm --prefix frontend test -- tests/supabase-auth.test.ts tests/auth-session.test.ts tests/auth-refresh.test.ts tests/auth-logout-origin.test.ts tests/auth-callback-resolver.test.ts
```

### Task 4: Port the branded login and registration forms

**Files**

- Create frontend/app/auth/login/page.tsx and frontend/app/auth/register/page.tsx.
- Create frontend/components/auth/AuthFrame.tsx, LoginForm.tsx and RegisterForm.tsx.
- Create frontend/app/auth/auth.css.
- Reuse frontend/public/brand assets and existing fonts.
- Extend frontend/tests/auth-figma-integration.test.tsx.
- Create frontend/tests/supabase-auth-forms.test.tsx.
- Modify existing auth entry links only where needed; /api/auth/login stays stable.

- [ ] Add failing rendered tests for email/password validation, matching password
      confirmation, keyboard submission, busy state, errors and registration links.
- [ ] Port the maintained themes/knora/login/login.ftl and register.ftl layout into
      React using existing brand assets and visible copy. Keep required fields,
      autocomplete, focus, password toggle and mobile behavior. Do not embed FreeMarker.
- [ ] Treat username as display metadata. Change the login label to Email, and
      explain re-registration without suggesting old data was erased.
- [ ] Submit through Task 3's same-origin BFF routes. No direct browser Supabase
      client, provider tokens in JSON/localStorage, or service-role key.
- [ ] Check these observable UI assertions:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { RegisterForm } from "@/components/auth/RegisterForm";

it("rejects mismatched confirmation before sending registration", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<RegisterForm />);
  await user.type(screen.getByLabelText("Email"), "demo@example.test");
  await user.type(screen.getByLabelText("Password", { exact: true }), "Password-1");
  await user.type(screen.getByLabelText("Confirm password"), "Password-2");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match");
  expect(fetchMock).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});
```

Keep these accessible labels/exports as the form contract. Use the test suite's
afterEach cleanup/restore so a failed assertion also releases its mocks.

- [ ] Verify the rendered forms at 390×844 and 1440×900, including a long email,
      validation, provider unavailable, 429, tab focus and loading recovery.
      Keep current design; screenshots are evidence, not a request to redesign it.

### Task 5: Move email-OTP recovery to Supabase

**Files**

- Create frontend/app/auth/forgot-password/page.tsx,
  frontend/app/auth/reset-code/page.tsx and frontend/app/auth/new-password/page.tsx.
- Add focused recovery forms beside the auth components from Task 4.
- Create frontend/lib/auth/supabase-recovery.ts.
- Create frontend/app/api/auth/recovery/request/route.ts,
  verify/route.ts and password/route.ts.
- Create frontend/tests/supabase-recovery.test.ts and recovery-form tests.
- Preserve the existing Keycloak OTP code/tests for compatibility.

**Interfaces**

```typescript
export declare function requestRecovery(email: string): Promise<void>;
export declare function verifyRecovery(
  email: string,
  code: string,
): Promise<KnoraSession>;
export declare function updateRecoveredPassword(
  recovery: KnoraSession,
  password: string,
): Promise<void>;
```

The first two call POST /recover and POST /verify with type=recovery. The last
calls PUT /user with a recovery access token. Validate provider responses with the
same issuer/audience/signature rules. Store no raw OTP/password in application state
beyond the active request/form.

- [ ] Write tests for uniform known/unknown-email response, wrong/expired/reused OTP,
      provider 429, timeout, malformed code and a recovery cookie used as a normal login.
- [ ] Use a separate encrypted knora_recovery cookie with purpose=recovery,
      original deadline capped at five minutes, matching subject/session and fixed
      local continuation. Never use user-supplied redirect URLs.
- [ ] Missing/expired recovery state redirects to the request-code step. A valid
      code permits only password update through this BFF flow.
- [ ] Password update checks confirmation/minimum length, updates via the user
      token, revokes provider sessions with scope=global, clears both cookies and
      requires a fresh sign-in. Do not alter Task 1's grants or Workspace owners.
      Check backend session status before using an unexpired recovery cookie for a
      password update; a previously consumed flow's revoked session must fail.
- [ ] Do not retry ambiguous provider password updates or OTP consumption blindly.
      Show a safe retry/sign-in path; no success message until the provider result
      is established.
- [ ] Prepare Supabase recovery email template with {{ .Token }}, six-digit length,
      300-second expiry and 60-second resend minimum. Verify the exact current project
      settings support these values. Record template/configuration hashes without secrets.
- [ ] Prepare custom SMTP using the existing authorized sender if compatible.
      Test actual synthetic-recipient delivery only in the authorized staging phase.
      Default SMTP is not acceptance for public recovery.
- [ ] Verify resend invalidates the previous code and a consumed code cannot be used
      again against the real provider; mocks cannot establish these provider guarantees.

**Check**

```powershell
npm --prefix frontend test -- tests/supabase-recovery.test.ts tests/supabase-auth-forms.test.tsx
```

### Task 6: Integrate verification, configuration and documentation

**Files**

- Update .env.example, .env.production.template and existing Compose entry points.
- Update CONTEXT.md, docs/standards/architecture.md and ADR 0020 after design approval.
- Update docs/runbooks/public-demo-deployment.md and docs/development/feature-map.md.
- Extend scripts/prepare-figma-e2e.ps1 and its ownership/configuration tests where
  needed; preserve Keycloak profiles.
- Add frontend/tests/e2e/supabase-auth.spec.ts and the Supabase selection in the
  existing Playwright configuration/support.
- Update conftest.py partition rules/tests if new tests are not already selected.
  Reuse .github/workflows/ci.yml and existing Runtime Verification; add no third
  Compose file or separate competing verification workflow.

- [ ] Configuration matrix:

| Process               | Variables / prerequisites                                                                                                                                        |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend/BFF          | KNORA_AUTH_PROVIDER=supabase, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_JWT_ALGORITHM, SESSION_SECRET, KNORA_API_URL                                      |
| Backend               | KNORA_AUTH_PROVIDER=supabase, KNORA_SUPABASE_ISSUER, KNORA_SUPABASE_AUDIENCE, KNORA_SUPABASE_JWKS_URL, KNORA_SUPABASE_JWT_ALGORITHM, existing KNORA_DATABASE_URL |
| Supabase project      | Email/password enabled, email confirmation off for immediate demo signup, anonymous auth off, asymmetric signing, custom SMTP/recovery limits                    |
| Database runtime role | Knora grant-table access and SELECT on required auth.sessions/auth.users columns, same project as Auth                                                           |

Fail startup/preflight when Supabase mode is incomplete. Keep Keycloak default
environments functional; worker-only processes do not need frontend secrets.

- [ ] Record the changed OTP custody boundary: browser/BFF transiently handle
      recovery input; provider owns OTP storage/verification. Update the provider-
      specific architecture wording, while preserving the authorization order.
- [ ] Add an owned Supabase test mode through the existing launcher/Compose source.
      Offline CI uses local signed JWTs, fake provider HTTP and disposable DB fixtures.
      Provider-backed staging points to the explicitly authorized project and synthetic
      identities. Never run existing Keycloak-bound ownership checks against Supabase.
- [ ] Make E2E selection explicit and retries=0. Check root/login redirects do not
      loop, fresh registration, PDF/citation/refusal, two-user isolation, token expiry,
      concurrent tabs, logout, recovery and no token exposure.
- [ ] Format changed maintained frontend/shared files and Python:

```powershell
npm --prefix frontend run format
npm --prefix frontend run format:check
npm --prefix frontend run format:shared
npm --prefix frontend run format:shared:check
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
python -m ruff format .
python -m ruff format --check .
python -m ruff check .
python scripts/export_openapi.py --check
```

- [ ] Inspect all owning tests and the collection-conservation gate. Applicable
      backend, database, frontend and unchanged Keycloak contracts must produce
      readable reports with nonzero selected/executed counts.
- [ ] Run the new selected browser journey through the updated owned launcher:

```powershell
node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.figma.config.ts supabase-auth.spec.ts --reporter list,junit
```

This command is valid only after the Task 6 selector/launcher changes and
ownership checks are implemented. Use a fresh output directory for each attempt,
managed inside the existing launcher lifetime, with synthetic identities.

- [ ] Attach redacted outcomes to the exact candidate SHA. Distinguish offline
      contracts, hosted SMTP/provider checks and actual public application evidence.

### Task 7: Stage, switch and retain rollback

This task requires approval of the implementation candidate and the actual provider/
deployment changes. Do not execute it while merely writing or reviewing this plan.

- [ ] Verify the exact project reference and sanitized DB host/project mapping,
      subscription/free limits, SMTP availability, signing algorithm and read privileges.
      Inventory other Auth consumers before changing project-wide settings.
- [ ] Save current frontend/backend configuration names and rollback references
      securely; take a recoverable database backup and legacy Workspace/object inventory.
      Do not claim Supabase Free includes PITR or managed downloadable backups.
- [ ] Audit legacy retention/cleanup against F2 before proceeding. Keep old ownership
      rows, source-object references, Keycloak realm/DB and configuration recoverable.
- [ ] Apply the additive Knora migration to the authorized target, verify its head,
      table privileges and unchanged legacy counts. No auth schema migration/reset.
- [ ] Deploy the approved SHA to staging/preview with Supabase mode explicitly
      enabled on both sides. Verify A1–A11, including real SMTP, refresh concurrency and
      successful logout replay rejection. Keep secrets out of screenshots.
- [ ] Cut over backend then frontend in a bounded maintenance window. Existing
      Keycloak sessions will require re-registration/sign-in. Do not accept both
      issuers to hide a mismatched rollout.
- [ ] Check public HTTPS from a separate browser context: register, upload a text
      PDF, ask one grounded question, open its citation and ask an out-of-source
      question. Repeat isolation and recovery with synthetic accounts.
- [ ] Roll back on persistent 401/503, wrong-Workspace access, renewed revoked grants,
      broken recovery, project mismatch or data-count drift: restore both previous app
      versions/configurations, restore Keycloak provider selection, invalidate new
      cookies through provider binding and retain all new data. Do not downgrade/drop
      grant tables or import Supabase users into Keycloak.
- [ ] Explain rollback limits: restoring the prior Keycloak deployment does not
      repair its known Render memory cap, and new Supabase users/data remain inaccessible
      through Keycloak until an approved migration. If the old service is unhealthy,
      use the maintenance/unavailable surface while recovery continues.
- [ ] Only after Supabase runtime acceptance, propose stopping the old Keycloak
      process. Deletion, realm removal and old-data migration are separate work.
- [ ] Record actual URL, full SHA, CI run, provider/project, selected runtime cases,
      known limits, restart/rollback references and reviewer acceptance in the follow-up
      Issue/PR. Do not turn these documents into a progress ledger.

## Coverage and review checklist

| Spec / acceptance | Tasks      |
| ----------------- | ---------- |
| F1 / A1–A2        | 3, 4, 6, 7 |
| F2 / A9, A12      | 1, 2, 7    |
| F3 / A3–A5        | 1, 2, 6    |
| F4 / A6–A7, A10   | 2, 3, 6, 7 |
| F5 / A8           | 5, 6, 7    |
| Cost/access / A11 | 6, 7       |

Before execution, review the exact revision for policy changes: email-only login,
display-only username, provider OTP custody, explicit Supabase selection, read-only
managed session checks and legacy data retention. These are proposed details for
approval; the owner has already approved Supabase as the direction and re-registration.

## References

- [Verification contract](../runbooks/ci.md#verification-contract).
- [Agent environment](../runbooks/agent-environment.md).
- [Issue/document ownership](../agents/issue-tracker.md#issue-and-document-ownership).
- [Supabase Auth REST](https://github.com/supabase/auth).
- [Supabase JWT validation](https://supabase.com/docs/guides/auth/jwts).
- [Session rotation, logout and auth.sessions checks](https://supabase.com/docs/guides/auth/sessions).
- [Email recovery and passwords](https://supabase.com/docs/guides/auth/passwords).
- [Custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp).
- [Rate limits](https://supabase.com/docs/guides/auth/rate-limits).
- [Free plan limits](https://supabase.com/pricing).
