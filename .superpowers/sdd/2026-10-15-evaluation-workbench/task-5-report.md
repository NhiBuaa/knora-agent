# R3 / #198 technical checkpoint

Status: offline implementation verified; owner UI/model acceptance remains pending.
Base: `0a6ca4a` (A2 integrated checkpoint).

## Change

- Existing Runs service/store/API/UI now accepts exact frozen Builder PDF references and case IDs.
  DatasetSelection preserves version/digest and ordered context-only dependencies. Unsupported
  follow-up execution is an explicit preflight blocker.
- Reviewed runtime binding stays separate from immutable gold. It binds source SHA-256, runtime
  chunk/embedding sets, configurations, candidate budget and anchor alternatives. Review is not
  model/egress/quota approval. Server profiles are the only binding/endpoint authority.
- PDF HTTP capture uses existing public-response/citation/generation-evidence validators and exact
  `(workspace_id, trace_id)` correlation. Full ordered candidates and actual generation aliases are
  separate. Configuration, corpus, candidate rank and source drift fail observation validation.
- PDF deterministic reports use full fused evidence-group coverage, no K; generation coverage is
  diagnostic. AND groups/OR alternatives, valid miss=0, REFUSAL retrieval=N/A, zero denominator=null.
  Every selected case remains visible with applicable/evaluable denominators and failure reasons.
- Existing durable RunStore JSON fields hold the report/source snapshots; no schema/migration or
  shared dependency change. Indeterminate calls are not retried or resumed automatically.
- Runs UI accepts frozen PDF gold; readiness exposes case/source issues. Case/Report views show
  gold, evidence/PDF links, captured answer/citations, traces and all populations. Saved result
  refresh performs GET only. Read-only operators cannot start runs.

## Evidence

- Failing-first run/HTTP/UI fixtures were followed by fixes; pure scorer reviewed independently.
- Python 3.13: **132 passed** in `backend/test/evaluation`, HTTP Runs and SQL RunStore tests.
  Python 3.12: **130 passed** before adding the real-PDF workflow and missing-source regressions.
- Integration test uses retained public PDF, real local extraction, SQL DatasetStore, review/freeze,
  new offline observations and deterministic report. Frozen artifact remains byte-for-byte equal.
  SQL RunStore round-trip is also exercised with SQLite; PostgreSQL concurrency is not proven here.
- Operator/Run UI: **119 passed** across 14 files, including the GET refresh regression.
- Ruff format/check and lint, frontend Prettier/typecheck, OpenAPI exporter check and diff check
  passed. Compose config succeeded with missing local MinIO credential warnings (no service start).
- Standalone frontend production build passed before the last small refresh/link edits; typecheck
  and focused UI regressions cover those edits. Existing ConversationComposer image warnings remain.
- Independent review found stale report fields overwriting fresh checkpoints, original-PDF route
  prefix, and snapshot refresh gaps. Regression tests reproduce each and the fixes pass.

## Coordination and limits

#153 shared-file ACK: https://github.com/NhiBuaa/knora-agent/issues/158#issuecomment-6192449827.
R3 has no edits to answering algorithms, Postgres evaluation_reader or #153 PDF runner. #188 consumes
saved native artifacts and emits a separate local shadow report; no detector contract is added.

Default runtime profiles remain empty. No model/provider calls, runtime activation, migration,
export, enforcement, merge or deploy occurred. No live approval is inferred from offline tests.
The installed frontend lock reports 8 advisories (1 moderate, 7 high); no unsolicited upgrade was
made. Full repository tests were not rerun here: primary full collection previously lacked optional
DeepEval/Ragas; full frontend previously had a build-hook timeout. This is not full CI/quality PASS.

Next: integrate the reviewed R3 checkpoint in the coordinator, finish A3/R2 on saved artifacts,
prepare the concrete owned-runtime/Free quota/live-call approval for UI acceptance, and submit PRs.
