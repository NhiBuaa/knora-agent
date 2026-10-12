# CI foundation design

Status: architecture approved by the owner on 2026-10-11, including authorization to execute after writing the plan. Implementation starts from `70eb7ffc24f4d959d7a52164f8bfc74e83b10c2f` on `ci/foundation`.

## Purpose and acceptance

Make existing executable contracts run from a fresh checkout on every pull request, and require scoped, reproducible runtime evidence for releases that change those runtime capabilities. Reuse pytest, Ruff, Alembic, Vitest, Playwright, Maven and the guarded Compose harnesses. CI does not grant acceptance to unfinished features in issues #146, #150, #152, #153, #156, #158 or #159.

The owner approved four requirements:

1. One `.github/workflows/ci.yml`, with Frontend, Backend, Database, Keycloak and aggregate `CI required`. On 2026-10-12 the owner approved moving formatting into component jobs and replacing the former `Prettier format check` requirement with `CI required` through a safe protection migration.
2. Frontend runs only independent Playwright fixtures. E2E with real backend/auth/storage belongs to Runtime Verification.
3. Suitable unit and integration tests run on every PR. Expensive/model/multi-service checks run separately. An executed suite with missing, empty, failed or skipped tests fails its gate.
4. Runtime Verification is manual and a release acceptance requirement for related changes, with evidence bound to the actual tested commit SHA.

## Observed starting state

- At the original baseline, the only workflow was `.github/workflows/frontend-formatting.yml`, running `npm ci` and `format:check`. Main protection required `Prettier format check`, from the GitHub Actions app, with strict checks.
- Frontend already exposes lint, typecheck, Vitest, build and Playwright commands; Node 22 and Next.js 15 are established choices.
- PostgreSQL tests need migrated pgvector storage. `test_workspace_concurrency.py` explicitly requires a database named `knora_issue110_task2` and otherwise skips.
- Windows PDF hard-memory-limit and local launcher contracts require Windows. Other configuration tests need `pwsh` and Docker configuration inspection.
- One Ollama grounding test requires an explicitly enabled real model. Its surrounding tests use synthetic responses and remain automatic.
- `figma-ui-interactions.spec.ts` mixes independent fixtures and guarded application journeys. Its current fixture selection collects application tests as skips.
- Native theme fixtures use an offline Java renderer, but its export script assumes an existing Docker Maven volume and parent CSS fetched from an owned live Keycloak. A fresh PR runner must render from pinned Maven artifacts without live services.
- Maven `EmailOtpResetFlowIT` exercises in-process flow contracts. `OtpChallengeConcurrencyIT` requires two real nodes and includes opt-in outage/crash/fault cases.

## Tier 1: PR CI

Triggers: `pull_request` targeting main, `push` to main, and manual dispatch for verification. No top-level path filters. Checkout the default PR merge commit; record both checkout SHA and PR head SHA. `permissions: contents: read`; no external AI/service credentials or developer `.env` files. Use dependency caches, explicit timeouts and cancellation of superseded PR runs.

| Job ID / check | Runner | Scope |
| --- | --- | --- |
| `frontend` / `Frontend` | Ubuntu | Frontend/shared Prettier checks first, ESLint, TypeScript, all Vitest tests, production build, Chromium fixture Playwright; Java 21/Maven only to render synthetic native fixtures offline |
| `backend` / `Backend (ubuntu/windows)` | Ubuntu and Windows matrix | Portable Python/evaluation contracts on Ubuntu; Windows launcher/PDF contracts on Windows. Ruff format and lint, OpenAPI drift and both Compose entry-point validation on Ubuntu |
| `database` / `Database` | Ubuntu | Disposable pgvector/PostgreSQL 16 service, Alembic upgrade and database integration/concurrency contracts |
| `keycloak` / `Keycloak` | Ubuntu | Maven Spotless Java formatting in validate, then Java 21 unit tests and `EmailOtpResetFlowIT`, without the two-node runtime suite |
| `required` / `CI required` | Ubuntu | Explicit `needs` for the four component job IDs; accept only `success` for every dependency |

Formatting belongs to the owning component. Shared workflow/Compose/CI-document formatting reuses the frontend's existing Prettier installation with explicit paths. Generated files and immutable evaluation evidence retain their existing validation. See the runbook for exact scope and languages without a formatter.

The final job uses `if: ${{ always() }}` and compares every dependency result to `success`. Failure, cancellation, skip, absent/malformed results and unknown job IDs fail validation. Matrix `fail-fast: false` preserves evidence for both platforms. A workflow cancelled before the aggregator runs can leave that check cancelled or missing; it cannot authorize a merge. Enable the verified `CI required` check before removing the former Prettier requirement, preserving strict mode, Actions app binding and other protection settings. YAML alone does not change branch protection.

### Python partition and skip policy

Use one small pytest collection plugin rather than a new runner framework. An explicit reviewed file list assigns database tests, explicit Windows file/node lists assign platform contracts, and the single live Ollama node belongs to runtime. Default selection remains the existing full local collection when no CI suite option is passed.

CI suite names: `backend`, `windows`, `database`. A test belongs to exactly one PR suite or explicitly to runtime. Collection writes selected and deselected node IDs to an artifact. New ordinary tests enter the portable suite by default; database tests must be classified with their service requirement. Verify the union and disjointness of partitions against full collection, including mixed files; routing must not rely on a filename guess about integration tests.

Database uses `postgresql+psycopg://knora:knora@127.0.0.1:5432/knora_issue110_task2`, satisfying the existing isolation guard. Never point this suite at a developer database. Do not globally enable `KNORA_RUN_LIVE_OLLAMA_GROUNDING` in PR CI.

Real PDF database contracts need a writable, memory-limited cgroup. Run this suite in a disposable privileged Linux container on the ephemeral runner, with a 2 GiB limit and delegated memory controller; keep extractor fail-closed behavior. Backend checkout must include immutable historical Git objects used by evaluation provenance tests.

For pytest, Vitest, Playwright and Maven, validate their JUnit XML: require a report, at least one test case, no failures/errors, no skips and no duplicate test identities. Do not pass `--passWithNoTests`, `-DfailIfNoTests=false` or `continue-on-error`. Deselection is reported as scope, never as execution success; required tests must actually be selected. Windows cases run on Windows instead of allowing their Linux skips.

### Fixture browser scope

Reuse the Figma fixture host, typed synthetic projections and assertions. Select the fixture portion explicitly so application-only cases are not collected as skipped cases. Render native FTL/resources with `FigmaThemeRenderer.java` from pinned FreeMarker 2.3.32 and Keycloak themes 26.3.3, preserving resource checksum validation and local assets. Do not download CSS from a running Keycloak or require an existing Docker cache. No backend, realm, session or real user is involved. This is UI contract evidence, not proof of live authorization, OTP or Figma visual parity.

## Tier 2: Runtime Verification

`.github/workflows/runtime-verification.yml` is `workflow_dispatch` only. Inputs specify a full 40-character `subject_sha` and a named profile, initially `application` or `otp`. Resolve and verify the checked-out commit with `git rev-parse HEAD`; reject invalid refs or mismatches. Record separately the workflow source SHA, actual tested SHA, profile, run ID/attempt, UTC timestamps, selected scenarios, tool versions, service/image versions and report hashes. Never label `github.sha` as the tested SHA when an explicit checkout selected another commit.

Use fresh GitHub-hosted Ubuntu runners, synthetic accounts, Mailpit and guarded Figma services from `docker-compose.dev.yml`. Preserve ownership/port/realm guards. Run each profile with no test retries for release qualification; do not collect old controller-owned records as prerequisites for a fresh run. A missing prerequisite, scenario or report is a failed verification, not an optional skip.

`application` covers current real identity/login/logout, Workspace and Document navigation/archive/restore, Conversation navigation, Operator permissions and unavailable observations. Use the existing dedicated specs and explicit application scenarios that create their own records. Do not select controller-dependent PDF/Turn cases until the wrapper provides fresh processing and artifacts for those exact cases.

`otp` covers native OTP through synthetic email plus existing essential two-node/JPA storage contracts. Reuse `prepare-figma-otp-runtime.ps1` and `prepare-figma-otp-proof.ps1`; Bind/Restore only owned test realms, and never mix proof instrumentation with ordinary runtime. Crash/outage/commit-reply/activation scenarios remain separate explicitly named acceptance scopes, not covered by a base OTP pass. Releases changing those capabilities need those additional scenario proofs; #152 remains open until its own gates are met.

Reports must list selected/executed scenarios, counts and any excluded scenarios with release limitations. Upload only allowlisted sanitized JUnit/JSON reports and synthetic UI evidence; no blanket upload of `.verification`, logs, `.env`, realm snapshots, authentication URLs, OTPs, tokens or browser traces. Failure/cancel must produce no success manifest. Restore/stop only resources proven to belong to this run's fresh checkout. Cleanup cannot be guaranteed after runner termination; the disposable runner bounds this residual risk.

### Release rule

For a release that changes a runtime capability, the release record must identify the exact release candidate commit and all applicable Runtime Verification profiles/scenarios. Every applicable profile must have a successful run and complete evidence for that same SHA; failed/cancelled/skipped/missing runs, different SHAs and narrower scenario selections cannot satisfy acceptance. Code changes invalidate previous evidence. CI PR merge-SHA evidence cannot substitute for a release commit's runtime evidence.

No deployment/release workflow exists today. Implement this rule as a documented acceptance checklist and an evidence validator; do not pretend a manual workflow automatically blocks GitHub releases. A future publishing workflow must call the same validator before publication. Tests that require a paid provider or local model are never run automatically for each PR. Their dataset/model/scoring/budget approvals remain issue-specific.

## Extension rule

Add ordinary unit/contract tests to current suites. Add cheap service integration to Database or a dedicated required job and include it in `required.needs`; add expensive multi-service/model checks to a named runtime profile with release mapping. Qdrant integration must use a pinned disposable service and tenant/active-version tests; OCR must use synthetic pinned fixtures; DeepEval deterministic adapter tests can run on PR while model judges require approved budgets; Langfuse uses mocked transport contracts on PR and a scoped real integration/outage profile. No empty or pass-through jobs for tools not yet implemented.

## Verification and sources

Acceptance includes partition coverage, strict report tests, aggregate truth-table tests (success/failure/cancel/skip/missing), fixture execution from a fresh checkout, migrated database integration, Java flow tests, runtime SHA/evidence negative cases, actionlint and actual GitHub runs after publication. Run repository pytest/Ruff/Compose checks and frontend format before format:check for maintained frontend changes.

Primary GitHub references fetched through Context7:

- [Job dependencies and always()](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs)
- [Skipped job status semantics](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions)
- [PR merge SHA and events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

Local sources: AGENTS.md, CONTEXT.md, architecture/seam standards, current workflow/package/POM, guarded preparation scripts and issues #149/#150/#152/#153/#158/#159. No thresholds for semantic quality or runtime latency are invented by this design.
