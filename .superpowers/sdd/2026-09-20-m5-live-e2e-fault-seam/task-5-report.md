# Task 5 report — complete M5.4 live E2E fault gate

## Result

`PARTIALLY_VERIFIED`

The complete load-bearing gate passed on the tested product commit, and both live fault scenarios
passed through the real Keycloak, Next.js BFF, backend, and Chromium path. The release gate remains
unclaimed because the product deletion policy is still unavailable; that observation is preserved as
`blocked/DOCUMENT_DELETION_POLICY_UNAVAILABLE`, not relabeled as a deletion pass.

Tested product commit: `49a1f8f2c94a5866ad689f5ada3331023dd3267e` (`test(m5): cover live fault and interruption states`).

Evidence/documentation commit: the Task 5 evidence-only commit created after verification (its SHA
is distinct from the tested product commit and is returned with this report).

## Required gate

All required commands exited successfully:

- `.\.venv\Scripts\python -m pytest` — `1054 passed, 3 skipped`.
- `.\.venv\Scripts\ruff check .` — passed.
- `docker compose config --quiet` — passed.
- `git diff --check` — passed.
- `frontend/npm test` — `17` files, `49` tests passed.
- `frontend/npm run typecheck` — passed.
- `frontend/npm run lint` — passed with no ESLint warnings or errors (Next.js deprecation notice only).
- `frontend/npm run build` — passed; all routes generated.
- `frontend/npm audit` — `0 vulnerabilities`.
- `frontend/npm run test:e2e` — `14 passed`.

The E2E run used the existing isolated Compose stack and process-only fixture environment values
from the local test Keycloak realm. No credential value, token, cookie, database URL, raw provider
payload, or raw exception text was recorded.

## Live scenario evidence

The append-only ledger now contains two records with exact `environment: "live-keycloak-playwright"`
and the tested product commit:

- `PROVIDER-FAILURE` — `LIVE_E2E_PASS`; public alert `Request failed: PROVIDER_REQUEST_FAILED`,
  with no final answer, citations, or trace.
- `STREAM-INTERRUPTION` — `LIVE_E2E_PASS`; public alert `The request was interrupted. It was not
  completed.`, with no final answer, citations, or trace.

Both scenarios used real authorization-code plus PKCE login and the approved isolated one-shot fault
seam. No browser interception, synthetic SSE, direct database seeding, fabricated session, or mocked
outcome was used.

## Final status and concerns

- Provider-failure/interruption live blocker: removed; both scenarios passed.
- Deletion policy: still unavailable (`blocked/DOCUMENT_DELETION_POLICY_UNAVAILABLE`); retained as
  unavailable evidence and not a successful deletion.
- M5.4 release gate: not claimed complete until the deletion policy is changed or an approved live
  deletion path exists.
- Evidence JSONL parsed successfully after the append, and the final secret-value scan found no
  fixture password values in tracked evidence/report files.
