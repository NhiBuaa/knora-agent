# Manual Test Guide: Milestone 2 regression and release gate

## Metadata

- Status: Locked after explicit human approval. Do not change this revision.
- Feature: Milestone 2 — Production-shaped ingestion
- Slice: GitHub Issue #21 — Regression and release gate
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/21
- Parent ledger: https://github.com/NhiBuaa/knora-agent/issues/14
- Guide revision: `m2-issue-21-r3`
- Supersedes: locked `m2-issue-21-r2`; its append-only Evaluation history remains unchanged.
- Candidate baseline: exact clean release-candidate SHA, recorded when inventory generation begins.
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-11T11:04:40+07:00

## Purpose and boundaries

This is a verification-only release gate. It can identify a defect in approved behavior. It must not add production behavior or relax a failed oracle. Evidence contains only safe IDs, checksums, counts, timestamps, allowlisted errors and redacted logs. Do not record credentials, raw PDF contents, object keys, SQL text or provider payloads.

Earlier locked guides are evidence inputs. They do not replace this gate: #15 submission, #16 extraction, #18 derivation/activation, #19 public polling/reprocess and #20 lifecycle/metrics. The Evaluation record links those append-only histories and records fresh results against this candidate.

## Defect-gate rule

If any required oracle fails, record the affected case as `FAILED` or `BLOCKED`. Keep the release gate `FAILED` or `BLOCKED`. Do not relax, reinterpret or remove the oracle.

A repair can correct only the observed defect within approved behavior. The repair creates a new candidate SHA. Rerun every failed case, every affected regression case and repository verification against that SHA. If a repair requires a contract, domain-model or architecture change, stop the release gate and return to the applicable design authority. Do not treat that change as a repair.

## Prerequisites

- Clean release-candidate worktree; local PostgreSQL/pgvector and MinIO from Compose; API and worker.
- Two authorized Workspace credentials; safe PostgreSQL and metrics/alert test projections.
- Resettable Workspaces; valid, changed, malformed, encrypted, textless and boundary PDFs; fixed immutable configuration profiles; clean lifecycle work and metrics state per case.
- A pre-execution machine-generated test inventory from the exact clean candidate SHA. The inventory contains each pytest node ID, collection/static disposition metadata, candidate SHA, generation commands, toolchain/environment/configuration fingerprints and a manifest digest.
- An explicit human-approved non-pass allowlist before execution when any node is expected to skip or xfail. Each entry contains exact node ID, disposition, reason, authority and expiry.
- Run repository verification with `./.venv/Scripts/python -m pytest`, `./.venv/Scripts/ruff check .`, and `docker compose config --quiet`.

## Locked Test Cases

### TC-01: Release health and Milestone 1 compatibility

- Purpose: Issue #21 full verification and no Milestone 1 regression.
- Steps:
  1. Record the clean candidate SHA.
  2. Generate the pre-execution inventory from that exact clean candidate SHA before acceptance execution. Do not include observed acceptance outcomes as expected outcomes.
  3. Calculate the inventory digest. Lock `candidate SHA + inventory digest` as the baseline identity before execution.
  4. Obtain human approval for any non-pass allowlist entry before execution.
  5. Run the full pytest suite with the same test environment and profile used to generate the inventory.
  6. Compare the full execution node set and observed outcomes to the locked inventory and approved allowlist.
  7. Run Ruff, Compose configuration verification, and existing synchronous ingestion, question/citation/refusal, authentication and evaluation suites.
- Expected results:
  - Every collected inventory node defaults to required `PASS`.
  - An expected `skip` or `xfail` is valid only when its exact node ID appears in the human-approved pre-execution allowlist with disposition, reason, authority and unexpired expiry.
  - The full execution node set exactly equals the locked inventory node set. A missing, deselected or new node fails or blocks this case.
  - A collection error, unknown skip/xfail, outcome outside policy, or environment/toolchain/configuration fingerprint mismatch fails or blocks this case.
  - A candidate or test-tree change invalidates the inventory. Regenerate the inventory and obtain human approval before execution.
  - Markdown/plain-text ingestion and existing cited-answer/refusal contracts remain unchanged.
- Evidence: candidate SHA, inventory artifact and digest, baseline identity, generation commands, toolchain/environment/configuration fingerprints, approved allowlist, execution node/outcome diff, lint/Compose outputs and safe HTTP samples.

### TC-02: Authenticated PDF upload-to-cited-answer integration

- Purpose: prove upload -> durable Job -> worker -> polling -> active PDF cited answer.
- Steps:
  1. Upload a valid text PDF in Workspace A with a fresh scoped Idempotency-Key.
  2. Poll the Workspace-scoped Job through terminal completion while a worker processes it.
  3. Ask a PDF-specific question after success. Capture the server-resolved Evidence Set and every returned Citation Projection.
  4. Use an active Chunk from the same Workspace that is absent from that Evidence Set. Attempt to produce a citation for that Chunk through the citation-validation seam.
  5. Repeat a matching submission and cross-Workspace lookup.
- Expected results:
  - Upload/polling obey public status, safe metadata, no-store and retry-hint contracts. Success is visible only after complete activation.
  - Every returned citation resolves to one member of the server-resolved Evidence Set for that answer. It resolves to the same pinned Document Version and Chunk as its Evidence Set member.
  - An active Chunk outside the Evidence Set fails citation validation. It cannot appear in the answer or Citation Projection.
  - The valid answer preserves version-pinned page/offset provenance and backward-compatible line fields. Duplicate and tenant-isolation behavior is correct.
- Evidence: redacted HTTP sequence, Evidence Set member IDs and digest, alias-to-member resolution, citation projections, rejected outside-set active-Chunk result, worker-stage trace, current/active/served IDs and 404 result.

### TC-03: PostgreSQL lifecycle, concurrency and atomicity matrix

- Purpose: prove #17/#18/#19 durable coordination obligations.
- Steps:
  1. Run deterministic PostgreSQL/integration cases for request/document/derivation deduplication, atomic claim, heartbeat, stale-worker fencing, expiry recovery, retries/exhaustion and CAS supersession.
  2. Run duplicate-delivery and definite pre-commit finalization rollback cases.
  3. Inspect Job, immutable Attempt, derivation and pointer projections after each case.
- Expected results:
  - One current leased attempt exists at most. Stale calls do not mutate outcomes. Recovery commits before a later claim. Exhausted work is terminal.
  - One visible complete success exists. Rollback leaves no partial chain, pointer or terminal success. An older target is `superseded` without retry.
- Evidence: focused selectors/pass counts, safe lease/operation trace, Attempts and before/after rows and pointers.

### TC-04: PDF parser rejection and resource-budget matrix

- Purpose: prove #16 deterministic extraction and every safe terminal boundary.
- Steps:
  1. Run malformed, encrypted/password-protected, unsupported and textless/insufficient-text fixtures.
  2. Run raw-size, page-count, per-page/aggregate stream, child-timeout and child-memory cases.
  3. Inspect public Job/Attempt projections and prior active knowledge after each failure.
- Expected results:
  - Each fixture returns its stable allowlisted code/reason. Budget violations are `PDF_RESOURCE_LIMIT_EXCEEDED` with the approved safe reason evidence.
  - Child limits hold. No partial derivation activates. Previous active knowledge stays served.
- Evidence: fixture category, code/reason, child-limit trace, call counts and before/after pointers.

### TC-05: Reprocess, serving state and citation contracts

- Purpose: prove #19 public lifecycle/serving separation, immutable reprocessing and Evidence Set citation safety.
- Steps:
  1. Observe unavailable/current/previous serving in a processing/failure/newer-version sequence.
  2. Reprocess the current Document Version with `same_as_job` plus explicit source selector, then with `current`. Cover idempotency replay/conflict, reuse and generation history.
  3. For each cited answer, capture the server-resolved Evidence Set and resolve every returned citation to a member.
  4. Select an active Chunk that is absent from each captured Evidence Set. Attempt citation validation for that Chunk.
  5. Exercise non-current and superseded paths and verify tenant-isolated polling.
- Expected results:
  - Serving state does not replace Job state. Timestamps, safe errors, pointers, cache policy and citations follow the locked #19 contract.
  - Reprocess snapshots configuration, preserves prior Jobs and rejects non-current/cross-Workspace access.
  - Every returned citation resolves to a member of its server-resolved Evidence Set. An active outside-set Chunk fails citation validation and produces no Citation Projection.
- Evidence: safe response sequence, audit/idempotency trace, configuration IDs, generation links, Evidence Set member IDs and digest, alias-to-member mapping, rejected outside-set result and citation fields.

### TC-06: Object lifecycle, reconciliation, metrics and alerts

- Purpose: prove #20 retention/cleanup and operational safety.
- Steps:
  1. Classify each test object as a retained Original Source Object, a staging/temporary/partial artifact, or a failed-upload diagnostic-retention artifact.
  2. For each class, record its owner, retention predicate, cleanup eligibility predicate and earliest eligible time before dispatching lifecycle work.
  3. Run success, supersession, failed-upload, duplicate-delivery, worker-crash and object/database-gap cases.
  4. Run cleanup/reconciliation for unreferenced and inconsistent records with age and Workspace guards.
  5. Generate queue/lease/retry/cleanup/orphan scenarios and evaluate Alert Configuration V1.
- Expected results:
  - A retained Original Source Object belongs to its Document Version. It is ineligible for terminal cleanup. Only approved hard-delete retention can make it eligible.
  - A staging, temporary or partial artifact is eligible only after its owning operation reaches the approved terminal/compensation condition. Its cleanup cannot delete a retained Original Source Object or change an Ingestion Job outcome.
  - A failed-upload diagnostic-retention artifact is not an Original Source Object. It is ineligible until its separate bounded diagnostic-retention deadline. Its cleanup uses its own lifecycle-work record and cannot transfer ownership to a Document Version.
  - Deletion is idempotent and fenced. Reconciliation is Workspace-scoped. Required low-cardinality metrics/alerts reflect scenarios without identity labels or annotations.
- Evidence: artifact-class classification, owner, retention and eligibility predicates, eligible-at values, lifecycle/attempt projections, delete/head trace, retention references, metric/alert snapshots and label audit.

### TC-07: Migration, documentation and criterion-level release traceability

- Purpose: prove upgrade safety, operator usability and criterion-level evidence for every parent and child ticket.
- Steps:
  1. Upgrade clean PostgreSQL through all migrations. Run focused invalid-pointer, uniqueness and protected-hard-delete constraint cases.
  2. Follow README/operations instructions for MinIO, API/worker startup, polling, reprocess, retry/lease, retention, metrics and failure diagnosis.
  3. Create a machine-readable traceability row for every acceptance criterion in #14 and #15–#21.
  4. For every row, record the criterion ID/text digest, candidate SHA, evidence/test ID, `fresh|inherited` provenance and result.
  5. If a row is `inherited`, point to the exact immutable accepted Evaluation record and its guide revision. Do not point only to a guide, ticket, branch or summary.
  6. Mark the release `PASSED` only after every row is `PASSED` and a human approves the appended Evaluation record.
- Expected results:
  - Migrations and database constraints reject invalid commits atomically.
  - Documentation works from a clean environment without stale commands or secret/object-key leakage.
  - Every criterion has exactly one traceability row. A row is sufficient only when it contains the candidate SHA, evidence/test ID, provenance and result.
  - An inherited result names the exact immutable accepted Evaluation artifact. A fresh result names evidence captured from the candidate SHA. Missing, ambiguous, failed or blocked rows keep the release gate `FAILED` or `BLOCKED`.
- Evidence: migration output, constraint class/projections, documentation transcript, machine-readable criterion matrix, candidate SHA, exact Evaluation artifact paths and explicit human decision.

## Traceability matrix

| Authority | Cases |
| --- | --- |
| Issue #14 lifecycle, active-only retrieval, retries, isolation and test seams | TC-01–TC-07 |
| Issue #15 submission/idempotency | TC-02, TC-03, TC-05, TC-07 |
| Issue #16 extraction/normalization/budgets | TC-04, TC-07 |
| Issue #17 coordination/leases/retry | TC-03, TC-07 |
| Issue #18 derivation/activation/CAS | TC-02–TC-04, TC-07 |
| Issue #19 polling/reprocess/citations/serving | TC-02, TC-05, TC-07 |
| Issue #20 retention/reconciliation/metrics | TC-06, TC-07 |
| Issue #21 acceptance criteria | TC-01–TC-07 |

This guide is immutable. A semantic change requires a new revision. Execution observations belong in a separate append-only JSONL Evaluation history.
