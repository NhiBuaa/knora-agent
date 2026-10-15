# Retrieval V3 S2 (Qdrant BM25-only) Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` after the owner approves this whole plan. Steps use checkbox syntax for tracking.

**Goal:** Deliver an opt-in BM25-only retrieval path whose lifecycle is PostgreSQL-authoritative, whose Qdrant projection is rebuildable and isolated, and whose evaluation is comparable with the frozen Baseline B without changing the 16-PDF/60-case corpus or metric contracts.

**Architecture:** PostgreSQL remains the authority for workspace authorization, document versions, chunk sets, lexical generations, desired revisions and active pointers. Qdrant is a searchable projection containing deterministic generation/chunk identities and raw native BM25 scores; it is never a source of truth for eligibility, content, citations or provenance. The application keeps the existing answering, selector, citation and evaluation facades and enables the new path only through an explicit lexical configuration.

**Tech Stack:** Existing Python/PostgreSQL application and Alembic lifecycle, Qdrant Server `1.19.2` with `qdrant-client` `1.19.1` as compatibility candidates, the existing filesystem object-store adapter for the isolated run, existing pytest/Ruff/Compose CI, and deterministic fixtures. Native Qdrant BM25 is used through a thin adapter; no FastEmbed, neural model download, Cloudflare call, judge or second evaluation framework is added.

**Spec:** Issue [#153](https://github.com/NhiBuaa/knora-agent/issues/153), approved S1–S8 roadmap, ADR0013, ADR0018, and the S2.1 contract in `docs/development/issue-153-s2-1-checkpoint.md`.

## Global constraints

- Frozen corpus SHA: `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`.
- Frozen Gold SHA: `2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae`.
- Keep all 16 PDFs, 60 cases, 47 persisted chunks, 61 reviewed mappings, 25 missing anchors, eight controls, all missing/failed/not-run outcomes and the frozen Baseline B artifacts.
- Keep Baseline B's vector threshold `0.65` unchanged. BM25 raw scores are not cosine scores and receive no numeric cutoff in S2.
- Primary comparison is Top-8 from one saved native Top-200 result. Top-200 coverage and diagnostics are reported separately. Retrieval coverage is never semantic correctness.
- PostgreSQL authorization and active-generation eligibility are checked before querying and revalidated before evidence, generation or citations. Qdrant outages and stale data are operational failures, not empty evidence.
- BM25 mode makes zero query-embedding calls and requires no fabricated `EmbeddingSet`. Dense and hybrid paths retain their existing embedding validation.
- No change to PR #189, frozen artifacts, historical metrics, security/provenance contracts, production defaults or deployment selectors.
- No model/provider calls, migration execution or service startup is authorized until this whole plan is approved. S2.4 uses saved Baseline B captures and deterministic generation stubs; a future live semantic rerun is a separate decision.
- S2 work is in separate PRs/worktrees under `C:\Developer\Projects\knora-agent-worktree`; no merge, deploy or Issue close is performed by the agent.
- Shared changes are coordinated with #158 and #192. Their evaluation/Workbench authority remains intact; S2 adds only versioned retrieval diagnostics and reads their public contracts.

## Current gate and coordination

S2.1 offline implementation is `e78a3b5f0d507916fcf6acce0adada6d037532cd` in Draft PR #201, stacked on S1 `a67842e`. The exact-head manual CI run is [38748177861](https://github.com/NhiBuaa/knora-agent/actions/runs/38748177861). It completed successfully: Keycloak, Database, Backend Ubuntu, Backend Windows and Frontend all report success; `head_sha` and the uploaded `ci-subject.json.checkout_sha` both equal the exact S2.1 SHA. This satisfies the S2.1 CI required gate. It does not change the scope of the prior 229 offline tests, and it is not a claim that the optional full local collection ran in the S1 interpreter.

The shared boundary request is recorded in `.verification/s2-boundary-request.md` and is being read by #158/#192. No common schema or runtime file is edited until concurrent ownership is acknowledged and the Alembic parent is verified.

> 🧠 **From Hindsight memory (Issue158 incremental DeepEval Ragas Langfuse evaluation)** — #153 retains the frozen PDF/gold projection and Knora retrieval authority while #158 integrates evaluation tools on that existing source; S2 therefore keeps diagnostics supplemental and does not create a second dataset, run authority or evaluation framework.

## Scope map and interfaces

| Slice | Main files | Produces | Does not change |
| --- | --- | --- |
| S2.1 | `answering/stores.py`, `answering/module.py`, `answering/retrieval_configuration.py`, `adapters/postgres/evaluation_reader.py`, `evals/runners/pdf_retrieval_v3.py` | Versioned lexical contracts, raw score/reason trace fields, candidate versus selected coverage | Dense/hybrid validation, public evaluation facade, frozen metrics |
| S2.2 | `ingestion/job_processing.py`, `ingestion/store.py`, `ingestion/search_indexing.py`, `adapters/postgres/search_index_store.py`, `adapters/postgres/tables.py`, one additive Alembic revision | PostgreSQL-authoritative lexical readiness, durable desired/active generations, CAS activation, retry/reconcile and lifecycle invalidation | PostgreSQL authority model, existing dense ingestion behavior, production defaults |
| S2.3 | `adapters/qdrant/search_index.py`, runtime settings/composition, `backend/pyproject.toml`, opt-in Compose verification profile | Native BM25 projection/query, tokenizer/IDF profile, tenant/stale isolation and compatibility evidence | Qdrant as authority, vector threshold, LangChain-wide migration |
| S2.4 | `evals/runners/pdf_retrieval_v3.py`, evaluation reader/report supplements, isolated fixtures and application E2E tests | Same-corpus Top-8/Top-200 comparison, failure taxonomy, evidence/citation and deterministic application proof | Baseline B captures, gold/corpus SHAs, semantic PASS claims |

The focused ports are deliberately small:

```python
class SearchIndexPort(Protocol):
    def stage_generation(self, generation: LexicalGeneration) -> StageReceipt: ...
    def query_top(self, request: LexicalQuery) -> tuple[LexicalHit, ...]: ...
    def remove_generation(self, generation_id: str) -> RemovalReceipt: ...

class SearchIndexStore(Protocol):
    def request_generation(self, request: GenerationRequest) -> DesiredGeneration: ...
    def activate_ready(self, request: ActivationRequest) -> ActiveGeneration: ...
    def reconcile(self, request: ReconcileRequest) -> ReconcileResult: ...
```

`LexicalHit` carries only point/generation/chunk identity, rank, raw score and score-policy digest. Authoritative text, source locator and citation data are loaded from PostgreSQL after authorization and revalidation.

## S2.1 — contract and trace gate

### Files and tests

- Existing S2.1 files listed above; no additional dependency or migration.
- Existing tests: `backend/test/answering/test_bm25_contract.py`, `test_module.py`, `test_issue_61_trace_contract.py`, `backend/test/adapters/postgres/test_evaluation_reader.py`, and `evals/test/test_pdf_retrieval_v3.py`.
- CI required: Backend Ubuntu/Windows, Database, Frontend and Keycloak; strict XML/report validation and Compose configuration.

### Acceptance

- Lexical candidates validate workspace, document version, chunk set, index generation, finite BM25 score and rank ordering.
- No embedding provider is invoked for lexical retrieval; dense/hybrid still fail closed on missing or mismatched embedding provenance.
- Raw branch score, rank, rejection reason, retrieved-candidate coverage and selected-generation coverage survive trace → reader → capture → report.
- Missing historical fields remain `unknown`/unavailable; no frozen metric denominator is rewritten.
- Exact-head CI evidence is attached to PR #201 before S2.2 implementation starts.

## S2.2 — lexical readiness and durable indexing lifecycle

### Data and authority design

1. Add additive PostgreSQL state keyed by `(workspace, document, document_version, chunk_set, lexical_profile)` with immutable generation identity, desired revision, readiness, active pointer, acknowledgement digest, retry metadata and failure reason. Do not add a second source of truth.
2. PostgreSQL transactionally records the desired revision and queues work. A worker extracts/normalizes chunks, stages deterministic Qdrant point IDs, verifies acknowledgement count/digest, then CAS-activates only the still-current desired revision.
3. A Qdrant write is not cross-database atomic. Crash-after-ack is repaired by reconciliation; repeated staging is idempotent. Lease version and worker fencing follow existing `ingestion/job_processing.py` patterns. Existing retry policy and maximum attempt runtime are reused rather than creating a new retry framework.
4. A source-version switch, archive, revoke or delete immediately removes the generation from PostgreSQL eligibility and increments the desired revision. Physical Qdrant deletion is asynchronous and idempotent; stale points can never be returned or cited while cleanup is pending.
5. A failed rebuild leaves the prior generation eligible only when the same source version/profile remains explicitly eligible. A new source version fails closed until its lexical generation is ready. Rollback may target only a currently eligible generation and uses a revision CAS; it cannot reactivate revoked data.

### Implementation steps and checks

- [ ] Add failing unit tests for no-embedding extraction, duplicate delivery, stale lease, out-of-order completion, crash after acknowledgement, CAS conflict, retry exhaustion and unknown/outage failure.
- [ ] Add PostgreSQL integration tests for desired/active generation identity, source-switch invalidation, archive/revoke/delete, acknowledgement digest and reconciliation.
- [ ] Add the one additive Alembic revision after checking the current head and #192 migration changes. Down revision is the verified then-current head; downgrade is permitted only on an empty owned database and never drops legacy columns.
- [ ] Implement `search_indexing.py` worker orchestration by reusing existing claim/lease/fence contracts; implement `search_index_store.py` queries with explicit workspace and source-version predicates.
- [ ] Keep the feature opt-in and production-disabled. Run unit/contract tests offline; run PostgreSQL integration only in the approved isolated runtime envelope.

### S2.2 acceptance

An extracted PDF can become lexical-ready with no embedding configuration or provider call. Every activation is provenance-complete, CAS-safe and replayable. Archive/revoke/source changes deny immediately. A Qdrant outage is visible as failed/not-run and never counted as an empty retrieval result.

## S2.3 — native Qdrant BM25 projection

### Compatibility and scoring policy

- Candidate versions are Qdrant Server `1.19.2` and `qdrant-client` `1.19.1`; freeze exact image/package digests only after wire compatibility tests pass. No silent downgrade or auto-upgrade.
- Use native server BM25 with `k1=1.2`, `b=0.75`, multilingual Unicode tokenizer profile `bm25-unicode-multilingual-v1`, NFKC/lowercase query normalization, preserved accents, and no English stemming/stopwords. The original text and source offsets remain in PostgreSQL.
- Use one shard for the controlled baseline. IDF corpus is derived from the PostgreSQL authorized active corpus for the requested workspace, independently from the retrieval filter. An empty or unavailable corpus fails closed; there is no global/stale IDF fallback.
- Measure `avg_len` from the exact native tokenizer output during profile build and freeze the resulting population digest. If the pinned server cannot expose a verified token count, the profile build stops; whitespace counts are not substituted. A changed population or tokenizer requires a new profile and rebuild.
- Query Top-200 with no numeric score cutoff. Report raw score and score policy; derive primary Top-8 from that same ordered list. Do not compare BM25 numeric values with vector `0.65`.
- Deterministic ties use the canonical chunk identity only when the server exposes a stable boundary; otherwise the report records the boundary as unknown and does not claim exact beyond the returned limit.

### Isolation and adapter tests

- [ ] Verify wire requests target only the self-hosted loopback Qdrant endpoint and never client inference/FastEmbed/Cloudflare.
- [ ] Verify tenant keyword indexes, workspace/generation filters, authorized-corpus IDF filters and stale-generation rejection with foreign and revoked points.
- [ ] Verify mixed Vietnamese/English text, accents, identifiers, empty text, finite scores, deterministic ordering and server/client compatibility.
- [ ] Verify malformed payloads, mismatched profile digests and Qdrant errors fail closed with explicit operational status.
- [ ] Run the exact pinned server/client in the isolated envelope; retain image/package digests and request/response captures.

### S2.3 acceptance

The adapter returns only PostgreSQL-authorized identities with native raw BM25 scores and complete provenance. Tenant/stale isolation and tokenizer/profile parity pass compatibility tests. Qdrant remains opt-in and absent from the production default.

## S2.4 — same-corpus evaluation and application proof

### Evaluation contract

1. Restore the frozen 47 chunk records and approved runtime binding into the isolated PostgreSQL/Qdrant project without reparsing PDFs or changing gold. Verify corpus SHA, Gold SHA, runtime proposal SHA, derivation SHA, binding SHA and 25 missing anchors before querying.
2. Run exactly one bounded retrieval query per all 60 cases. Keep the full denominator and every status. Save native Top-200 rows, then derive Top-8 from those rows; do not refill Top-8 after PostgreSQL revalidation or use a second query.
3. Compare BM25 Top-8 candidates and selected evidence with Baseline B's observed post-`0.65` candidates separately. Report Top-200 diagnostics separately and label threshold/candidate-depth differences. Do not call any retrieval result a semantic answer-quality pass.
4. Preserve saved Baseline B captures as the comparison baseline. Use deterministic generation stubs only for application/E2E shape tests: fresh upload → extraction → lexical-ready → question → evidence/citation. Do not call a model, judge, Langfuse export or Cloudflare provider.
5. Human review consumes the same saved captures and distinguishes candidate coverage, selected generation evidence, public citations, facts, conditions and refusal language. Historical verdicts 001/005/012 ACCEPT and 014/032 REJECT remain supplements, not rewritten gold.

### Files and tests

- Extend existing PDF runner/report projection only; do not create a second evaluation package.
- Add/extend `backend/test/adapters/postgres/test_pdf_evaluation_e2e.py`, `backend/test/application/test_answer_question.py`, and focused adapter/selector tests.
- Add a deterministic isolated application profile to the opt-in Compose verification file. Required CI keeps only cheap no-service contracts; multi-service checks are named and manually invoked.
- Validate report schema, all 60 case records, all 47 chunk identities, all 25 missing anchors, provenance digests, candidate/selected fields and failure/not-run populations.

### S2.4 acceptance

The report is reproducible from saved inputs, has the frozen denominator, distinguishes raw candidates from selected evidence, and contains no invented evidence for missing mappings. The application path is proven with deterministic fixtures, while semantic quality remains unclaimed.

## Isolated runtime envelope (only after whole-plan approval)

- Compose project: `knora-153-s2`; services are loopback-only and use no existing project/network/volume.
- Host ports: PostgreSQL `127.0.0.1:15433`, Qdrant REST `127.0.0.1:16433`, application `127.0.0.1:18053`. Qdrant gRPC is not published.
- Volumes: `knora-153-s2-pgdata`, `knora-153-s2-qdrantdata`, `knora-153-s2-objects`; the filesystem object store uses the owned objects volume, so no MinIO or external bucket is needed.
- Resource caps: Qdrant 2 CPU/2 GiB, PostgreSQL 1 CPU/1 GiB, application/worker 1 CPU/768 MiB; total container cap 3.8 GiB plus filesystem overhead. Preflight requires at least 8 GiB free host RAM, 10 GiB free disk and all three ports unused. The current host has about 1 GiB free RAM, so startup must wait for a new preflight pass.
- Query/index limits: 60 retrieval queries, no automatic query retry; one indexing batch for 47 chunks (batch size ≤64); at most 1,200 Qdrant API calls for the accepted run and at most 3,000 for structural isolation tests. A failed run is retained and is never overwritten.
- Runtime window: one measured run up to four hours; at most two replacement runs after a code fix, each still all 60 cases. Every attempt ID and outcome remains in the report.
- Cleanup: stop only the owned Compose project; retain volumes and sanitized evidence through owner review. Remove owned temporary volumes only after final owner disposition. Never run `docker system prune`, kill unrelated processes, reuse Baseline B databases or delete other worktrees.

## CI, dependencies and migration safety

- S2.1 gate is the current required CI run and exact-subject artifact check. Do not rerun it merely for content changes.
- S2.2–S2.4 changes use separate PRs stacked on the reviewed S2.1 head or its reviewed successor; each PR runs the required CI before integration.
- Python changes run `python -m ruff format .`, `python -m ruff format --check .`, `python -m ruff check .` and focused pytest. Frontend/shared files, if touched by Compose or workflow changes, run the prescribed Prettier commands. Compose changes run `docker compose config --quiet`.
- `qdrant-client` is the only new runtime dependency proposed, pinned with compatibility evidence. No LangChain or provider dependency is added solely to wrap native BM25. No model weights are downloaded.
- The Alembic revision is additive and executed only against the owned isolated PostgreSQL after approval. Migration parent, downgrade behavior and concurrent #192 revisions are recorded before commit.

## Risks and rollback

| Risk | Detection | Response |
| --- | --- | --- |
| Native tokenizer count unavailable | Profile-build compatibility test | Stop profile build; record unknown; do not substitute whitespace counts |
| IDF corpus leaks stale/foreign data | Cross-tenant/stale isolation fixture | Fail closed, invalidate profile, inspect PostgreSQL filter and Qdrant indexes |
| Qdrant write acknowledged before PG activation | Crash/reconcile test | Keep PG pointer unchanged; replay idempotently or mark failed |
| Source revoked during query | PG revalidation | Drop candidate with explicit stale/revoked reason; never promote a later native rank |
| Host resource pressure | Preflight and container health | Do not start; stop owned services; preserve evidence; no unrelated cleanup |
| Migration conflict with #192 | Parent/head and schema diff check | Pause shared edit, rebase/coordinate exact diff; never guess a migration parent |
| CI regression | Required job/report failure | Fix in the owning PR, rerun focused tests and required CI, report failure honestly |

Rollback is feature-disable plus PostgreSQL pointer CAS to an eligible prior generation. It does not delete frozen data, change Baseline B, downgrade production schema or reactivate revoked sources. If a runtime experiment is abandoned, stop and remove only the owned Compose project after evidence retention.

## Acceptance checklist for the one overall approval

- [ ] Owner approves this S2.2–S2.4 scope, interface map, scoring policy and isolated resource envelope.
- [ ] #158/#192 acknowledge the shared-file/schema boundary and any exact conflicts are resolved before edits.
- [ ] S2.1 required CI passes on exact `e78a3b5` and `ci-subject.json` proves checkout SHA.
- [ ] S2.2 offline contracts and focused PostgreSQL tests pass; migration is additive and isolated.
- [ ] S2.3 compatibility, tokenizer, IDF, tenant/stale isolation and no-provider tests pass with pinned digests.
- [ ] S2.4 all-60 deterministic evaluation preserves frozen identities, denominators, missing anchors and provenance.
- [ ] Evidence review finds no unclassified operational failure, stale citation, invented mapping or semantic-quality overclaim.

After this approval, checkpoints are recorded as evidence rather than owner approval gates. The agent stops only for a real blocker, a requested architecture/scope change, a cost or quota issue, or a permission outside this envelope.
