# CI foundation verification

Date: 2026-10-12 (Asia/Ho_Chi_Minh)

Branch: `ci/foundation`

Initial implementation commit: `0001bb5` (`ci: finalize strict runtime evidence and unified checks`)

This record covers local implementation, isolated container checks and the published PR
[#161](https://github.com/NhiBuaa/knora-agent/pull/161). Main protection now requires `CI required` with strict checks and GitHub Actions app 15368;
other protection settings are unchanged. No release Runtime Verification profile has been accepted.

## Automatic CI

The unified workflow is `.github/workflows/ci.yml`. It contains Frontend, Backend (Ubuntu and
Windows), Database, Keycloak, and the exact-result aggregate `CI required`. Owner approval on
2026-10-12 moved formatting into component jobs and superseded the independent Prettier check.
The former `Frontend formatting` workflow was removed.

The current pytest collection is 1,818 nodes:

| Partition                     | Selected |          Deselect/runtime accounting |
| ----------------------------- | -------: | -----------------------------------: |
| Backend portable (Linux)      |    1,245 |                       573 deselected |
| Backend Windows               |      222 |                     1,596 deselected |
| Database                      |      347 |                     1,471 deselected |
| Explicit runtime/manual nodes |        4 |          excluded from PR partitions |
| Total collection              |    1,818 | partitions are disjoint and complete |

The portable suite includes runtime-evidence and component-result validator tests. Every required PR suite
uses a JUnit report and `scripts/ci_checks.py`; missing, empty, failed, skipped, duplicate, or
inconsistent reports fail validation. `CI required` accepts only the exact four component dependency keys,
each with result `success`, so failure, cancellation, skip, or missing jobs cannot become PASS.

## Evidence from this worktree

- Full default pytest after the hosted-run corrections: **1,802 passed, 4 skipped**, exit 0. The four skips are the existing
  manual/runtime-only scope retained by the default local suite; required CI partitions select no
  skipped tests.
- Linux portable partition in the isolated `knora-ci-foundation-linux` container: **1,202 passed**,
  strict report validation passed.
- Windows partition at `0001bb5`: **220 passed**, strict report validation passed.
  A later 222-case partition run during overlapping local browser checks had **219 passed,
  3 failed** in real PDF-isolation preflight. The subsequent full default pytest rerun above
  passed all Windows nodes. The failed partition report is not counted as qualifying evidence.
- Database partition against isolated PostgreSQL/pgvector, rerun in a Linux Python 3.12 container
  with a 2 GiB cgroup memory limit: **347 passed**, zero skips; strict report validation passed.
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

## Hosted qualification

The owner authorized renaming the branch to `ci/foundation`, pushing it and creating PR #161
against `main`. The first hosted [CI run](https://github.com/NhiBuaa/knora-agent/actions/runs/38219068548)
on head `fed96adac4d99811c7ca7c72c82847863f3e28f6` failed correctly: Prettier and Keycloak passed;
Frontend, Backend Ubuntu, Backend Windows and Database failed; `CI required` failed.

The failure causes and corrections are:

- Backend Ubuntu: five immutable evaluation provenance checks need historical Git objects;
  backend checkout now fetches full history. The five tests passed in a focused rerun.
- Backend Windows: Compose 2.40.3 omits `create_host_path: false` in canonical JSON. The runtime
  guard accepts omission and still rejects explicit true; both cases have regression coverage.
- Database: normal runner cgroup permissions cannot enforce PDF worker limits. The disposable
  memory-limited Linux container executes all 347 contracts without weakening extraction guards.
- Frontend: Linux Chromium font hinting changes text advances. Typography uses geometric text
  rendering, controls inherit it, and menu triggers retain their normal dropdown placement.
  A workspace-menu assertion guards placement. Existing fixture readiness waits now precede
  interactions, preventing checkbox initialization from overwriting a premature click. Existing
  assertions and visual baselines were not weakened.

The corrected hosted [run 38259796127](https://github.com/NhiBuaa/knora-agent/actions/runs/38259796127)
passed all seven checks at head `e1014afcf0af0fee95596772162a69c11042a195`, checkout
`ca60591b2506e22deb6a872f4faa675abbdfd49c`. This qualifies the original separate-format workflow;
the subsequent component-format consolidation requires its own successful hosted run.

PR #161's checks record hosted qualification for each published branch head. Each run's
`ci-subject.json` artifact records the exact checkout SHA, PR head SHA, run ID and attempt; require
successful checks for the current head before integration. No merge or deployment has been
performed. The approved migration enables the already verified `CI required` before removing
the former Prettier requirement, preserving strict mode and the Actions app binding. Runtime evidence remains an explicit release
acceptance record for the affected capabilities.

Future Qdrant/OCR/DeepEval/Langfuse work follows the design rule: cheap deterministic contracts in
required CI; real multi-service or model checks in a named profile with pinned inputs and explicit
release mapping. No paid AI benchmark is invoked by PR CI.

## Component formatting consolidation

Approved on 2026-10-12; Python formatting baseline commit `0b24253`.

- Removed the independent format job. Frontend runs frontend/shared Prettier before its tests;
  Backend Ubuntu checks Python format before lint/tests. Database and Windows share that Python
  source gate and remain mandatory aggregate dependencies.
- Ruff 0.17.0 is pinned; Markdown is excluded so historical Python code examples remain untouched.
  All 143 changed tracked Python baseline files have identical ASTs to their original versions.
- Maven Spotless 3.10.4 and google-java-format 1.24.0 use AOSP style to retain four-space Java
  indentation. Check is bound to validate and covers all 16 maintained provider/test/probe Java
  files. Initial verify rejected formatting before any tests; apply followed by clean verify
  passed 11 unit and 23 flow cases. Both XML suites passed strict validation.
- The first default pytest run rejected 13 cases because uncommitted formatted runtime sources
  differed from Git HEAD. The provenance guard was preserved. After committing only the pure
  Python formatting baseline, all 14 process-probe tests passed and the full rerun passed
  **1,814 cases with 4 explicit manual/runtime skips** (425.14 seconds, exit 0).
- Exact-four-component aggregate tests: **56 passed**. Every component failure/cancellation/skip
  and missing result is rejected; the obsolete format dependency is rejected as an extra key.
- Ruff format/lint, frontend/shared Prettier, OpenAPI, Compose and actionlint checks passed.
- Main protection migration was performed in two verified API updates: first both Prettier and
  the already green CI required, then CI required only. Strict mode and Actions app 15368 were
  preserved; every other protection field compared equal before and after.

These local checks cover the consolidation working tree on the formatting baseline. The new
PR head must pass hosted CI; its ci-subject artifact records the exact tested checkout/head.
The formatting scope and excluded languages are specified in the CI runbook.
