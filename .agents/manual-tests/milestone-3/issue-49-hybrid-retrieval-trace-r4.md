# Manual Test Guide: M3.1 — Hybrid retrieval and trace provenance

## Metadata

- Feature: Milestone 3 — Retrieval quality and evidence evaluation
- Slice: Issue #49 — Hybrid retrieval and trace provenance
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/49; https://github.com/NhiBuaa/knora-agent/issues/48
- Guide revision: m3-issue-49-r4
- Supersedes: m3-issue-49-r3 for implementation planning; r3 remains immutable approval evidence.
- Approved by: NhiBuaa
- Approved at: 2026-08-12T09:20:00+07:00

## Authority review and resolved semantics

| Semantic | Authority | Resolution |
|---|---|---|
| Initial M3 pipeline | [Issue #48 threshold-admissibility clarification](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261367093); `CONTEXT.md` Retrieval Configuration definition; Architecture Standard `docs/standards/architecture.md:631-646`; [Issue #48 Evidence Sufficiency](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260914527) | **Vector/FTS branch eligibility → branch ranking and `candidate_k` → fusion → Evidence Selection redundancy, chunk-count, token-budget.** Initial M3 has no independent numeric post-fusion Evidence Selection threshold. |
| Vector `min_similarity` | [Issue #48 threshold-admissibility clarification](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261367093); [Issue #48 Evidence Sufficiency](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260914527); Architecture Standard `:631-636` | Vector-only branch eligibility gate applied before branch rank, branch `candidate_k`, and fusion. It is neither an RRF confidence threshold nor a post-fusion threshold. |
| FTS eligibility/rank | [Issue #48 Evidence Sufficiency](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260914527) | Native/configuration-defined FTS eligibility and rank apply before FTS ranking and fusion. Native rank is not converted to similarity. |
| Fusion | [Issue #48 threshold-admissibility clarification](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5261367093); [Issue #48 design decision](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260899855) | The immutable `rrf-v1` policy supplies `1/(60 + rank)` and fused ordering `fusion_score DESC, chunk_id ASC`. `fusion_score` is ranking-only; no `min_fusion_score` exists. This guide does not originate the contract. |
| Branch filtering and ties | [Issue #48 design decision](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260899855); Architecture Standard `:637-641` | Workspace, Active Embedding Set, and Embedding Configuration predicates execute in each branch before ordering and `LIMIT`; high-scoring excluded rows never consume `candidate_k`. Branch ordering is deterministic and versioned. |
| Trace shape/cardinality | [Issue #48 trace decision](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260941927); [candidate taxonomy](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260971731) | Persist ordered, deduplicated fused union of configured branch outputs, bounded by their sum less deduplication. No separate fused-output cap or raw rejected-hit persistence is assumed. Contributions are typed nullable; null means no eligible branch contribution. |
| Trace read/isolation | `CONTEXT.md:288-291`; Architecture Standard `:674`; [Issue #48 exact correlation](https://github.com/NhiBuaa/knora-agent/issues/48#issuecomment-5260987445) | Issue #49 owns exact `(workspace_id, trace_id)` trace read/isolation behavior. Evaluation categorization of observation failures is deferred to Issue #51. |

## Prerequisites

- Environment: local backend integration-test environment with PostgreSQL/pgvector and PostgreSQL full-text retrieval enabled.
- Data/state: two Workspaces; active/inactive and wrong-configuration sets; vector and FTS tie fixtures; vector-only, FTS-only, and dual-branch Chunks; and zero-eligible-contribution branch fixtures.
- Access: Workspace-scoped credentials plus exact Workspace/trace-ID trace-read access.

## Locked Test Cases

### TC-01: Deterministic strategy-agnostic seam and common trace schema

- Purpose: Prove vector-only and hybrid configurations use one application retrieval seam and one trace contract.
- Steps:
  1. Seed the fixed corpus and deterministic query fixture: vector-only selects `chunk-v1`; hybrid selects `chunk-hybrid-1`; the deterministic provider returns `Answer [[E1]]`.
  2. Execute the request under immutable vector-only and `rrf-v1` configurations, retaining both public responses and returned trace IDs.
  3. Read traces using their exact `(workspace_id, trace_id)` pairs.
- Expected results:
  - Both requests return `decision=ANSWER`, `Answer [[E1]]`, and exactly one `E1` citation.
  - Both use `AnsweringStore.retrieve_candidates`; no application-level vector/FTS selection path exists.
  - Both use the same trace schema with retrieval configuration and embedding/Chunk Set provenance, ordered pre-Evidence-Selection fused candidates, and typed nullable branch contributions. Vector-only has null FTS contribution; no value is fabricated.
- Evidence: deterministic public-interface tests, trace IDs, and persisted-schema assertions.

### TC-02: Filtering and deterministic ties precede every branch candidate budget

- Purpose: Prove branch-local filtering precedes ranking/`candidate_k` and tie ordering is stable.
- Steps:
  1. For vector and FTS fixtures separately, add higher-ranked foreign-Workspace, inactive-set, and wrong-configuration rows plus equal-ranked eligible rows.
  2. Set `candidate_k=1`; execute retrieval repeatedly for Workspace A.
- Expected results:
  - Each branch filters to Workspace A’s active selected configuration before ordering/`LIMIT`; excluded high-score rows do not consume candidate budget.
  - Each branch’s equal-score fixture resolves through its versioned deterministic order identically on repeated runs.
  - Excluded rows never enter fusion or Evidence Selection.
- Evidence: focused PostgreSQL integration assertions and repeated ordering output per branch.

### TC-03: `rrf-v1` fusion, deduplication, and bounded trace union

- Purpose: Prove the locked fusion policy without inventing an independent cap.
- Steps:
  1. Use one dual-branch Chunk and one distinct eligible Chunk per branch; execute the same hybrid request twice.
  2. Inspect fused candidates before Evidence Selection and trace provenance.
- Expected results:
  - Every branch returns no more than configured `candidate_k` eligible results after its filtering and deterministic ordering.
  - The shared Chunk occurs once with both contributions; one-branch Chunks carry a null other-branch contribution.
  - `rrf-v1` contributions and fused order match the immutable policy (`1/(60 + rank)`, `fusion_score DESC`, then `chunk_id ASC`) on both runs.
  - Trace candidate cardinality equals the deduplicated union of branch outputs and is bounded by their configured-output sum; no raw rejected branch hits are invented as fused candidates.
- Evidence: contract/integration output, two matching trace candidate lists, policy identity, and cardinality assertion.

### TC-04: Post-fusion Evidence Selection and stable answer behavior

- Purpose: Verify initial M3 applies only approved post-fusion policies and preserves refusal/citation semantics.
- Steps:
  1. Run a fixture with zero eligible vector contributions and zero eligible FTS contributions; confirm the fused candidate set is empty.
  2. Run separate non-empty fused fixtures that exercise overlap/redundancy, chunk-count limit, and token-budget decisions; each retains at least one selected candidate.
  3. Run a selected-evidence fixture with a deterministic structured provider refusal.
  4. Run the deterministic cited-answer fixture from TC-01.
- Expected results:
  - The observable pipeline is branch eligibility → branch ranking/`candidate_k` → fusion → redundancy, chunk-count, token-budget; no post-fusion numeric threshold and no `min_fusion_score` is applied.
  - Zero eligible contributions in both branches yield zero fused candidates, an empty Evidence Set, deterministic `REFUSAL` with `INSUFFICIENT_EVIDENCE`, and no generation invocation.
  - The separate fixtures record `REDUNDANT_OVERLAP`, a count-limit budget decision with `CHUNK_COUNT_LIMIT`, and a token-budget decision with `TOKEN_BUDGET`, without requiring every candidate to be removed.
  - Non-empty evidence supports a valid structured provider refusal; valid cited answers preserve alias mapping and citation marker/order.
- Evidence: public responses, generation-call sentinel, selection decision traces, and candidate pipeline assertions.

### TC-05: Exact trace read/isolation and implementation-detail exclusion

- Purpose: Verify the Issue #49 trace contract, not evaluation failure categorization.
- Steps:
  1. Execute a hybrid request and retain its Workspace and returned `trace_id`.
  2. Read with the exact pair; repeat with another Workspace, missing trace ID, and incomplete trace fixture.
  3. Inspect trace provenance and candidate records.
- Expected results:
  - Exact pair succeeds; non-exact reads follow the workspace-authorized trace-read contract.
  - Trace includes retrieval config, fusion policy, embedding/Chunk Set provenance, ordered fused candidates, final rank/score/decision, and typed nullable contributions; null is never filled with synthetic data.
  - Trace includes no SQL, `tsvector`, `tsquery`, plans, or database implementation details.
  - Evaluation observation-failure classification is not introduced in this ticket.
- Evidence: exact-read/isolation tests and persisted trace-content assertions.

This guide becomes immutable only after explicit human approval. Create a new revision for semantic changes; Evaluation runs remain append-only.
