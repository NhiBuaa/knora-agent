# Issue #188 offline security shadow

This is an opt-in, supplementary scan of saved Knora artifacts. It does not alter answers,
citations, refusals, enforcement, or the #153 gold artifact. Reports use the existing atomic
evaluation report writer and contain IDs, digests, counts, and safe diagnostics; raw text and
secret matches are not published.

## Pinned trial

- `guardrails-ai==0.11.0`
- `guardrails-ai-secrets-present==0.1.0`
- `detect-secrets==1.5.0`
- Python 3.12.15, in an isolated worktree environment. Guardrails transitive provider SDKs are
  installed as dependencies but are not invoked. No weights, provider calls, or credentials were
  used.
- Fixture: `evals/test/fixtures/security_shadow/cases.json`, SHA256
  `09d64242c694abee6017723b73c1dabd468f6125a0816c003337e05c40954d4a`.
- Owner label review: `labels.review.json`, bound to the exact fixture digest and Issue #188
  approval comment.

## Pilot result

`evals/reports/security_shadow/pilot-003.json` ran the eight reviewed synthetic units offline:

| TP | FN | FP | TN | Recall | False-positive rate |
|---:|---:|---:|---:|---:|---:|
| 3 | 1 | 1 | 3 | 0.75 | 0.25 |

The missed positive is the deliberately line-broken fake key. The false positive is the public
URL/checksum case. Population is 8/8 reviewed and evaluable; no timeout, error, or unknown rows.

The saved #153 smoke input is used only as unlabelled evidence. Its source SHA256 is
`6daa50d8876efa79663ae433c7a0b2b8028a6f0091a8602d4fdd080dc7224729`; the supplementary report
`evals/reports/security_shadow/pdf-smoke-002.json` records two unavailable, unreviewed units and
does not reinterpret the original failure or answer.

The PDF smoke was run without `--execute`: it has no usable detector result. It does not
establish that the saved output is free of secrets. Pilot findings remain 3 TP, 1 FN (split key),
1 FP (public checksum), and 3 TN; the implementation is an experimental baseline, without
security-quality acceptance.

## CI separation

Pure tests remain under `evals/test/test_security_shadow.py`. The real validator test lives in
`evals/integration/test_security_shadow.py`, executed by the required Security shadow CI job with
only its own pinned dependencies and pytest. Missing dependencies fail the test, never skip it.
Backend dependencies remain unchanged. Enforcement and export remain OFF.

## Boundaries

Only secrets-presence was trialled. Prompt injection, PII, and dangerous-output detection remain
`not_run`. This is shadow-only: `enforcement=off` and `release_gate=false`. The worker blocks
Python-level socket/subprocess audit events and uses offline/telemetry-disabled settings; this is
an application-level guard, not an OS firewall guarantee.
