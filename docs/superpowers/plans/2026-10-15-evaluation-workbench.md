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

## Technical checkpoint — 2026-10-16

The checklists above remain the acceptance scope, not an assertion that product acceptance is
complete. PR #202 contains the contract, R1, A1/A2, R3 and A3 technical checkpoints. R2 is added
on the same coordinator branch after independent review; no additional framework or issue.

R2 touches the existing run persistence/table plus migration0051 (after unmerged0050), HTTP/main
wiring, native evaluator/DeepEval wheel inclusions, fixed BFF routes, Runs UI and regenerated
OpenAPI. Dependencies do not change. Its supported mappings are M3 and explicit Builder PDF gold;
#153's existing PDF contract is not assumed compatible. Saved Q&A, deterministic reports and gold
remain unchanged. Default provider registries remain empty; live profiles are blocked.

Local R2 evidence (Python3.12, existing evaluation-pilot venv; no model or network transport):

| Verification | Result |
| --- | --- |
| Evaluation suite + HTTP datasets/runs/scoring + SQL dataset/run tests + native DeepEval/Ragas tests | 214 passed |
| Operator/Runs UI and BFF tests | 131 passed, 16 files |
| Ruff format, format check and lint | Passed |
| Frontend format, format check and typecheck | Passed |
| OpenAPI exporter check | Passed |
| Alembic heads | Single proposed head0051; not applied |
| Backend wheel build and native scorer/evaluator inclusion check | Passed |

Independent review found callback mutation could change provenance and cancellation could label
a dispatched judge call NOT_RUN. Regression tests failed before fixes and pass afterward. Input,
result and scorer configuration are now isolated snapshots; dispatch checkpoints uncertainty
before calling the judge, with idempotent recovery and no replay.

At coordinator cc0cc48, Ubuntu, Database, Frontend and Keycloak CI jobs passed; Windows failed
waiting20s for a launcher fixture's DEV_READY. The exact Windows test passed locally in5.81s.
No timeout or validation was relaxed. This is not proof the CI failure is resolved; the updated
PR head still needs its required CI result.

Remaining product evidence: explicitly owned browser/runtime walkthrough, actual PostgreSQL
concurrency behavior for new scoring batches, runtime binding and separately approved live model
quality/calibration. No shared services or databases were started/changed. Do not mark slices
accepted or #192 Done from offline technical tests. Keep #188 shadow outputs supplementary, reuse
native source/capture identities, and serialize shared file/migration integration with #153/#188.

Subsequent completion audit found the service fixtures were the only profile-composition path.
The existing application factory now accepts explicit trusted native/PDF/proposal/scoring profile
arguments, all empty by default. Composition and default-denial tests plus evaluation, bootstrap
and main lifecycle tests pass223 cases. No provider/corpus preparation runs during composition.
This closes the host-composition seam only: actual retained-source corpus preparation, reviewed
binding construction and approved live admission remain implementation/acceptance work, not just
permission to press Run. See the current product audit in Issue192 comment6199348185.

## Takeover checkpoint — 17 October 2026

The preceding paragraphs are historical checkpoints. At `7ee019d`, all six CI checks, including
CI required, succeeded. The reviewed corpus adapter and new deterministic UI run now exist; the older statements
that those were missing are superseded. The run remains SEMANTIC_PENDING with a false refusal and
coverage 0/1. Runtime files are retained, but the old services are stopped and logical database
recovery has not been verified. See the [current acceptance matrix and evidence](../../development/issue-192-workbench-verification.md)
for exact identities, PostgreSQL concurrency follow-up, shared-file ACK and remaining acceptance.
No historical result, gold, threshold or activation restriction is changed by that update.
