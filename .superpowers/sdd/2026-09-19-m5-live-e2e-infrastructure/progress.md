# SDD ledger — plan: docs/superpowers/plans/2026-09-19-m5-live-e2e-infrastructure.md

## Pre-flight plan scan

| Scope | Files/interfaces checked | Finding | Ruling |
|---|---|---|---|
| Task 1 ↔ Task 2 | Compose overlay and local Keycloak URLs consumed by `m5E2EEnvironment()` | Task 1 produces the issuer/ports that Task 2 configures; no contradictory port or service name | None required; Task 2 must use the exact `8180` issuer from Task 1 |
| Task 2 ↔ Task 3 | `playwright.config.ts`, `environment.ts`, `npm run test:e2e` | Task 3 depends on Task 2's base URL and runner; discovery remains isolated from Vitest | None required; Task 3 runs only after Task 2's list/typecheck gate |
| Task 3 ↔ Task 4 | `support/auth.ts`, `loginAs`, `newRoleContext` | Task 4 extends the helper but does not redefine identity names | None required; preserve the four identity literals exactly |
| Task 4 ↔ Task 5 | Structured scenario result and evidence schema | Task 4 supplies public outcomes; Task 5 appends sanitized records only after live execution | None required; no credentials/tokens/raw provider payloads may cross the boundary |
| Task 1 | Overlay, realm, PowerShell validation | Test fails before files exist and becomes independently runnable after readiness | Agrees with spec; no production Compose change |
| Task 2 | Package scripts, Playwright config, environment helper | RED test covers dependency/script/helper and GREEN gate lists only e2e specs | Agrees with spec; Vitest discovery stays untouched |
| Task 3 | Real login helper and auth spec | Browser assertions use public behavior and separate contexts | Agrees with spec; no fabricated sessions |
| Task 4 | User/operator specs and auth extension | Scenarios cover accepted M5 states and negative cases through public UI | Agrees with spec; direct internal-table seeding is prohibited |
| Task 5 | JSONL/final evidence and full gates | Evidence is append-only and commit-bound | Agrees with spec; blocked infrastructure remains blocked rather than pass |

## Rulings

- Task 3 missing-session assertion: preserve the approved M5 behavior of rendering an explicit
  `No workspace is available for this session.` state rather than requiring a redirect to login.
  The design says route guards improve navigation but does not require a redirect, while it does
  require explicit unavailable semantics. Cost if wrong: unauthenticated navigation will remain
  a safe unavailable state rather than forcing sign-in; a future product decision can add a guard
  with a separate approved design.
- Task 3 API dependency: extend the M5-specific Compose overlay with test-only MinIO credentials
  for existing base services and prove API readiness. The base Compose's blank interpolated values
  prevent `minio-init` and thereby the API from starting; this is test-environment configuration,
  not a production Compose semantic change. Cost if wrong: the overlay may need an additional
  fixture service adjustment, but production credential handling remains untouched.

## Task status

- Task 1: fix round 1/5 (1 addressed, 0 open; commits 765d2bc..fb9824d)
- Task 1: complete (commits 455485e..fb9824d, review clean)
- Task 2: fix round 1/5 (1 addressed, 0 open; commits 22cb316..20e4faf)
- Task 2: complete (commits fb9824d..20e4faf, review clean)
- Task 3: blocked (commit 43dcc3f; Keycloak claim mapper and API dependency prerequisites)

## Review rulings

- Task 3 review — production session/rendering changes: not a Task 3 scope breach. They were
  separately approved by the user as the bounded M5.2/M5.3 corrective design, implemented in
  `codex/m5-user-session-correction` and `codex/m5-operator-oidc-correction`, independently
  reviewed, then cherry-picked as `7d90cc2`, `5f542d3`, and `95b47ee`. Cost if wrong: the
  corrections would need to be split into separate PRs before integration, but the current branch
  has their review and test provenance.
- Task 3 review — Keycloak password grant in readiness: retained as a test-realm infrastructure
  probe only. It validates API JWT authorization and never creates/injects a browser session;
  browser acceptance remains authorization-code plus PKCE. Cost if wrong: readiness would need to
  use a browser-derived token path, increasing runner complexity without strengthening the browser
  proof already supplied by the live suite.
- Task 3 review — ambient OIDC/API/session runtime overrides: accepted finding. The Playwright
  runner must validate/derive only its isolated local M5 environment before final verification.
- Task 4: blocked (live run: 2 passed, 3 failed). Root-cause evidence: the real authorization-code + PKCE access token contains `workspace_id=m5-workspace` and `documents:write`; the Next.js BFF forwards it and does not locally return the 403; FastAPI returns 403 because ingestion authorizes a persisted Workspace and the isolated environment has no provisioned `m5-workspace` record. The plan prohibits direct internal-table seeding and there is no public/supported Workspace provisioning seam. The question flow reaches `started` then `INTERNAL_ERROR`; no accepted deterministic provider failure/refusal seam exists. Additional coverage remains blocked by no delete-capable identity and no operator UI target-workspace path. Preserve these as unresolved live-evidence gaps; do not relabel them as passes.
- Task 5: evidence recorded (current release-gate evidence is partially verified; M5.4/release gate is not claimed complete)

## Task 5 resume evidence (2026-09-20)

- Current evidence candidate: `cbe84afabe56666aac7be389fc1828ac2cce0260` on
  `codex/m5-e2e-verification`.
- The real Keycloak authorization-code + PKCE, Next.js BFF, backend authorization, and Playwright
  path recorded **12 passed**. This replaces only the earlier browser-runner/Keycloak availability
  observation; it does not convert unavailable product outcomes into passes.
- Full frontend gate recorded **49 tests passed**, with typecheck, lint, build, and audit passed.
- Backend pytest recorded **1042 passed, 3 skipped** only with `PYTHONPATH` explicitly bound to
  `C:/Developer/Projects/knora-agent-worktree/m5-e2e-verification/backend/src`. Bare pytest had a
  collection failure because the shared editable install resolves imports to the primary checkout;
  this is an environment binding issue and is not recorded as passed. The shared `.venv` was not
  changed.
- Ruff, Docker Compose configuration, and `git diff --check` passed.
- Provider-failure/interruption remains **`BLOCKED_LIVE_E2E`**: no deterministic public seam is
  approved, and no mock or fabricated outcome was used.
- Deletion remains unavailable evidence: `blocked` /
  `DOCUMENT_DELETION_POLICY_UNAVAILABLE` is not a successful deletion.
- This evidence does not claim M5.4 or the release gate complete.
