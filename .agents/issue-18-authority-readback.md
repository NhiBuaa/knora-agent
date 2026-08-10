# GitHub Issue #18 authoritative read-back

Source: `GET /repos/NhiBuaa/knora-agent/issues/18` via `gh api`  
Read at: 2026-08-09 (current session)

## Parent

#14

## What to build

Complete the background PDF ingestion path by connecting the durable worker runtime to versioned extraction/chunking, the Embedding Provider and atomic derivation persistence. A job either activates a complete compatible Embedding Set, becomes superseded when its target is no longer current, schedules a classified retry, or fails safely without exposing partial knowledge.

## Acceptance criteria

- [ ] `ProcessIngestionJob` owns orchestration from claimed job through ObjectStore read, isolated extraction, chunking, embedding, persistence, activation and terminal/retry cleanup outcome.
- [ ] The worker uses only the immutable parser/normalizer/chunking/embedding configuration IDs snapshotted at job creation and never resolves mutable current configuration while running.
- [ ] Original source checksum and ObjectStore metadata are verified before processing; streaming reads avoid whole-object memory loading.
- [ ] Parser/chunker output creates or reuses the correct Chunk Set for the PDF Document Version and immutable extraction/chunking configuration target.
- [ ] Embedding Provider calls happen outside database transactions and validate vector count, dimensions, provider and model/configuration identity before persistence.
- [ ] Retry taxonomy for the Issue #18 PDF handler covers provider timeout/429/5xx, transient ObjectStore failures, retryable isolated-extractor infrastructure failure or eviction, and unexpected ordinary handler failures according to the Issue #17 cause mapping. Deterministic input, pinned-configuration, resource-limit, and vector-validation failures are non-retryable. Coordinator-owned attempt timeout and worker disappearance retain Issue #17 semantics; worker/process disappearance is recorded only as `LEASE_EXPIRED` when recovery proves lease expiry. PostgreSQL coordination-store deadlock, serialization, connectivity, network, and ambiguous-commit failures follow Issue #17 persistence/reconciliation or indeterminate-infrastructure semantics and never become handler `DATABASE_TRANSIENT`. `DATABASE_TRANSIENT` remains available only when a business-work handler legitimately observes a transient database dependency; the Issue #18 PDF handler introduces no such dependency.
- [ ] Final persistence atomically creates or reuses the complete Chunk Set/Embedding Set, validates Document/Workspace ownership and records the job outcome without partial retrieval-visible derivations.
- [ ] Activation CAS succeeds only with matching `worker_id + lease_version`, target still equal to `current_document_version_id`, and a completed compatible Embedding Set belonging to the same Document/Workspace.
- [ ] A newer source version causes stale activation to finish `superseded` without consuming retry budget and records replacement metadata when available.
- [ ] `current_document_version_id` and `active_embedding_set_id` may refer to different source versions; retrieval continues from the prior active set while a newer job processes or fails.
- [ ] Database constraints prevent cross-Document/Workspace pointers, incomplete active sets and deletion of current/active resources.
- [ ] Integration tests cover successful local embedding activation, provider retry, non-retryable failure, lease loss during processing, stale CAS supersession, duplicate delivery and no-partial-write rollback.

## Blocked by

- #15
- #16
- #17
