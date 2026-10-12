# CI and Runtime Verification

## Pull request checks

The automatic workflow runs the existing backend, frontend, database and Keycloak contracts.
`Prettier format check` remains an independent check; `CI required` is the aggregate check to add
to branch protection after the first published run succeeds. Report XML is strict: missing,
empty, failed, skipped or duplicate cases fail the job.

No AI provider credentials, developer `.env` files, model benchmarks, or real application E2E
services are used by pull request CI. Browser fixtures are synthetic and offline.

Database PDF integration tests run in a disposable Linux container with a 2 GiB memory limit
and a delegated cgroup memory controller. That container requires privileged execution on the
ephemeral GitHub runner so the real extractor can enforce its child-process limits. Failure to
configure isolation fails the job; these tests do not substitute a mocked extractor. Backend
checkout includes full Git history for immutable evaluation provenance checks.

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
published CI run is reviewed, add `CI required` alongside `Prettier format check` in the repository
branch protection settings. Runtime evidence remains an explicit release record requirement for
changes to the related capability.

Future Qdrant, OCR, DeepEval and Langfuse checks must follow the extension rule in the CI design:
cheap deterministic contracts belong in required CI; real multi-service or model checks require a
named profile, pinned inputs and an explicit release mapping. Empty jobs and pass-through evidence
are not valid extensions.
