# Milestone 2 — Production-shaped ingestion

Status: completed and accepted on 2026-08-11.

Milestone 2 adds durable, Workspace-scoped PDF ingestion to Knora. A PDF upload creates or
reuses an Ingestion Job. A separately composed worker extracts, chunks, embeds and activates the
new derivation only after the complete fenced transaction succeeds. Existing Markdown/plain-text
ingestion and cited answers remain compatible.

## Delivered scope

- Durable PDF submission, request idempotency, source-version identity and ObjectStore staging.
- Deterministic, isolated PDF extraction with versioned normalization, page-bounded chunks and
  configured raw-size, page, stream, timeout and memory limits.
- PostgreSQL claim/lease/fencing, four-attempt retry policy, expiry recovery, attempt history and
  atomic derivation/activation CAS.
- Public job polling, safe lifecycle and serving-state projections, current-version reprocessing,
  audit, idempotency and PDF citation provenance.
- Retained Original Source Objects, independent cleanup/reconciliation lifecycle work, S3-compatible
  storage, operational metrics and versioned alerts.

## Acceptance record

- Closed specification and design ledger: [GitHub Issue #14](https://github.com/NhiBuaa/knora-agent/issues/14).
- Accepted release gate: [GitHub Issue #21](https://github.com/NhiBuaa/knora-agent/issues/21).
- Candidate: `1ac2aac7259d2dcd0faf307883aeafb471e8ac0d`.
- Final Evaluation: [m2-issue-21-r3](../../../.agents/manual-tests/milestone-2/21-regression-release-gate-r3-run-20260811-01-approved.json).
- Verification: 434 pytest cases passed; three explicitly approved manual-fixture skips remained in
  the full suite; the three fixtures also passed when run with `KNORA_RUN_MANUAL_ACCEPTANCE=1`.
- Criterion traceability: 118 of 118 rows passed. No technical blocker remains.

Future work begins in Milestone 3. It must not reinterpret or weaken Milestone 2 contracts without
an approved design change.
