# Issue 188 Secrets Shadow Implementation Plan

> Execute this plan inline with the approved Issue #188 scope.

**Goal:** Add an offline, opt-in secrets-presence shadow that scans reviewed synthetic text and saved Knora output without changing user responses or enforcement, and reports detection plus false positives with immutable provenance.

**Architecture:** A pure scanner adapter accepts text and returns sanitized finding metadata; a runner loads a native saved capture or synthetic cases, preserves scope/status/IDs, computes confusion metrics only for reviewed labels, and publishes a local immutable supplement through the existing atomic report writer. The runner never calls Q&A, a provider, a model, or canonical Workbench APIs.

**Tech Stack:** Python 3.12, pytest, Guardrails core 0.11.0, SecretsPresent 0.1.0, detect-secrets 1.5.0 in an opt-in requirements file.

**Spec:** Issue #188 audit/proposal comment https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6186579899

## Global Constraints

- Keep Guardrails enforcement OFF and user responses/citations/refusals unchanged.
- Keep injection, PII, and dangerous-output detectors not_run in this slice.
- Keep raw input, secret matches, canaries, and validator reasons local; reports contain IDs, digests, finding types, counts, and safe diagnostics.
- Do not edit #153 gold, M3/DeepEval helpers, backend runtime, CI, canonical Workbench contracts, or shared dependency extras.
- Do not call a provider, download a model, use Cloud credentials, or spend money.
- Treat missing evidence, failures, timeouts, and unreviewed labels as unavailable, never as PASS or a metric denominator.
- Use source artifact SHA 6daa50d8876efa79663ae433c7a0b2b8028a6f0091a8602d4fdd080dc7224729 only as an unlabelled saved-output smoke input.

---

### Task 1: Define behavior with failing tests

Files: evals/test/test_security_shadow.py; evals/test/fixtures/security_shadow/cases.json; evals/test/fixtures/security_shadow/capture.json.

Tests import scan_text, evaluate_cases, load_capture_units, and write_shadow_report from new modules. Cases use case_id, scope, text, and reviewed label. Cover sanitized findings, TP/FP/TN/FN and precision/recall/FPR, unavailable evidence, capture identity, duplicate rejection, and no raw match in report.

- Write tests first.
- Run python -m pytest evals/test/test_security_shadow.py -q and confirm collection fails because implementation modules do not exist.

### Task 2: Minimal local scanner adapter

File: evals/scorers/security_shadow.py.

Interface: scan_text(text: str, validator) -> dict returns status, finding_type, and safe diagnostics. It calls only a supplied local validator and maps pass/fail/error/timeout to typed statuses; it never enables fix/reask/enforcement.

- Implement only what Task 1 requires.
- Run the focused tests green.

### Task 3: Offline case/capture runner and immutable report

File: evals/runners/run_security_shadow.py.

Interfaces: load_capture_units(path) reads saved native capture fields, preserves IDs/status, and marks absent generation evidence unavailable. evaluate_cases(cases, scan) computes metrics only for reviewed positive/negative labels and returns explicit unavailable/error counts. write_shadow_report(path, report) adds schema/provenance digests and uses evals.runners.evaluation.write_report_atomic without overwriting an existing path. CLI takes explicit paths and never performs Q&A or network calls.

- Implement validation, metric aggregation, safe diagnostics, and atomic publication.
- Run focused tests until green.

### Task 4: Pin opt-in dependencies and create reviewed synthetic fixture

Files: evals/requirements-security-shadow.txt; evals/test/fixtures/security_shadow/cases.json.

- Pin exactly guardrails-ai==0.11.0, guardrails-ai-secrets-present==0.1.0, detect-secrets==1.5.0. Core brings provider SDKs transitively; do not invoke them or download model weights. Keep this environment separate from backend dependencies.
- Fixture has 8 reviewed synthetic cases: 4 fake-secret positives and 4 benign negatives across Vietnamese/English, including multiline and boundary limitations.
- Verify wheel metadata/licenses and install only in the new worktree venv after tests are red.
- Run the local validator and record counts/latency without raw matches in output; unavailable/error stays explicit.

### Task 5: Document and verify

File: docs/development/issue-188-security-shadow.md.

- Document artifact pins, input SHA, population/denominator rules, measured result, and not-run threat groups.
- Run focused tests, Ruff format/check/lint, repository pytest, and Compose config; report baseline failures separately.
- Check git diff for raw secret leakage and confirm no shared/runtime files changed.

