# S2.2 embedding-free PDF design audit

Reviewed HEAD `b789e909cecf10fb51e10fb3e10c868554bbcbf2`, approved plan at `1346b7c`, repository guidance, CONTEXT, architecture/module seams, ADR0013/0018, and the M5 projection runbook. Read-only audit; no implementation, tests, providers, services, dependency installation, or migration execution.

## Recommendation

Use a **durable two-job handoff in the existing ingestion coordinator**:

1. An explicitly requested extraction-only PDF job uses the normal submission/admission/source-identity path and existing `ProcessIngestionJob` claim/lease/retry machinery.
2. Its fenced success transaction validates source/configuration/provenance, persists or verifies the real completed Chunk Set, records the desired lexical generation, and inserts exactly one queued lexical-index job. All four effects commit together.
3. The lexical-index job uses the same `ingestion_jobs` / `ingestion_job_attempts`, supervisor, timeout, recovery and RetryPolicyV1. It loads the immutable generation and authoritative PostgreSQL text, performs idempotent projection I/O outside transactions, then atomically verifies the live attempt and receipt, CAS-activates the still-desired generation, and closes its attempt/job.
4. Extraction success means extraction completed and indexing was durably requested. **Only successful indexing activation means lexical-ready.** An extraction job must not claim readiness merely because its Chunk Set exists.

This is smaller and safer than keeping one attempt live across a new intermediate checkpoint API. It introduces two typed work variants, not another queue/coordinator/retry framework. The boundary ACK should explicitly cover the two-job semantics and additional job-kind/generation binding; the earlier phrase “lexical-tagged nullable embedding” alone is insufficient.

## Concrete seam and caller map

| Area | Minimum complete change |
| --- | --- |
| `ingestion/jobs.py` | Explicit extraction-only submission configuration/value object alongside existing dense configuration; union in prepared submission/reprocess context. Preserve dense constructors and exact historical dense fingerprint bytes. Give extraction a versioned, distinct fingerprint including its kind; never use a fake embedding configuration or empty embedding ID as identity. |
| `ingestion/job_processing.py` | Data-only extraction success containing validated `PdfExtractionResult`; separate immutable index work/success containing generation identity and verified receipt. Existing dense success/provider/vector checks stay required. Dispatch by persisted kind, never infer lexical intent from a missing optional embedding value. |
| `adapters/postgres/ingestion_job_store.py` | Keep the compatible facade; add only transaction-shaped delegation required by the variants. Application callers do not import private collaborators or receive sessions. |
| `adapters/postgres/ingestion_jobs/submission.py` | Skip embedding-config insertion only for extraction configuration. Include kind in dedup/reprocess equality. Reconstruct extraction config without querying `session.get(EmbeddingConfigurationTable, None)`. Audit/idempotency/admission remain atomic. |
| `adapters/postgres/ingestion_jobs/coordination.py` | Update all three work constructions (claim, claim replay, historical claim replay) and `pdf_profile_for_work`. Reuse source/chunk validation and Chunk Set write/reuse logic in the existing finalizer. Separate vector checks/writes into the dense branch. Fingerprints must bind success variant and generation/receipt; replay cannot reinterpret one variant as another. |
| `ingestion/search_indexing.py`, `adapters/postgres/search_index_store.py` | Typed index handler and store port; share transaction-local request/activation implementation with ingestion coordination so handoff and final activation are atomic. Do not call the current public methods, each of which opens an independent transaction, from inside finalization. |
| `adapters/postgres/tables.py`, new revision after `20261016_0153` | Explicit three-way kind (`dense` default, `pdf_extraction`, `lexical_index`), nullable embedding FK only for the latter two, generation FK required only for index work, checked valid combinations. Preserve source/configuration ownership constraints and attempt invariants. Verify concurrent migration head/ACK first. |
| HTTP/composition | `adapters/http/routes.py:ingest_document` always constructs a dense configuration; `main.py:create_app` always builds embedding providers/config. For the approved isolated E2E compose an explicit extraction path without requiring an embedding config/provider. Keep production defaults and synchronous text path unchanged; a public selector/default change needs its coordinated contract. |
| Tests/fixtures | Extend focused `test_jobs.py`, `test_pdf_job_processing.py`, `test_pdf_derivation_finalization.py`, `test_ingestion_job_coordination.py`, reprocess/status tests and `test_search_indexing.py`. Existing Issue18 fixtures remain dense; add small explicit lexical fixtures instead of weakening all dense fixtures. |

The index job may retain the same immutable source/parser/chunk configuration columns to satisfy existing job ownership checks. Its payload should add only the generation ID required to resolve real persisted chunks/profile. An internal fixed operation such as `index_lexical` plus a generation-bound fingerprint can reuse current `(workspace, operation, content_fingerprint)` uniqueness. Keep client submission/reprocess operations and their existing idempotency meaning intact.

## Load-bearing correctness constraints

- **Handoff exactly once:** durable generation request and queued index job must be created before extraction attempt closure in the same transaction, with unique identity/replay validation. Replaying extraction finalization must return the existing result and create no second generation/job. A lost final lease rolls everything back.
- **Fence activation:** current `activate_ready` checks desired revision/source/workspace snapshots but has no ingestion-attempt capability. Add final attempt ownership proof in the same transaction as activation, using fresh database time after locks and the existing final conditional job update. An old worker may stage immutable external points; it may not activate after lease expiry.
- **Crash after acknowledgement:** retry the same persisted generation/point IDs, verify readback/receipt, then activate. Never allocate a new generation on every retry, blindly accept an upsert success, or treat a projection outage as empty evidence.
- **Kind/nullability:** database check must reject dense+NULL embedding, extraction/index+non-NULL embedding, missing/foreign generation for index work, and unknown kind. A simple nullable column broadens dense behavior unsafely. Validate generation ownership through document/version/chunk-set relationships, not a plain generation FK alone.
- **Explicit source supersession:** extraction success for an obsolete source must use existing superseded handling and enqueue no index work. Index activation must recheck current source, desired revision, document/workspace archive state and generation provenance. Preserve all terminal closure, safe failure, cleanup and admission handling.
- **Retry taxonomy:** keep RetryPolicyV1 and attempt limits. Projection unavailable/timeouts must map to an explicitly reviewed transient cause (or a narrow added versioned projection cause); malformed receipt/profile/provenance is terminal. Do not silently route every projection exception to transient retries.
- **Previous generation:** failed rebuild may preserve only an explicitly eligible same-source/same-profile active generation. Source switch/archive/revoke must immediately deny old eligibility; re-unarchive must not resurrect it merely by clearing an archive flag. Source/workspace revision comparisons must be used on every read/revalidation, not only activation.
- **Revision coupling:** `source_revision` currently stores `Document.revision`, which also changes on dense activation and archive transitions; `workspace_revision` changes on workspace updates. Keep this conservative invalidation visible. Do not increment Document revision during lexical activation after snapshotting it and thereby make the new generation stale immediately. A narrower dedicated eligibility revision would be a separately justified schema change.
- **Lock order:** current coordinator locks job/attempt then document; lexical store locks workspace then document. Shared transaction implementation must pick an order consistent with admission/source/archive paths and account for retries on deadlock; do not nest transaction-opening stores.
- **Profile authority:** extraction config and index request must bind the explicit immutable lexical policy/profile. Native tokenizer counts/avg_len/statistics digest cannot be guessed from PDF/whitespace token counts. A changed active corpus requires the approved new profile/population identity, not silent reuse.

## Reprocess and projection consequences

1. `submission.py:_configuration_from_job` currently assumes embedding is always present. `_current_configuration_for_document` resolves an active Embedding Set or latest succeeded job. With two job kinds, latest succeeded may be an index job; explicitly select the requested derivation/configuration source. `jobs.py` deployed reprocess currently requires embedding and `replace(...embedding_configuration=...)`; preserve its dense meaning or explicitly reject unsupported lexical deployed conversion. Never silently turn extraction config into dense config.
2. Internal index jobs will become the “latest job” in `document_reader.py:_projection`, affect last-processed timestamps and appear through `get_job_status`. Decide explicitly whether the UI shows the extraction job plus supplemental indexing state, or the actual index job lifecycle. Do not silently replace upload-job identity with an unrelated internal job.
3. `submission.py:get_job_status` and `document_reader.py:_projection/_answer_availability` resolve serving only through active Embedding Sets. Lexical-ready documents will otherwise display unavailable/not-indexed. Keep `embedding_readiness=not_indexed` truthful, and add coordinated strategy-aware lexical availability/serving observations; never fabricate embedding IDs or mark extraction success as answer availability. M5/#192 owns the public contract; new response fields imply schemas/OpenAPI regeneration and frontend ownership.
4. `answering_store.py` BM25 readiness/retrieve currently fail closed unconditionally. S2.2 needs actual PostgreSQL-authoritative generation selection and pre-query/post-query/pre-citation checks. Generation metadata from Qdrant is an identity hint; load text/locators only from PostgreSQL. Lexical retrieval may have no embedding provenance; dense/hybrid still require it.
5. `evaluation_reader.py:read_pdf_chunks/read_active_corpus` currently join active Embedding Sets. Add an explicit lexical projection through its existing public facade for S2 captures; do not change dense historical readers or frozen dataset/47-chunk artifacts. Preserve #158 authority, missing historical values and all denominators.
6. `ingestion_jobs/lifecycle.py:enqueue_terminal_cleanup_in_transaction` queues one terminal cleanup item per job; a second index job will enqueue another for the same retained source. Existing revalidation must continue suppressing retained Original Source Object deletion. Neither job success/failure permits deleting original source bytes.
7. `operator_reader.py` is trace-focused rather than an ingestion scheduler, but operator/frontend consumers must distinguish extraction success, pending/failed indexing and available lexical retrieval. Safe low-cardinality failure output must not expose PDF text, credentials or storage keys.

## Small focused acceptance matrix

- Fresh PDF extraction with no embedding configuration/provider produces a complete real Chunk Set, one desired generation, one queued index job; zero Embedding Sets/vector rows/provider calls.
- Dense submission/fingerprint/config reconstruction/provider validation remain unchanged.
- Extraction commit rollback/replay, stale lease and source supersession produce no orphan or duplicate queued indexing work.
- Index outage retries existing generation; exhaustion leaves explicit failure and no invented readiness.
- Receipt replay, crash after ack, out-of-order generations, revoked/archived/source-switched input and expired lease cannot activate.
- Same-source eligible prior generation survives a failed rebuild; changed source/profile does not.
- Public/document/reprocess/evaluation projections preserve identity, unavailable/unknown semantics and cross-workspace denial.

## Limits

This is a source-based design audit, not runtime compatibility or migration evidence. No code changes, schema execution, service startup, provider/model calls, tests or external coordination messages were performed. The only written artifact is this report. The two-job handoff and public projection contract require the concrete shared-owner ACK before implementation.

