# CI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver strict automatic PR CI and manual runtime release verification using existing Knora tests.

**Architecture:** One ci.yml has Frontend, Backend, Database, Keycloak, an independent preserved Prettier check and CI required aggregation. A separate manual workflow checks an exact candidate SHA and emits scoped sanitized runtime evidence. Small collection/report helpers connect existing tools, without an orchestration framework.

**Tech Stack:** GitHub Actions, Python 3.12, pytest/JUnit XML, Ruff, PostgreSQL 16/pgvector, Alembic, Node 22, Vitest, Playwright Chromium, Java 21/Maven, PowerShell and existing Compose profiles.

**Spec:** `docs/superpowers/specs/2026-10-11-ci-foundation-design.md`

## Global Constraints

- Preserve the exact check name `Prettier format check` and add the aggregate `CI required`.
- All required job results must equal `success`; fail, cancel, skip, missing results and empty suites cannot pass.
- No AI benchmarks or paid providers on every PR.
- Fixture-only Playwright on PR; real service E2E belongs to Runtime Verification.
- Scope partition is explicit and reported; required executed suites have zero skipped tests.
- Runtime release evidence must match the exact full 40-character candidate commit SHA.
- Use existing tools and synthetic isolated data; never load developer .env or publish credentials.
- Worktree: `C:/Developer/Projects/knora-agent-worktree/ci-foundation`, branch `codex/ci-foundation`.
- No push, merge, branch deletion, worktree removal, GitHub protection change or deployment without the user's integration choice.

## File ownership and dependency map

| Task | Files | Produces / consumes |
| --- | --- | --- |
| 1 | root conftest.py; scripts/ci_checks.py; backend/test/config/test_ci_checks.py | pytest suite routing; strict JUnit and aggregate validation |
| 2 | frontend/playwright.figma.config.ts; fixture exporter/support; focused Vitest support tests | fresh offline fixtures and explicit fixture test selection |
| 3 | .github/workflows/ci.yml; remove old formatting workflow; AGENTS.md workflow reference | invokes Task 1/2 commands; exact required status names |
| 4 | .github/workflows/runtime-verification.yml; scripts/run-runtime-verification.ps1; evidence helper/tests; docs/runbooks/ci.md | exact-SHA manual profiles and release evidence validator |
| 5 | verification record, README CI entry, this plan | fresh gate evidence, review and integration handoff |

Tasks 1 and 2 have disjoint files and can be developed independently. Task 3 consumes both interfaces. Task 4 consumes the report validator, keeps runtime-specific code separately owned and can proceed after those interfaces are fixed. Task 5 runs after all implementation tasks.

## Task 1: Test partitions and honest result checks

**Files:** Create `conftest.py`, `scripts/ci_checks.py`, `backend/test/config/test_ci_checks.py`.

**Interfaces:** `pytest --ci-suite=backend|windows|database --ci-selection=PATH`; `python scripts/ci_checks.py reports PATH [PATH ...]`; `python scripts/ci_checks.py jobs` reads an exact dependency JSON object from environment `CI_NEEDS`. Report CLI returns nonzero on invalid input and prints safe case identities, never captured output.

- [x] Write tests for success, failure, error, skip, zero cases, missing/malformed report and missing/cancelled/skipped job results. Hand-created report fixtures must include one valid case and variants that fail for the specified reason.

```python
@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped"])
def test_required_job_non_success_is_rejected(result):
    needs = {name: {"result": "success"} for name in ("format", "frontend", "backend", "database", "keycloak")}
    needs["database"]["result"] = result
    assert required_jobs_succeeded(needs) is False
```

- [x] Run focused test RED with the primary Python interpreter and `PYTHONPATH` pointing to this worktree's backend/src. Implement the validator with standard json/xml libraries, then run GREEN; no XML-text grep tests.
- [x] Add opt-in collection routing. Route `backend/test/adapters/postgres/**` plus real database files outside that directory: CLI ingest/worker/trace gate, HTTP ingestion/questions, issue19 application E2E, OpenAI-compatible application integration, tools execution/proposal/reconciliation PostgreSQL tests. Windows node selection takes precedence in mixed files. Windows launcher files and Windows-specific PDF/worker nodes go to Windows. The real Ollama grounding node is runtime. Unselected tests remain reported by node ID.
- [x] Collect all tests, then each suite and the runtime node. Assert union equals full collection and PR partitions are disjoint; default local invocation retains current behavior. Do not select real-model test on PR.
- [x] Ensure Database uses the existing required isolated database name `knora_issue110_task2` so Workspace concurrency runs rather than skips.
- [x] Run `python -m pytest backend/test/config/test_ci_checks.py`, `python -m ruff check conftest.py scripts/ci_checks.py backend/test/config/test_ci_checks.py` and collection coverage check. Commit only owned files after successful checks.

## Task 2: Independent browser fixtures

**Files:** Modify `frontend/playwright.figma.config.ts`, `frontend/tests/e2e/support/figma-theme-export.mjs`, related focused support tests; add a fixture-only config only if the existing selection interface cannot express the scope clearly.

**Interfaces:** fixture invocation remains `FIGMA_TEST_MODE=fixture npx playwright test --config playwright.figma.config.ts --reporter=list,junit`. JUnit output is selected through `PLAYWRIGHT_JUNIT_OUTPUT_NAME`; native fixture export accepts explicit paths to pinned Maven jars or a repository-local artifact directory.

- [x] Write selection tests asserting fixture mode excludes `guarded application journeys`, application mode excludes fixture-only sections, and unknown/incompatible selection fails closed. Run focused Vitest RED.
- [x] Select application sections with grep/grepInvert rather than collecting them as skipped fixtures. Do not disable assertions or delete live tests.
- [x] Replace export's owned live CSS/cache prerequisite with pinned Keycloak theme/FreeMarker JAR inputs; use the existing Java renderer and resource hash checks. No Docker/live realm needed for this export. Preserve clear validation failures for missing/changed resources. Add an assert-based exporter check or focused test for invalid input and run GREEN.
- [x] From fresh checkout install with `npm ci`; fetch Maven artifacts using existing provider POM dependency resolution, compile renderer with Java21, export synthetic fixtures and install Chromium.
- [x] Run `npm --prefix frontend run format` before `format:check`, then `typecheck`, all Vitest tests, lint, build and the full independent fixture selection. Validate JUnit via Task1 with zero skips; stop and repair concrete failures.
- [x] Commit owned files after verification. Do not update visual baselines to make the CI gate pass.

## Task 3: Unified automatic CI

**Files:** Create `.github/workflows/ci.yml`; remove `.github/workflows/frontend-formatting.yml`; update only the workflow-reference sentence in AGENTS.md; add CI command reference to README/runbook.

- [x] Define PR/main/manual triggers without path filters, contents read permission, checkout/cache/setup actions, explicit timeouts and PR concurrency. Use Node22, Python3.12, Java21 and existing dependency files.
- [x] Add independent `format` job named `Prettier format check`; add Frontend with Task2 fixture export and lint/typecheck/Vitest/build. Generate separate XML reports and validate them before success.
- [x] Add Backend Ubuntu/Windows matrix with `fail-fast: false` and respective Task1 suite options. Ubuntu also runs Ruff, exporter check and both Compose validations using only synthetic env values. Windows tests never require a host Linux Docker daemon.
- [x] Add Database service image `pgvector/pgvector:pg16`, DB `knora_issue110_task2`, health check and loopback DSN. Run `python -m alembic -c backend/alembic.ini upgrade head` from the correct backend working directory, then database suite serially with XML validation.
- [x] Add Keycloak: `mvn -B -f infra/keycloak/providers/email-otp-reset/pom.xml -Dit.test=EmailOtpResetFlowIT verify`; validate Surefire and Failsafe XML separately. Do not call full unfiltered verify without two real nodes.
- [x] Add aggregation exactly:

```yaml
required:
  name: CI required
  if: ${{ always() }}
  needs: [format, frontend, backend, database, keycloak]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: python scripts/ci_checks.py jobs
      env:
        CI_NEEDS: ${{ toJSON(needs) }}
```

- [x] Upload only CI report/selection artifacts with if:always and unique matrix names; never dump runtime env or private traces. Failure must preserve failed job status.
- [x] Validate workflow with actionlint and aggregate truth-table tests. Verify no duplicate Prettier name remains. Document required-check transition: preserve existing protection, add `CI required` after actual GitHub run and authorized integration.
- [x] Run applicable commands locally and commit only this task's files.

## Task 4: Manual runtime and exact release evidence

**Files:** Create `.github/workflows/runtime-verification.yml`, `scripts/run-runtime-verification.ps1`, a small runtime evidence helper with focused tests, and `docs/runbooks/ci.md`.

**Interfaces:** dispatch inputs `subject_sha` (full commit) and `profile` (`application` or `otp`); runner validates actual checkout SHA. Evidence JSON schema `knora-runtime-verification-v1` includes `subject_sha`, workflow/source SHA, run ID/attempt, profile, selected/executed scenarios, tool/image identities, timestamps, report hashes and outcome. Release validator requires a candidate SHA and evidence files for each applicable profile; missing/mismatch/failure/skip/empty evidence fails.

- [x] Write RED tests: actual SHA mismatch, invalid SHA, missing requested profile, unsuccessful outcome, changed report hash, missing/empty/skipped XML, evidence for another SHA. Implement the smallest strict evidence validation/generation and run GREEN.
- [x] Create manual workflow with trusted workflow definition, full-SHA checkout and validated profile inputs passed as environment/arguments, never interpolated into shell source. No scheduled or PR trigger; no paid AI secrets.
- [x] Application runner uses `prepare-figma-e2e.ps1`, dedicated identity/document/conversation/operator specs and fresh synthetic records. Preserve ambient selectors and ownership guards. Select only self-contained application journeys; list controller-dependent exclusions and their release limitations.
- [x] OTP runner prepares native provider/vault and proof nodes using existing guarded scripts, selects essential storage cases explicitly, then native email/OTP tests with Bind/Restore. Enable no outage/crash opt-in silently. Scope unsupported hardening as unsatisfied release evidence, not an accepted fallback.
- [x] Disable raw auth traces/video/automatic screenshots and upload only sanitized reports plus explicitly masked synthetic evidence. Ensure finally restores only owned realm/resources. If any setup, scenario, report, cleanup or evidence step fails, final outcome remains non-success.
- [x] Write runbook with local/dispatch commands, exact SHA release checklist, applicable profile mapping, evidence retention and branch-protection integration. Future Qdrant/OCR/DeepEval/Langfuse additions must follow the spec extension rule; no empty jobs.
- [ ] Validate with actionlint, helper tests and feasible fresh isolated runtime profile execution. Actionlint and helper tests are green; complete live runtime profile execution remains pending a clean hosted/manual run. GitHub publication is unavailable on this branch; no push is implied by implementation approval.
- [x] Commit owned files after verification.

## Task 5: Integrated verification and completion

- [x] Self-review scope against the four owner adjustments; request independent spec and quality review, fix load-bearing findings, then rerun affected gates.
- [x] Run full existing repository checks in the isolated test environment: `python -m pytest`, `python -m ruff check .`, `docker compose config --quiet`, `docker compose -f docker-compose.dev.yml config --quiet`, `python scripts/export_openapi.py --check`, `git diff --check`.
- [x] Run frontend format then format:check, typecheck, Vitest, lint, build and fixture browser suite. Run strict CI partitions with zero selected skips and Java flow tests. Run workflow syntax and runtime evidence negative-case checks.
- [x] Record actual pass/fail counts and SHA in `docs/development/ci-foundation-verification.md`; distinguish local Windows/Linux/container evidence from actual GitHub checks and runtime profiles not yet qualified. Update completed plan boxes only with evidence.
- [x] Present integration choice for push/PR or keep branch. Actual GitHub PR/main runs, required-check update and runtime release evidence become concrete after that authorized publication; never claim GitHub gates ran from local checks.

## Self-review and continuity

The spec has a task for each accepted requirement: unified/check-preservation/aggregate behavior (1,3); fixtures and live scope (2,4); classification and no false PASS (1,2,3); exact runtime release evidence (4,5); reuse/extension/no paid every-PR AI (global constraints and runbook). No task changes domain, runtime production defaults or unfinished issue acceptance. Document any necessary implementation ruling in the verification record.
