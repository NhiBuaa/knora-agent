# CI and Runtime Verification

## Verification Contract

Apply this loop to each code change. For documentation/tooling changes, verify the affected
instructions or contract rather than inventing a production change. Keep commands, outcomes and
work status in the relevant Issue/PR; this runbook owns the procedure, not a second evidence ledger.

1. **Define:** name the expected observable behavior, changed surfaces/callers and acceptance
   criteria before editing. Identify affected quality requirements using the Issue, approved
   standards and existing contracts; for each, record an observable pass condition and planned
   check in the Issue/PR. Use [quality evidence](#matching-quality-claims-to-evidence) below;
   resolve material missing product criteria rather than inventing thresholds. For a bug,
   identify a reproducer or regression test that fails for
   the original symptom before the fix; explain any limit to reproducing it.
   When a criterion can be read in materially different ways, record examples of pass,
   fail and insufficient evidence before implementing. For [#183 Master §12.5](../superpowers/plans/2026-10-16-issue-183-master-plan.md#125-owner-clarification--conditional-lists-not-compulsory-enumeration),
   count-only prose is allowed but does not prove list coverage; an answer enumerating
   chapter names must preserve every generated item and its order as a list. Losing an
   item in the composer/renderer fails preservation. An observed count-only answer leaves
   list coverage unverified. These examples explain that contract, not a new product criterion.
2. **Select:** inspect the owning tests, `frontend/package.json`, root `conftest.py` and the
   applicable workflow under `.github/workflows/`. Choose the smallest set covering the behavior
   and affected boundaries, including relevant failure, authorization or concurrency paths.
   Cover successful behavior as well as these affected safety boundaries while implementing;
   update the verification plan if new impacts emerge within the approved scope.
   State why broader checks or runtime observation are required, unnecessary or blocked.
3. **Run and read:** execute the selected checks on the intended checkout. Inspect exit codes,
   selected/executed counts and actual assertions/reports, including failures, errors and skips.
   A collected test, successful command launch or old report is not passing execution evidence.
4. **Repair:** on failure, distinguish a product regression from test/environment/pre-existing
   failure using the output. Fix within approved scope and rerun the failed checks plus affected
   regressions. Preserve failed-attempt evidence. Missing tools, dependencies or unsafe targets
   are blockers to report, not permission to install, skip, weaken gates or change another stack.
5. **Observe:** for user-visible behavior, select an applicable journey from the
   [Agent environment](agent-environment.md) and [Feature Map](../development/feature-map.md)
   when feasible. Check the UI and authoritative response/projection; use owned, bounded logs
   for diagnosis and verify owned cleanup. If the harness cannot exercise the behavior, report
   the gap; fixture rendering or unrelated smoke cannot substitute for it.
6. **Conclude:** compare evidence to every acceptance criterion after the final edit, including
   the quality requirements identified in Define. State observed results, material trade-offs
   and unverified claims; a green test suite alone does not establish every quality dimension.
   Record the
   tested full SHA (and dirty diff if any), working directory, reproducible commands, scope/counts,
   exit/result and sanitized report/run references. Before publishing commands, replace token,
   password and other secret values with `[REDACTED]`, including literal arguments and inline
   environment assignments. Preserve executable/subcommands, flag and variable names, quoting and
   non-secret arguments; supply real secrets only through authorized local configuration.
   After later code edits, rerun affected checks
   and refresh evidence. Separate verified scope from blockers and checks not run; with missing
   required evidence, report partial progress, not completion.

### Matching quality claims to evidence

Select only dimensions affected by the change or needed to support its claims. Scale checks to
risk; this is not a requirement to run every row for every Issue. Keep the requirement, pass
condition, planned check and eventual evidence together in the existing Issue/PR, not a new ledger.

| Affected requirement or claim            | Evidence to select before editing                                                                                                                                              |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Correct behavior                         | Assertions for expected outcomes, relevant invalid input, failure and boundary cases through the owning public/application seam                                                |
| Authorization or data safety             | Allowed and denied access, including cross-Workspace requests where relevant; verify rejection before protected lookup/side effects and safe error/log output                  |
| Faster or less resource-intensive        | Before/after measurements with the same inputs, workload, environment and measurement method; record tested versions, repetitions/variation and resource or latency trade-offs |
| User experience or accessibility         | The affected application journey, including relevant waiting, error/recovery and keyboard/accessibility behavior; link observations to the specific criterion                  |
| Design, compatibility or maintainability | Inspect affected callers, component responsibilities and dependency direction against approved seams; run applicable contract/regression tests and state the design trade-off  |
| Operation or recovery                    | Relevant failure, retry, concurrency, ownership and cleanup checks in an isolated owned environment; observe authoritative state and bounded logs                              |

A working browser journey proves the exercised behavior, not that users find it easier. A usability
improvement needs an appropriate comparison or user evaluation; without it, report only the observed
behavior. Likewise, functional tests or shorter code do not prove speed, security or maintainability.
If comparable measurements are unavailable, label the improvement unverified and do not claim a gain.
Mark each applicable criterion passed, failed or unverified with its evidence or blocker; explain
why omitted checks are unnecessary. Missing required evidence blocks completion. Optional follow-up
must remain explicit and cannot replace an existing acceptance criterion or required CI check.

### Choosing the verification surface

Use existing checks; command and partition definitions remain in package/config/workflow sources.
Local targeted checks do not replace the unchanged full required PR CI.

| Changed surface                  | Start with                                                                       | Expand when needed                                                                                                                                                                            |
| -------------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend/application              | Tests mirroring the owning module under `backend/test`; Python formatting/lint   | HTTP/provider contracts and real database tests (using shared local DB sequentially or isolated test DB for migrations/destructive fixtures) for changed boundaries, persistence or atomicity |
| Frontend/BFF                     | Owning Vitest tests, typecheck, lint and formatting from `frontend/package.json` | Build and relevant application Playwright journey for user-visible behavior; fixture mode proves rendering only                                                                               |
| Launcher, evidence or CI tooling | Existing config/CLI regression tests, including refusal/failure/cleanup paths    | Compose configuration, supported OS checks and affected disposable application journeys when launch/ownership/browser behavior changes                                                        |
| Instructions/docs                | Link/command/source checks and applicable shared formatting                      | For changed agent instructions, a fresh agent exercising an existing task; a read-only trial is not proof of a bug-fix loop                                                                   |
| Model/retrieval quality          | Deterministic contracts for code behavior                                        | Separately authorized evaluation with approved inputs and provenance under the [Architecture Standard](../standards/architecture.md#evaluation-governance); no inference by default           |

Unit/integration PASS proves only the asserted seam. Offline Playwright fixtures do not prove a
live backend. Application browser PASS proves only the executed journeys on that build/environment;
deterministic providers do not establish AI semantic quality. A targeted smoke does not satisfy a
broader release profile. Full E2E and model inference are not required for every Issue.

### Reporting state and CI identity

Report each applicable state with evidence, or explicitly as pending, blocked, not run or not
applicable with a reason. These are independent facts, not an automatic promotion chain:

| State            | Evidence required for the claim                                                                                                     |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Implemented      | Requested code/instruction change exists in the diff; says nothing about execution                                                  |
| Local Verified   | Named local checks actually passed on the reported checkout/diff; only that scope                                                   |
| CI Verified      | `CI required` from GitHub Actions succeeded for the current PR head; link the run and full head SHA                                 |
| Runtime Verified | Applicable real application journeys passed with fresh, scoped evidence tied to the tested build; identify smoke vs release profile |
| Reviewed         | Actual review and its scope/findings; tests do not constitute review                                                                |
| Merged           | GitHub merge record and resulting commit                                                                                            |
| Deployed         | Deployment record and target/version observation; merge or runtime smoke is insufficient                                            |

Assigning a reviewer is pending review, not `Reviewed` or review PASS. Record the actual
reviewer/task, subject and returned findings/result in the PR. An interrupted or failed
required review remains incomplete or failed and blocks its gate; do not relabel it advisory
to bypass that requirement.

For CI, compare the current PR `headRefOid` with the run's head and the existing `ci-subject`
artifact: `pr_head_sha` identifies the PR head, while `checkout_sha` records the tested synthetic
merge checkout for `pull_request` runs. A push run has no PR head and tests its recorded checkout.
Keep these identities distinct; a green old head, another PR or workflow-source SHA does not
verify the current change. A new push invalidates the previous head's CI claim. A missing, failed,
cancelled or skipped required result is not CI Verified. Runtime release profiles additionally
use the exact subject-SHA validation below.

## Local test execution and evidence retention

Local test execution uses the existing `--ci-suite` options defined in root `conftest.py`: `backend`, `windows`, `database`, and `security-shadow`. These options route tests according to partition rules, not ad-hoc directory conventions:

- `backend`: The backend unit and non-Windows, non-database partition according to repository routing. It is not "all tests without a database".
- `windows`: Windows-specific tests requiring Windows APIs, Job Objects, or local launcher harnesses.
- `database`: Integration tests interacting with PostgreSQL adapters, ingestion workers, and stores.
- `security-shadow`: Archived/research tests excluded from required CI.

Use `--ci-selection` to write a selection manifest (`selection.json`) capturing the exact executed and deselected tests. This bounds terminal output while preserving complete, auditable proof of partition execution.

### Suite execution commands

Run suite commands in a dedicated PowerShell process from the verified checkout root using the discovered Python interpreter. `$evidence` is a fresh, per-run directory:

```powershell
# Backend partition according to existing routing (not all local tests).
python -m pytest backend/test evals/test --ci-suite=backend --ci-selection="$evidence/backend-selection.json" --junitxml="$evidence/backend.xml" -o "cache_dir=$evidence/cache"

# Windows partition: run on Windows with configured shells and dependencies.
python -m pytest backend/test evals/test --ci-suite=windows --ci-selection="$evidence/windows-selection.json" --junitxml="$evidence/windows.xml" -o "cache_dir=$evidence/cache"

# Database partition: requires explicit reviewed test target before invocation.
if ([string]::IsNullOrWhiteSpace($env:KNORA_DATABASE_URL)) { throw 'LOCAL_DB_TARGET_REQUIRED: set the reviewed test target in this process; do not use the implicit fallback' }
python -m pytest backend/test evals/test --ci-suite=database --ci-selection="$evidence/database-selection.json" --junitxml="$evidence/database.xml" -o "cache_dir=$evidence/cache"
```

Capture `$LASTEXITCODE` immediately after executing a single pytest command.

**Database target safety**: Setting `$env:KNORA_DATABASE_URL` alone does not prove permission to truncate or reset data; an operator must separately verify that the targeted database is an authorized, disposable test instance before invoking the database suite. Certain database suite fixtures (such as `backend/test/adapters/postgres/test_object_lifecycle_store.py:30–36`) execute `TRUNCATE` and commit transactions before and after tests, which permanently destroys persistent data. Never run the database test suite against a shared development database preserving project records. Ordinary local application smoke tests use the shared local database sequentially and do not run this destructive test suite. Note that this preparation guard checks `$env:KNORA_DATABASE_URL` in the command template; bare `pytest` invocations bypassing the template fall back to the implicit default URL.

### Long-running command evidence pattern

To ensure evidence is captured from the beginning of execution, runs are tied to an exact git checkout, and process interruptions or lost connections are detected honestly, use the following PowerShell child-process pattern. The script block runs exclusively in an isolated child shell without mutating the caller environment:

```powershell
$testBlock = {
$ErrorActionPreference = 'Stop'
$python = (Get-Command python -ErrorAction Stop).Source
$evidence = Join-Path ([IO.Path]::GetTempPath()) ('knora-local-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $evidence -ErrorAction Stop | Out-Null
Write-Output "RUN_PID=$PID EVIDENCE=$evidence"
$subjectSha = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'GIT_HEAD_UNAVAILABLE' }
$subjectSha | Set-Content -LiteralPath (Join-Path $evidence 'subject-sha.txt') -Encoding UTF8
$worktreeStatus = git status --short
if ($LASTEXITCODE -ne 0) { throw 'GIT_STATUS_UNAVAILABLE' }
$worktreeStatus | Set-Content -LiteralPath (Join-Path $evidence 'worktree-status.txt') -Encoding UTF8
$ErrorActionPreference = 'Continue'
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) { $PSNativeCommandUseErrorActionPreference = $false }
$LASTEXITCODE = $null
& $python -m pytest backend/test evals/test --ci-suite=backend --ci-selection="$evidence/selection.json" --junitxml="$evidence/junit.xml" -o "cache_dir=$evidence/cache" *> (Join-Path $evidence 'pytest.log')
$testExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($null -eq $testExit) { throw 'PYTEST_EXIT_UNAVAILABLE' }
$testExit | Set-Content -LiteralPath (Join-Path $evidence 'exit-code.txt') -Encoding UTF8
Write-Output "EXIT_CODE=$testExit EVIDENCE=$evidence"
exit $testExit
}
$testShell = (Get-Process -Id $PID).Path
$encodedTestBlock = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($testBlock.ToString()))
& $testShell -NoProfile -EncodedCommand $encodedTestBlock
$outerExit = $LASTEXITCODE
Write-Output "CHILD_EXIT=$outerExit"
if ($outerExit -ne 0) { throw "TEST_CHILD_FAILED:$outerExit; inspect this run's evidence" }
```

### Evidence verification matrix

| Execution scenario                                  | Required evidence                                                               | Conclusion                                                                            |
| --------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Pytest runs to completion and passes                | Exit 0, readable JUnit XML, valid test count, selection manifest if suite used  | PASS in the executed scope                                                            |
| Test or assertion failure                           | Non-zero exit code, log file, JUnit XML if generated by pytest                  | FAIL; outer process completion does not imply pass                                    |
| Early error (foreign preload mismatch, usage error) | Non-zero exit code and error log; JUnit XML or selection manifest may not exist | Early initialization failure, NOT a PASS; missing JUnit is expected on early errors   |
| No tests selected                                   | Non-zero exit code (e.g. exit 5) or empty selection manifest                    | Unproven behavior, NOT a PASS                                                         |
| Interrupted or lost session                         | Log started, recorded PID, but missing `exit-code.txt`                          | Undetermined / incomplete; verify PID and files before rerunning; never assume exit 0 |

## Pull request checks

The automatic workflow runs the existing backend, frontend, database and Keycloak contracts.
Formatting runs inside the owning component job; `CI required` is the required branch protection
check. The former independent `Prettier format check` is replaced by this aggregate. Report XML is strict: missing,
empty, failed, skipped or duplicate cases fail the job.

No AI provider credentials, developer `.env` files, model benchmarks, or real application E2E
services are used by pull request CI. Browser fixtures are synthetic and offline.

The Frontend job uploads `frontend-reports` with `vitest.xml`, `figma-fixtures.xml` and
the masked touch-target captures from
`frontend/test-results/figma-ui/**/verification-touch-target-*.png`.
The current fixture contract in
[`figma-ui-interactions.spec.ts`](../../frontend/tests/e2e/figma-ui-interactions.spec.ts)
produces six captures: mobile 320/390/768, long-title dialog close at 320, and coarse-pointer
user/Operator views. Tests use `testInfo.outputPath(...)` so each invocation owns its output.
For changes to these controls, inspect the XML and open the expected captures from the same
CI run; an upload success alone does not prove every capture exists or the layout is correct.
Keep fixture evidence separate from application runtime or physical-device testing.

Issue #188 remains research-only / archived. The independent, non-required
`.github/workflows/security-shadow.yml` workflow owns the `Security shadow (offline unit)` and
`Security shadow (offline integration)` jobs. It runs automatically for pull requests targeting
`main` and pushes to `main` only when its `paths` filter matches Security Shadow code, tests, fixtures, dependencies, pytest hooks,
or CI evidence/gate tooling. Documentation-only and unrelated application changes do not trigger it.
`workflow_dispatch` permits manual execution on a selected ref, independently of path filters.
GitHub requires the workflow to exist on the default branch before manual dispatch is available.

The integration job retains its isolated runner, Python version, dependency pins, timeout,
`pip check`, real local validator test, strict JUnit validation and always-run report upload.
The separate unit job installs the existing `backend[dev]` dependencies without evaluation
extras or Guardrails, then runs `evals/test` with `--ci-suite=security-shadow` and retains its
strict JUnit report plus selected/deselected node manifest. Missing packages, dependency drift, test failure, skipped/empty/missing reports, or upload failure
remain workflow failures; no `continue-on-error` or optional test skip is introduced.
There is no model inference, provider credential, export, or production runtime integration.
The seven Issue #188 unit modules stay at their existing paths, with assertions and fixtures
unchanged. `SECURITY_SHADOW_FILES` in root `conftest.py` owns their explicit partition (plus
the standalone integration file). Required Backend, Windows and Database partitions exclude
these files before importing them; Shadow collection excludes unrelated modules before import.
Default local pytest without `--ci-suite` still discovers all the existing unit modules.
The required collection-conservation gate excludes research modules before import and checks
all remaining Backend/Evaluation nodes belong to exactly one required or explicit runtime
partition. Partition contract tests also prove each Shadow module routes independently and
cross-surface imports cannot occur during collection; other tests keep their existing routes.
CI gate tests remain required. Backend dependency declarations are unchanged.
`CI required` requires only Frontend, Backend, Database and Keycloak; it does not depend on
either Shadow job. Keep Security Shadow out of required branch/ruleset checks. Its failures
remain visible in the separate workflow and its `security-shadow-report` and
`security-shadow-unit-reports` artifacts; historical reports and evaluation evidence are preserved.

Database PDF integration tests run in a disposable Linux container with a 2 GiB memory limit
and a delegated cgroup memory controller. That container requires privileged execution on the
ephemeral GitHub runner so the real extractor can enforce its child-process limits. Failure to
configure isolation fails the job; these tests do not substitute a mocked extractor. Backend
checkout includes full Git history for immutable evaluation provenance checks.

### Formatting scope

| Component job             | Check                                                           | Maintained scope                                                                                                             |
| ------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Frontend                  | `npm --prefix frontend run format:check`                        | Frontend CSS/JS/JSX/JSON/MJS/SCSS/TS/TSX using existing ignores                                                              |
| Frontend (shared tooling) | `npm --prefix frontend run format:shared:check`                 | Workflows, Compose YAML, MinIO policy JSON, AGENTS/README and CI runbook/verification record; explicit paths in package.json |
| Backend Ubuntu            | `python -m ruff format --check .` then `python -m ruff check .` | Repository Python, including backend, migrations, scripts, evals and tests; Ruff pinned to 0.17.0                            |
| Keycloak                  | Maven Spotless check in `validate`                              | Provider and test/probe Java; Spotless 3.10.4 / google-java-format 1.24.0 (AOSP); before compilation/tests                   |

Use the matching `format`, `format:shared`, `python -m ruff format .`, or
`mvn -f infra/keycloak/providers/email-otp-reset/pom.xml spotless:apply` command to fix formatting.
The database tests share Python sources checked by Backend; no duplicate formatter installation
is needed in Database or Backend Windows. Their results remain mandatory dependencies.

Generated OpenAPI files use `python scripts/export_openapi.py --check`, rather than a formatter.
Locked evaluation datasets, manifests and historical evidence are outside shared Prettier scope.
Ruff excludes Markdown so it does not rewrite Python examples in historical records.
PowerShell, shell, XML and FreeMarker currently have no automatic formatting gate; the coverage
above is explicit and is recorded as a follow-up when those conventions are established. Add a formatter when an agreed convention exists for those languages.

## Backend Docker packaging

Build [`backend/Dockerfile`](../../backend/Dockerfile) with the repository root as its context,
as the existing Compose services do. The wheel requires sibling resources from `evals/` and
`docs/`, declared by `[tool.hatch.build.targets.wheel.force-include]` in
[`backend/pyproject.toml`](../../backend/pyproject.toml). There are currently 16 resources;
the Dockerfile stages those exact files before installing the package.

[`backend/Dockerfile.dockerignore`](../../backend/Dockerfile.dockerignore) excludes everything
first, then allows exact files. When adding or removing tracked backend source, migrations or
force-include resources:

1. Reconcile the exact allowlist with `git ls-files` and the manifest. Update resource staging
   in the Dockerfile when the manifest changes; keep WORKDIR, loaders and resource destinations
   consistent with the existing package contract.
2. Update the corresponding expected counts only when the tracked-file or manifest change
   justifies them. Keep the static equality check and BuildKit positive/negative probes in
   [`test_figma_e2e_harness.py`](../../backend/test/config/test_figma_e2e_harness.py).
   The positive probe must compare the full exported file set and bytes; the negative control
   must still detect an extra file. Directory/glob negations would weaken this boundary.
3. Obtain actual BuildKit results on an isolated runner, such as Backend Ubuntu CI. A local
   prerequisite skip is not proof that the Docker probe passed. Use the application runtime
   resource check below to verify the installed image as well.

## Runtime Verification

Prefer the hosted workflow for the full runner. A local invocation requires a disposable
environment with exclusive ownership of its Docker daemon resources and verification ports
for the entire run. `run-runtime-verification.ps1` uses the fixed `knora-figma-e2e` project and
cleans it with `down --volumes` after preparation, including failure paths. Its initial
freshness checks do not reserve that project against another session. Do not run the full
runner on a shared development machine; use the scoped
[`-Project ... -Run` smoke harness](agent-environment.md#launch) for authorized local checks.
That smoke run does not replace a release profile.

Runtime Verification is manual and must use the exact release candidate commit:

```powershell
$sha = (git rev-parse HEAD).Trim()
./scripts/run-runtime-verification.ps1 `
  -SubjectSha $sha `
  -WorkflowSha $sha `
  -Profile application `
  -RunId local `
  -RunAttempt 1
```

Dispatch `.github/workflows/runtime-verification.yml` with a lower-case full 40-character
`subject_sha` and either `application` or `otp`. The workflow checks out that SHA and the runner
checks `git rev-parse HEAD` before creating evidence. The workflow source SHA is recorded
separately from the tested SHA.

The runner performs `prepare-figma-e2e.ps1 -CheckFrontendOnly` before entering startup/cleanup.
A failed dependency check stops the run before Docker cleanup. See the
[frontend pre-check contract](agent-environment.md#frontend-dependency-containment-pre-check--checkfrontendonly)
for result codes and its limited scope.

The `application` profile runs fresh isolated identity, document, conversation, Workspace and
Operator journeys. Controller-owned PDF/Turn scenarios are excluded and remain release gaps until
their own fresh processing/controller evidence exists. The `otp` profile runs the native Mailpit
journey and eight essential two-node storage cases. Crash, outage, activation and commit-reply
fault cases are separate acceptance scopes and are never silently counted as the base OTP pass.

After collecting image identities and before the application browser journeys,
`Test-PackageResources` checks the installed `figma-api` distribution against the checkout's
force-include manifest and source hashes, including policy/JSON/corpus reads. Success prints
`RUNTIME_PACKAGE_RESOURCES_OK=<count>` (currently 16); missing sources, empty resource lists,
missing installed resources or content mismatches fail the run. The `otp` profile omits this
application resource check and does not collect a `figma-api` image identity.

The synthetic realm uses a 900-second user action lifespan so the real 300-second OTP resend
cooldown can finish inside the native reset transaction. OTP expiry and attempt/send limits remain
unchanged. Before enabling OTP on a deployed realm, verify that its user action lifespan exceeds
the resend cooldown; this profile does not configure a deployed realm. Keycloak checks reset
credentials against the user action lifespan
([Keycloak 26.3.3 source](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/services/resources/LoginActionsService.java#L473-L475)).

The OTP preparation uses the existing guarded vault and proof launchers. On Linux, the temporary
vault is owned by the Keycloak container UID (`1000:0`) with directory mode `0700` and file mode
`0600`; symlink/reparse paths and broader permissions fail closed. The proof secret exists only
in the test process/container callback and is removed during cleanup. No vault material, token,
OTP, trace, screenshot, video or raw log is uploaded.
The hosted Ubuntu runner invokes only the existing guarded OTP runtime preparer with `sudo pwsh`
because the container-owned vault is unreadable to the runner account. Its target, graph and
ownership checks remain active; other workflow steps run as the normal runner account.

## Release evidence checklist

1. Identify the exact release candidate SHA.
2. Run every applicable profile on that SHA with no retries.
3. Confirm each evidence manifest has schema `knora-runtime-verification-v1`, outcome `success`,
   complete selected/executed scenarios, tool/image identities, timestamps and report hashes.
4. Validate all manifests before release:

   ```powershell
   python scripts/runtime_evidence.py validate $sha `
     .verification/runtime/application/evidence.json `
     .verification/runtime/otp/evidence.json `
     --profile application --profile otp
   ```

   A failed, cancelled, skipped, missing, empty or differently hashed report fails validation.
   Evidence for another SHA or a narrower scenario selection cannot satisfy acceptance.

5. For `application`, inspect the same run's resource-check log and require
   `RUNTIME_PACKAGE_RESOURCES_OK=<count>` with the manifest's expected count (currently 16),
   plus the application image identities. Manifest validation alone does not verify this
   stdout marker. Keep the full workflow successful, including cleanup; a marker alone is
   not runtime acceptance.
6. Retain the sanitized JSON and JUnit reports for 30 days with the workflow run. Do not retain
   `.env`, realm snapshots, authentication URLs, OTPs, tokens, traces, videos or broad logs.

Runtime evidence does not change branch protection or publish a release automatically. After a
published CI run is reviewed, require `CI required` from the GitHub Actions app with strict
checks. During migration, enable it before removing the former Prettier requirement, preserving
all other protection settings. Runtime evidence remains an explicit release record requirement for
changes to the related capability.

Future Qdrant, OCR, DeepEval and Langfuse checks must follow the extension rule in the CI design:
cheap deterministic contracts belong in required CI; real multi-service or model checks require a
named profile, pinned inputs and an explicit release mapping. Empty jobs and pass-through evidence
are not valid extensions.

Java configuration follows [Spotless Maven documentation](https://github.com/diffplug/spotless/tree/main/plugin-maven#google-java-format).
