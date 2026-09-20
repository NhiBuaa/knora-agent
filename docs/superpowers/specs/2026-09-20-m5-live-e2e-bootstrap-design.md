# M5 Live E2E Bootstrap Design

**Status:** Design approved by user on 2026-09-20

## Goal

Make the isolated M5 Keycloak + Playwright environment capable of proving the approved user
and operator journeys without bypassing browser authentication, inventing backend outcomes, or
letting Playwright write internal database tables.

## Evidence that requires this change

The real authorization-code + PKCE browser session contains `workspace_id=m5-workspace` and
`documents:write`. The Next.js BFF forwards the request. FastAPI still returns 403 because
`PostgresIngestionStore.authorize_workspace` correctly requires a persisted Workspace and the
isolated environment has not provisioned that Workspace. This is a missing test control-plane
step, not an authorization weakening or frontend defect.

## Chosen design

### Test-only control-plane bootstrap

Add an idempotent M5 E2E bootstrap command, invoked by the M5 Compose readiness workflow after
database migration and before Playwright. The command uses the existing
`PostgresEvaluationWorkspaceGateway.provision_or_reuse` application seam; it does not contain
SQL, expose an HTTP endpoint, or run in the browser. It provisions exactly `m5-workspace` and
`m5-other-workspace` with fixture-only names.

The command emits only a sanitized summary of workspace identifiers and provisioning outcome.
It never emits database URLs, credentials, access tokens, cookies, or provider payloads. It is
safe to repeat and must fail clearly if migrations are absent.

### Identities and authorization

Extend only the isolated Keycloak realm with a `m5-delete-user` identity in `m5-workspace` whose
capabilities add `documents:delete`. Existing identities and their least-privilege roles remain
unchanged. Browser tests use a fresh role context for this identity and prove that deletion is an
accepted deletion request rather than a fabricated successful hard-delete.

### Authoritative answer outcomes

The bootstrap deliberately does not seed a corpus for the refusal test. Once its workspace
exists, the existing `AnswerQuestion` path receives no eligible evidence and emits its native
`REFUSAL` / `INSUFFICIENT_EVIDENCE` event. This supplies a deterministic refusal without a
provider mock, special question parameter, or frontend-owned outcome.

The existing product has no public, controlled provider-failure or interruption seam. The M5 E2E
suite must test the already-observed safe `INTERNAL_ERROR` rendering as an unavailable/failure
state, but must not claim a deterministic provider interruption. A future provider test adapter
would be a separate product design because it changes provider composition.

### Cross-workspace operator boundary

The existing public operator UI only reads the signed-in identity's selected Workspace. It has no
target-Workspace input, so no browser-only scenario can request an opaque object in another
Workspace. Keep the already-passing BFF/API cross-workspace 403 as the live authorization proof;
do not add a UI workspace switcher solely for acceptance testing.

## Data flow

```text
Compose readiness -> Alembic migration -> M5 bootstrap command
  -> PostgresEvaluationWorkspaceGateway -> persisted fixture Workspaces
  -> Keycloak real login -> Next.js BFF -> FastAPI authorization -> Playwright public UI
```

The bootstrap ends before browser execution. FastAPI remains authoritative for workspace lookup,
capabilities, ingestion, deletion requests, answering, and operator projections.

## Acceptance criteria

- Readiness provisions both fixture Workspaces idempotently through the named application seam.
- A real user can upload, view serving/ingestion state, archive/unarchive, and receive a native
  no-evidence refusal through the public UI.
- A real delete-capable user can observe a deletion request through the public UI.
- The safe question failure/unavailable UI is asserted without claiming a deterministic provider
  failure or completed answer.
- Existing non-operator and cross-workspace denials remain live passes.
- Tests and evidence contain no token, cookie, password, database URL, raw exception, or provider
  payload.

## Non-goals

- No production Workspace creation API.
- No direct table writes from Playwright or frontend code.
- No fabricated JWT, browser session, answer, citation, refusal, or provider failure.
- No operator UI Workspace selector.
- No change to production authorization, retrieval, citation, refusal, or M4 lifecycle behavior.
