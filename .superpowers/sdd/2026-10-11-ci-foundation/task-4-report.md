# Task 4 report — Runtime Verification

## Implemented

- Added manual-only `.github/workflows/runtime-verification.yml` with full-SHA checkout,
  workflow-source SHA/run provenance, no paid-provider credentials, and sanitized artifact upload.
- Added `scripts/run-runtime-verification.ps1` for fresh guarded application and OTP profiles.
  Application selections are self-contained identity, documents, operator, Workspace and
  conversation navigation journeys; controller-owned PDF/Turn cases stay excluded.
- Added `scripts/runtime_evidence.py` with schema
  `knora-runtime-verification-v1`, exact-SHA/profile/scenario checks, strict JUnit validation,
  report hashing, provenance validation and sanitized report copies.
- Added focused negative-case tests and release runbook documentation.
- Added a narrowly scoped Linux vault guard for the existing OTP preparer (container UID `1000:0`,
  modes `0700`/`0600`, reparse/symlink rejection). The wrapper invokes only that guard through
  `sudo pwsh` after ownership transfer; all other workflow steps stay unprivileged.
- Added an OTP proof callback so the Maven proof suite executes while the existing ephemeral
  proof secret is in scope; the preparer's `finally` removes it.

## Verification

- `python -m pytest backend/test/config/test_runtime_evidence.py -q`: **26 passed**.
- `python -m ruff check scripts/runtime_evidence.py backend/test/config/test_runtime_evidence.py`:
  **all checks passed**.
- PowerShell parser checks passed for the runtime wrapper and OTP preparers.
- Workflow YAML parsed successfully; `git diff --check` passed.
- The wrapper's deliberate wrong-SHA invocation failed with `RUNTIME_SUBJECT_SHA_MISMATCH`.

GitHub publication, actionlint and fresh Docker runtime execution were unavailable in this local
worktree. No runtime success manifest was produced locally. The release validator is fail-closed
until each profile has complete evidence for the exact candidate SHA.
