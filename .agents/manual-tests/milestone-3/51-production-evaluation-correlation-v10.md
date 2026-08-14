# Manual Test Guide: M3.2 — Production evaluation correlation and metrics

## Metadata

- Feature: Milestone 3 — Hybrid retrieval and evaluation
- Slice: Issue #51 — Production evaluation correlation and metrics
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/51
- Guide revision: issue-51-v10
- Binding authority: `docs/design/m3-evaluation-environment-binding-v3.md`
- Bootstrap authority: `docs/design/m3-evaluation-bootstrap-lifecycle-v1.md`
- Supersedes: locked `issue-51-v9`, unchanged
- Approval status: pending human approval

## Prerequisites

The following lifecycle completes in this order, before any measured Q&A request:

1. `EvaluationEnvironmentBootstrap` runs as control-plane before production API startup. Through
   its idempotent application/control-plane Workspace seam it provisions/reuses the isolated
   persisted evaluation Workspace; it does not use ad-hoc acceptance SQL or a public
   acceptance-only endpoint.
2. Bootstrap loads/binds `m3-corpus-v1` through normal production application/ingestion seams,
   verifies Binding V3 and PASS corpus closure: the full retrieval-eligible active corpus equals
   the manifest source set exactly; each source has exactly one active manifest-matching Document
   Version and corresponding Chunk Set; no extra/missing/duplicate/multiple-active source/version.
3. Bootstrap issues one normal credential scoped to that persisted Workspace. Its raw key exists
   only in the ephemeral bootstrap result/runtime launcher; it is absent from Binding V3, logs,
   reports, committed evidence and the manual record.
4. The runtime launcher materializes the credential's hash-only normal startup auth configuration
   in `KNORA_API_CREDENTIALS_JSON` (or typed equivalent), then starts production `create_app()`.
   The process uses normal `ApiKeyAuthenticator`; no evaluation-only auth, hot reload, or credential
   mutation occurs during the measured run.
5. The evaluator receives the raw key only as runtime input, consumes it for production Q&A, and
   cannot provision, issue, activate, revoke or modify credentials. Teardown ends the process and
   ephemeral credential lifecycle.

## TC-01: Pre-start bootstrap, corpus closure and exact correlated trace

1. Capture redacted evidence for the ordered pre-start lifecycle above: Workspace provision/reuse,
   Binding V3, startup-auth injection without raw key, and normal production API startup.
2. Before Q&A, inspect closure evidence for exact active-corpus source-set equality and exactly one
   active manifest-matching `(source_key, document_version_id, chunk_set_id)` triple per source.
3. Call the normal production `POST /v1/questions`; use only returned `(workspace_id, trace_id)` to
   read its exact correlated trace.
4. Verify response↔trace identity, Workspace, resolved Retrieval Configuration, ordered fused
   provenance, and each candidate's exact triple against its per-source V3 binding entry before
   canonical projection.
5. Exercise lifecycle/closure failures before Q&A: missing/extra/duplicate active corpus source,
   multiple active source/version, incomplete binding, absent startup auth configuration, or an API
   started before bootstrap. Exercise trace failures after Q&A: missing trace, identity/Workspace/
   configuration mismatch, unknown source, missing/wrong version or Chunk Set UUID, and malformed
   rank/order.

Expected: pre-start/closure failure blocks measured Q&A; trace defects are observation failures
with no quality score. No inference/fallback, UUID-set membership, silent dedupe, evaluation-only
retrieval/auth, hot reload, or credential mutation is permitted.

## TC-02: M3 Retrieval Metrics V1

After TC-01, match only canonical `(chunk_set_provenance_id, source_key, ordinal)`: Recall@8,
uncut MRR, macro averaging, valid-miss zeros in denominator, and inapplicable/failure exclusions
remain exactly as V9's worked oracle.

## TC-03: Citation correctness

After TC-01, public answer/citation/markers remain source of truth. Correlated trace validates only
alias membership in evidence of the exact request; it never repairs/infer/substitutes public data.
Alias structural failures are `CITATION_STRUCTURAL_ERROR`; TC-01 failure has precedence.

## TC-04: Semantic citation scoring

After TC-01, semantic scorer receives only public answer and public citation excerpts/source
locators; it receives no hidden candidates, database IDs or trace internals.

## TC-05: Independent durations

After TC-01, retain server `retrieval_latency_ms` and executor `end_to_end_latency_ms` separately
with Binding V3 provenance. Invalid/missing duration is an observation failure; no aggregate
latency statistic is defined.

This guide is unapproved. Do not execute manual acceptance or alter the append-only Evaluation
history until explicit approval.
