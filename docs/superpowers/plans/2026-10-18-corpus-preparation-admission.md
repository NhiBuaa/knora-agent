# Corpus Preparation Admission Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task by task, with an independent review through requesting-code-review.

**Goal:** Materialize and activate exactly two retained READY PDF versions under a separate, one-shot trusted-host authority.

**Architecture:** An immutable preparation plan pins the frozen dataset, owner, Workspace/document revisions, originals, configurations and two job identities. A dedicated PostgreSQL adapter admits both jobs atomically as single-attempt processing jobs, reuses PdfDerivationHandler and the existing fenced PDF finalizer, and excludes these jobs from ordinary worker claim/recovery. LiveAdmission owns the durable operation record, provider request budget, deadline and stop latch. Existing binding preparation stays read-only.

**Tech Stack:** Existing Python, SQLAlchemy, PostgreSQL, SQLite, httpx and pytest; no new dependencies.

**Spec:** docs/design/evaluation-workbench.md; approved A in the owner conversation, following #192 comment6245866319.

## Global Constraints

- Implementation/offline/mock verification only; no runtime, real provider calls, cost, export, merge or deployment.
- Exactly two READY sources; preserve DocumentVersion, Gold v1, thresholds and historical results.
- One job attempt per source; no retry or recovery under this authority. Interrupted work requires a new reviewed plan/approval.
- QA, scoring, proposals and binding approval remain separate. No endpoint, browser registration or default profile.
- Check authority before admission, provider dispatch and immediately before activation commit. Roll back on expiry, stop or drift.
- Exact diff ACK from #153 before shared coordination.py edits; no submission, schema or historical migration changes.

## Task 1 — Durable corpus authority

**Files:** evaluation/live_admission.py; test/evaluation/test_corpus_preparation.py.

- [x] Add failing tests: corpus purpose accepted, another purpose rejected for corpus mutation, exact payload required, concurrent/restarted operation cannot replay, expiry/stop deny mutation after the last HTTP attempt.
- [x] Extend allowed purpose with `corpus_prepare`; add `check_mutation(scope)` and `corpus_operation(scope, payload)` using the existing SQLite journal and stop latch.
- [x] Run focused tests including existing LiveAdmission tests. An operation inserts its input/provenance before mutation, retains STARTED on crash, and finishes COMPLETED only after both activations.

```python
with admission.corpus_operation(scope, plan.payload()):
    admission.check_mutation(scope)
```

## Task 2 — Exact preparation and fenced activation

**Files:** evaluation/corpus_preparation.py; adapters/postgres/corpus_preparation.py; adapters/postgres/ingestion_jobs/coordination.py; corresponding offline tests.

- [x] Add immutable `CorpusSourcePin` and `CorpusPreparationPlan`; reject duplicate/non-READY/missing originals, non-two source plans and invalid revision/configuration pins.
- [x] Add `prepare_corpus(plan, admission, store, handler, provider_client, runtime)`: preflight, durable operation, atomic admission, real handler, existing fenced activation. Check the actual provider client marker; propagate the dispatch context; stop on any failure and never retry.
- [x] Add PostgreSQL adapter: read/lock persisted owner, frozen reference, source/original/version and document state; create only the two pinned processing jobs/attempts using existing immutable configuration helpers; change current pointers only to pinned versions. Validate again before the transaction exits.
- [x] Prepare exact shared coordination patch in a temporary file and obtain ACK before applying: exclude operation `corpus_prepare` from ordinary claim/recovery; require an explicit scoped activation guard for that operation before derivation writes and at commit. Preserve ordinary paths.
- [x] Verify offline SQLite/mocked-session transactions: exact two source reuse, no Gold writes, single attempts, source/config/owner/revision drift, denied finalization without authority, rollback after stop/expiry, unrelated jobs untouched. Existing finalizer/handler tests cover normal fenced persistence.

```python
result = prepare_corpus(plan, admission=admission, store=store,
                        handler=handler, provider_client=guarded_client, runtime=runtime)
assert len(result) == 2
```

## Task 3 — Evidence and review

**Files:** docs/design/evaluation-workbench.md; CONTEXT.md; docs/development/issue-192-workbench-verification.md.

- [x] Record approved separate authority and interrupted-job behavior; retain earlier evidence as historical.
- [x] Run focused tests, Ruff format/check/lint and diff check. No maintained shared-format selection changed. Run broader offline tests only for affected seams.
- [x] Independent finite source review; fix material findings and reverify.
- [ ] Commit/push to draft PR202, verify exact-head CI, publish/read back checkpoint and Project status.
- [ ] Report remaining real execution, binding, viewer and quality gates; do not mark the whole Goal complete.
