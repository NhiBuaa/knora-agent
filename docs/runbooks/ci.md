# CI and Runtime Verification

## Pull request checks

The automatic workflow runs the existing backend, frontend, database and Keycloak contracts.
Formatting runs inside the owning component job; `CI required` is the required branch protection
check. The former independent `Prettier format check` is replaced by this aggregate. Report XML is strict: missing,
empty, failed, skipped or duplicate cases fail the job.

No AI provider credentials, developer `.env` files, model benchmarks, or real application E2E
services are used by pull request CI. Browser fixtures are synthetic and offline.

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

## Runtime Verification

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

The `application` profile runs fresh isolated identity, document, conversation, Workspace and
Operator journeys. Controller-owned PDF/Turn scenarios are excluded and remain release gaps until
their own fresh processing/controller evidence exists. The `otp` profile runs the native Mailpit
journey and eight essential two-node storage cases. Crash, outage, activation and commit-reply
fault cases are separate acceptance scopes and are never silently counted as the base OTP pass.

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

5. Retain the sanitized JSON and JUnit reports for 30 days with the workflow run. Do not retain
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
