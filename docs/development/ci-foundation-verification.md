# CI foundation verification

Date: 2026-10-12 (Asia/Ho_Chi_Minh)

Branch: `codex/ci-foundation`

Implementation commit: `0001bb5` (`ci: finalize strict runtime evidence and unified checks`)

This record covers the local implementation and isolated container checks. It does not claim that
GitHub Actions has run, that branch protection was changed, or that a release Runtime Verification
profile has been accepted.

## Automatic CI

The unified workflow is `.github/workflows/ci.yml`. It contains the independent required check
`Prettier format check`, jobs for Frontend, Backend (Ubuntu and Windows), Database, Keycloak, and
the exact-result aggregate `CI required`. The former `Frontend formatting` workflow was removed.

The current pytest collection is 1,804 nodes:

| Partition | Selected | Deselect/runtime accounting |
| --- | ---: | ---: |
| Backend portable (Linux) | 1,233 | 571 deselected |
| Backend Windows | 220 | 1,584 deselected |
| Database | 347 | 1,457 deselected |
| Explicit runtime/manual nodes | 4 | excluded from PR partitions |
| Total collection | 1,804 | partitions are disjoint and complete |

The extra 31 portable nodes include the runtime-evidence validator tests. Every required PR suite
uses a JUnit report and `scripts/ci_checks.py`; missing, empty, failed, skipped, duplicate, or
inconsistent reports fail validation. `CI required` accepts only the exact five dependency keys,
each with result `success`, so failure, cancellation, skip, or missing jobs cannot become PASS.

## Evidence from this worktree

- Full default pytest: **1,800 passed, 4 skipped**, exit 0. The four skips are the existing
  manual/runtime-only scope retained by the default local suite; required CI partitions select no
  skipped tests.
- Linux portable partition in the isolated `knora-ci-foundation-linux` container: **1,202 passed**,
  strict report validation passed.
- Windows partition: **220 passed**, strict report validation passed.
- Database partition against isolated PostgreSQL/pgvector: **347 passed**, strict report validation
  passed.
- Frontend Vitest: **447 passed**; fixture Playwright: **133 passed**, zero skips. Combined strict
  report validation: **580 passing test cases**.
- Frontend `format` followed by `format:check`, typecheck, lint and production build passed.
- Keycloak Maven: **11 unit + 23 flow tests passed**, zero skips; Surefire and Failsafe XML each
  passed strict validation.
- Runtime evidence and CI validator tests: **75 passed** (31 runtime-evidence tests plus the CI
  validator suite).
- Repository Ruff, Compose configuration (with synthetic credentials), OpenAPI export check,
  `git diff --check`, and actionlint 1.7.12 passed.

The frontend fixture exporter ran offline from pinned FreeMarker and Keycloak theme artifacts. The
fixture suite does not start backend, Keycloak, or a real application account; service-backed
journeys remain in Runtime Verification.

## Runtime Verification status

`.github/workflows/runtime-verification.yml`, `scripts/run-runtime-verification.ps1`, and
`scripts/runtime_evidence.py` implement the manual `application` and `otp` profiles. Evidence is
bound to a full 40-character subject SHA, records workflow/source SHA separately, validates report
hashes and scenario counts, and records explicit excluded scenarios with their release
limitations. Sanitized JUnit is the only report form emitted by the helper.

The helper's negative cases cover SHA mismatch, invalid or missing profile, unsuccessful outcome,
changed or invalid reports, missing provenance, incomplete scenario selection/counts/exclusions,
and duplicate evidence. A complete live application/OTP profile was not run in this local session;
there is therefore no release evidence manifest to accept. A clean hosted/manual run is required
for any release that changes those capabilities.

## Publication boundary

No push, pull request, merge, branch-protection update, deployment, or GitHub-hosted workflow run
was performed. After publication, run the workflow once, review the five job results, then add
`CI required` alongside the preserved `Prettier format check` status. Runtime evidence remains an
explicit release acceptance record for the affected capabilities.

Future Qdrant/OCR/DeepEval/Langfuse work follows the design rule: cheap deterministic contracts in
required CI; real multi-service or model checks in a named profile with pinned inputs and explicit
release mapping. No paid AI benchmark is invoked by PR CI.
