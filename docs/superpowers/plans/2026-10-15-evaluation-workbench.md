# Evaluation Workbench Implementation Plan

> For agentic workers: use executing-plans or subagent-driven-development to execute the approved
> slices and keep the remaining product acceptance requirements open.

**Goal:** PDF upload through human-reviewed frozen gold to new Q&A and a report on the Operator UI,
with supplementary Ragas proposals and DeepEval saved-capture scoring.

**Architecture:** Two application modules share the canonical dataset contract. Existing evaluation
runners/metrics and application Q&A seams remain authoritative. PostgreSQL/ObjectStore retain
metadata and artifacts; no second evaluation framework or infrastructure.

**Tech stack:** Existing Python backend, PostgreSQL, ObjectStore, Next.js Operator UI and evals.

**Spec:** [Approved design](../../design/evaluation-workbench.md), with exact scope and acceptance
details in [Issue #192](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6185802219).

## Global constraints

- No model calls, runtime changes, paid costs, merge, deployment or Done status without the
  corresponding separate authorization/acceptance.
- M3 and #153 native artifacts and semantics are unchanged; no regeneration of 16 PDF/60 gold.
- Gold may freeze with incomplete runtime binding. All selected cases and denominator exclusions
  remain visible. Execution completion does not imply quality PASS.
- Langfuse export and Guardrails enforcement are OFF. No new model download or paid fallback.
- Each implementer uses a distinct direct child of the canonical worktree container.
- Shared files have one coordinator; feature slices do not concurrently edit them.

## Task 1: shared contract checkpoint (#192)

Files: create `backend/src/knora/evaluation/contracts.py` and
`backend/test/evaluation/test_contracts.py`; add only needed package initializers. The coordinator
owns design/CONTEXT, capability policy, API schema coordination and integration.

Consumes the owner-approved contract; produces immutable typed PDF gold/evidence references,
digest-bound freeze, selections with explicit context-only dependencies, and independent binding
status. Legacy references remain format-specific and retain native digests.

- [ ] RED: semantic fixtures for source-anchored PDF gold, stable digest, tamper rejection, no-answer
  scope, multi-hop groups, follow-up cycles and selections; missing binding does not block freeze.
- [ ] GREEN: implement minimal standard-library types/validation/digest/selection behavior, without
  SDKs, persistence, UI, scoring thresholds or provider calls.
- [ ] Verify existing M3 full-loader validation before selecting two cases; legacy manifests and
  file bytes remain unchanged. Include fixture round trips, not source-text assertions.
- [ ] Run focused tests, Ruff format/check, and review diff before committing the common base.
- [ ] Derive HTTP request/response models from actual shared types while integrating R1/A1; run
  the repository OpenAPI exporter. Do not invent stub endpoints only to change generated files.

## Task 2: R1 new synthetic Q&A run (#193)

- [ ] Consume common dataset/selection types; implement Workspace-scoped catalog, durable run
  admission/preflight/progress/checkpoints and registered runtime profiles.
- [ ] Exercise existing production executor with exact correlated trace; preserve complete M3
  validation/sealing. No bootstrapping or credential hot reload in the measured Q&A path.
- [ ] Reuse retrieval/citation/refusal checks in an explicitly deterministic partial report with
  semantic fields pending, without bypassing the complete report validator.
- [ ] Implement typed HTTP/BFF and Runs UI: selection, readiness, start, progress, detail, case and
  report/trace links. Protect mutation requests and keep arbitrary URLs/commands out.
- [ ] Test authorization, idempotency/stale preflight, provider-denial/attempt limits, failures,
  crashes/indeterminate dispatch and population preservation; demonstrate new offline Q&A/report.
- [ ] Keep live dispatch blocked until exact live approval, compatible owned runtime and enforced
  Workers Free/provider budgets are proven. Real-model acceptance is still required separately.

## Task 3: A1 PDF source preparation (#194), parallel with Task 2

- [ ] Reuse PDF extraction/ObjectStore/Document Version identity via a local-only preparation seam;
  bypass the existing handler's embedding/activation stage without weakening normal ingestion.
- [ ] Persist sources, immutable extraction snapshots and retention references with original-PDF
  access checks. Failed extraction stays visible; unsupported OCR is not silently performed.
- [ ] Implement typed HTTP/BFF and Datasets upload/status/original/source-page UI.
- [ ] Test real PDF limits/extraction, ownership, stale identity, idempotency/failure recovery,
  authoritative deletion protection and zero embedding/generation calls.
- [ ] Demonstrate upload through source review; A2 owns case authoring/freeze.

## Tasks 4–7: remaining MVP slices

- [ ] A2/#195: basic case editor, human review and immutable freeze with original-source checks,
  digest/revision concurrency and retained-source protection.
- [ ] R3/#198: use manual A2 gold and existing R1 workflow for new PDF Q&A; independently validate
  full-candidate coverage, generation diagnostic, applicability and visible unscorable cases.
- [ ] A3/#197: extend Ragas PDF proposal mapping, reviewed evidence/provenance, VI/EN and 12-draft
  maximum, with separate live approval. Validate supported categories instead of assuming support.
- [ ] R2/#196: DeepEval on exact saved captures, no re-answer; initial supported M3 mapping and
  explicit PDF mapping after R3. Keep human calibration/semantic acceptance distinct from execution.

## Integration and acceptance

- [ ] Regenerate OpenAPI; run frontend/Python/shared formatting and AGENTS.md verification, with
  database/browser tests on an explicitly owned isolated test runtime when authorized/available.
- [ ] Independent review plus CI required for proposed PRs. Resolve concrete findings; no automatic
  integration into main/test or another session's branch.
- [ ] Prepare UI walkthrough/evidence for PDF → manual review/freeze → new Q&A → deterministic
  report, then supplementary Ragas/DeepEval evidence within approved live bounds.
- [ ] Owner acceptance, rather than SDK installation or green plumbing tests, closes the MVP.
