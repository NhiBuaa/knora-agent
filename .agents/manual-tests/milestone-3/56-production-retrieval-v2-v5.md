# Manual Acceptance Guide: M3 — Production retrieval calibration and lexical policy v2

## Metadata and authority evidence

- Feature/slice: Milestone 3 / Issue #56 — Production retrieval calibration and lexical policy v2
- Guide revision: `issue-56-v5`; supersedes unapproved `issue-56-v4` (preserved unmodified)
- Approval/execution: approved and locked 2026-08-13; unexecuted
- Approved by: repository owner through explicit Issue #56 guide approval
- Lock authority commit: `a64f40745db87d9f1584188f2f1ad73829f80d1f`
- Lock gate result: PASS — committed R9 blob and blob-byte SHA-256 exactly match the reviewed
  identities below; fresh Issue #56/#51 REST authority, protection, blocker, preservation, and
  native dependency assertions all passed.
- Final authority: `docs/design/m3-retrieval-rrf-v2-authority-proposal-r9.md`
- Reviewed R9 identity: Git blob SHA-1 `7833e7c4100b20ca5e5de01d3702ae29e0b55e9a`; blob-byte
  SHA-256 `F409277B54AA32E1A811D7B1D43ED3B0F993D7B715A14EEE3145FC9BBAAB5CF6`.
- GitHub authority snapshot: REST `GET /repos/NhiBuaa/knora-agent/issues/56`, issue ID
  `5137082930`, snapshot SHA-256 `5D3F403B097AEC39E6D2AE716D22C1F55B0D6680B07420CEE572AAF525F827A6`.
- Lock gate: R9 must be committed with `git ls-tree` blob exactly
  `7833e7c4100b20ca5e5de01d3702ae29e0b55e9a`, and the checked-out blob bytes must SHA-256 exactly
  `F409277B54AA32E1A811D7B1D43ED3B0F993D7B715A14EEE3145FC9BBAAB5CF6`. Any difference requires a
  new guide revision and human re-review; it cannot be accepted by pinning a different resulting
  blob. Re-fetch/digest Issue #56 and #51 and revalidate their assertions at lock.

## Scope and boundary

This guide accepts only a #56-only candidate from final R9. It must not mutate Issue #51 evaluator
semantics, locked `issue-51-v12`, its append-only history, or v1 artifacts/configurations.
It authorizes neither implementation nor Gemini/calibration/provider activity until approved and
locked. `m3-dataset-v1` remains development-exposed, never unbiased v2 improvement evidence.

## Prerequisites

- Pinned #56 candidate SHA; allowed-path diff and before/after locked-#51 digests.
- Isolated Workspace with existing M3 Chunk Sets; before snapshot of derivation/active/v1 identities.
- Pre-execution frozen, checksummed `m3-retrieval-calibration-v1` with all required manifests,
  cases, judgments and calculation policy.
- Controlled redacted fixtures for provider input, scores/ranks, FTS, fusion/provenance and selection.
- #51/#56 dependency read-back and a complete retained-evidence location enumeration contract.

## Locked Test Cases

### TC-01: Exact authority, closed retained-evidence protocol, and #56 isolation

- Purpose: Prove reviewed R9/GitHub authority, exact-value credential non-retention over closed
  bytes, and independent #56 boundary.
- Steps:
  1. Re-fetch GitHub Issue #56 and #51, canonicalize and SHA-256 digest responses, and verify #56
     names R9/Gemini canonical, #56 protects locked #51 artifacts, and #51 names #56 blocker while
     preserving TC-01/TC-05. Verify the committed R9 `git ls-tree` blob is exactly
     `7833e7c4100b20ca5e5de01d3702ae29e0b55e9a` and its blob bytes SHA-256 exactly
     `F409277B54AA32E1A811D7B1D43ED3B0F993D7B715A14EEE3145FC9BBAAB5CF6`. Abort on any difference;
     it requires a new guide revision and re-review.
  2. Complete all ordinary retained evidence. Enumerate every #56 retained evidence location,
     read its bytes, and form an immutable manifest containing only canonical reference, byte count
     and SHA-256. Seal the manifest and listed bytes in immutable/read-only storage; immediately
     revalidate all listed byte counts/digests. This is the sealed ordinary-evidence inventory.
  3. In a non-logging verifier, receive exact runtime credential only via non-logging process input
     and scan sealed bytes—not mutable paths—for exact byte equality. Credential/search literal must
     not occur in arguments, logs, names, reports, manifests, traces, or persisted verifier state.
  4. Produce the sole non-recursively-scanned closure artifact: a schema-constrained scanner result.
     Its schema permits only constants/enums, integer counts, fixed-format SHA-256 digests, timestamps,
     seal ID, sealed-manifest digest, and references already present in the sealed manifest. It has no
     free-form text or arbitrary payload fields, and its serializer accepts no credential or search
     literal parameter. Validate it structurally and bind it to the sealed manifest.
  5. Define final inventory as exactly `sealed ordinary evidence + structurally-qualified closure
     result`. The closure result is excluded from recursive exact-value scan solely by its closed
     schema/serializer proof. No later artifact is allowed; a required later artifact restarts
     ordinary-evidence enumeration, sealing, scanning and closure. Fail closed on a post-seal digest
     change, missing item, invalid schema, failed scan, match, or any unqualified post-scan artifact.
  6. Verify #56 allowed-path diff and before/after hashes for locked #51 guide/history.
- Expected results:
  - The exact reviewed R9, rather than a merely newly-pinned variant, and current GitHub issue state
    prove authority/dependency/protection at lock time.
  - Exact credential-value `match_count=0` over all sealed ordinary evidence. This claim covers only
    exact value occurrence in those bytes; it makes no claim about encodings, hashes, fragments, or
    other derived representations.
  - Final inventory has no TOCTOU mutation or unqualified post-scan artifact; #51 locked artifacts
    remain unchanged.
- Evidence: redacted configurations; API snapshot/digests; R9 commit/blob proof; sealed manifest;
  schema/serializer proof and closure result digests/counts/status; candidate diff; #51 hashes.
  Never retain credential or search literal.

### TC-02: Exact asymmetric input and one-Content invariant

- Steps: NFKC-distinct fixture; prove query is `task: question answering | query: {NFKC(question)}`
  and Chunk is `title: none | text: {NFKC(chunk_text)}`; assert one text Content per logical call;
  attempt source_key/database/display-title/gold-metadata injection.
- Expected: one shared Gemini configuration with role-specific policy; forbidden metadata and
  multi-part/direct-input aggregation rejected; explicit multiple Content objects do not satisfy it.
- Evidence: normalized values, sanitized payload-shape assertions, negative results.

### TC-03: Dimension and provider-output contract

- Steps: prove `EmbedContentConfig.outputDimensionality=1536` and no deprecated field; feed 1536,
  1535, 1537 response fixtures; inspect transform/persistence behavior.
- Expected: only 1536 proceeds; mismatch fails before write; provider output stored as returned with
  no client normalization.
- Evidence: config, response-length, transaction and transform assertions.

### TC-04: Immutable calibration artifact and pre-execution freeze

- Steps: inspect checksummed `m3-retrieval-calibration-v1` before first execution; verify manifest,
  applicable cases, gold/hard-/near-negative judgments and calculation policy; attempt post-freeze
  edit/add/remove; bind the first calibration run identity and its result artifact to the exact
  frozen calibration SHA-256 before any result is interpreted or threshold is selected.
- Expected: complete checksum-bound pre-execution artifact; post-result mutation requires new
  version; the first run/result references exactly the frozen artifact digest and cannot substitute
  a later or mutable calibration input.
- Evidence: manifest/checksum, freeze commit/time, validation, mutation rejection/new-version proof,
  and first-run/result provenance containing the frozen calibration digest.

### TC-05: Independently auditable calibration independence and informativity

- Steps: bind an independence-oracle record to the frozen calibration digest before first execution;
  capture source and authoring lineage for every calibration source/case/judgment; run deterministic
  exact-copy and normalized-overlap checks against `m3-dataset-v1` over source keys, facts, content
  and questions with versioned normalization/threshold rules; obtain an independent semantic review
  by a reviewer who did not author the calibration, explicitly assessing rephrase and derivation;
  prove >8 candidate universe, ≥8 non-gold eligible distractors per applicable case, and all required
  gold/negative/control coverage.
- Expected: lineage is complete and auditable; deterministic checks report no disallowed copy or
  normalized overlap; independent semantic review finds no rephrase/derivation; every oracle input,
  result and reviewer decision is digest-bound to the same frozen calibration artifact before first
  execution; all informativity preconditions pass. A missing/indeterminate oracle component blocks
  calibration rather than becoming a self-declared PASS.
- Evidence: lineage manifest and source references; versioned copy/normalized-overlap oracle inputs,
  rules, outputs and digests; independent reviewer identity/attestation and structured findings;
  frozen-artifact binding; counts, coverage and source/manifest digests.

### TC-06: Usefulness gates and deterministic threshold selection

- Steps: after approval run threshold-free vector retrieval with `vector_candidate_k=8`; calculate
  mean Recall@8, top-2-gold rate, hard-negative maxima and P10 first-gold similarity; seal the
  observed score/candidate table with its frozen calibration/provider/config provenance; enumerate
  all observed top-8 boundaries plus empty-above-max using frozen precision/percentile/population/
  identity/inclusion rules; on the same sealed table, repeat only the threshold-selection
  calculation and choose the largest threshold preserving every applicable Recall@8 and excluding
  every hard-negative candidate.
- Expected: Recall@8 ≥ .90, top-2 ≥ 90%, each hard-negative max strictly < P10; repeated selection
  over the identical sealed observed table yields the same boundary set and literal threshold.
  Determinism does not require rerunning Gemini/provider embedding or retrieval to reproduce vectors,
  scores or candidate tables bit-for-bit.
- Evidence: frozen calibration digest, provider/config provenance, sealed observed-table digest,
  formulas/intermediates, boundary list, literal threshold and repeated-selection comparison.

### TC-07: Calibration FAIL prohibits numeric threshold

- Steps: violate each usefulness gate in controlled result; attempt vector-v2/hybrid-v2 numeric pin.
- Expected: no pin; v2 unreleasable; fallback/guessed/inherited/post-fusion threshold rejected.
- Evidence: per-gate result, rejection and configuration-store state.

### TC-08: Corpus-wide re-embedding, activation, and v1 preservation

- Steps: resolve and digest the entire authority-bound production M3 corpus population; for every
  member snapshot Document Version, existing Chunk Set identity/content/ordinals, v1 Embedding Set/
  configuration/vector provenance and active pointer; re-embed each existing Chunk Set under
  `embedding-gemini-m1-v1`, validate completeness and guarded activation, then compare the full
  population after state. If activation is incremental, declare and verify a cutover condition that
  requires every authority-bound corpus member to have its complete compatible v2 Embedding Set and
  intended active state before v2 production retrieval is enabled.
- Expected: population coverage is exact with no missing/extra member; every existing Chunk Set is
  preserved bit-for-bit and no rechunk occurs; every v2 vector is newly produced under the Gemini
  configuration with no reuse/mixing of v1 vectors; v1 vectors, Embedding Sets, configurations and
  artifacts remain immutable. Incremental activation is allowed, but v2 production enablement stays
  disabled until the declared corpus-wide cutover condition passes; no new atomic activation
  guarantee is invented.
- Evidence: authority-bound population manifest/digest, per-member before/after derivation graph,
  Chunk Set hashes/ordinals, embedding provenance/completeness, activation sequence, cutover
  declaration/status, production-enable observation and v1 immutability diff.

### TC-09: `fts-m3-or-v2`, structural OR, empty and adversarial queries

- Steps: exercise NFKC/case-fold, split/collapse, exact stopword removal, numeric retention,
  dedup/codepoint sort; prove specified refund/period and 30/days OR examples; use no-lexeme query;
  add adversarial inputs covering quote/operator-like text, SQL metacharacters, repeated/mixed
  punctuation, combining/compatibility Unicode, control/whitespace variants, very long tokens,
  duplicates and entirely unrepresentable tokens; inspect simple indexing/query/eligibility/rank/ties.
- Expected: safe typed compiler/no raw interpolation; adversarial inputs can only become safely bound
  normalized lexemes or recorded omissions and cannot alter query structure/SQL; empty or fully
  omitted lexemes yield zero candidates/contribution, no SQL/raw fallback, and policy/empty-lexeme/
  normalization trace.
- Evidence: adversarial fixture matrix, normalized tokens/omissions, parameterization/SQL-spy/trace/
  order results.

### TC-10: Budgets, RRF v2, deduplication, order

- Steps: >8 branch fixtures, duplicates, branch-only candidates and ties; prove each branch limit 8;
  calculate eligible `1/(60+branch_rank)` contributions; inspect final order.
- Expected: exact `vector_candidate_k=8`, `fts_candidate_k=8`, one canonical duplicate, correct sum,
  and `fusion_score DESC → source_key ASC → ordinal ASC` deterministically.
- Evidence: branch ranks, worksheet, dedup map, repeated order.

### TC-11: Vector-v2/hybrid-v2 parity with explicit allowed differences

- Steps: compare normalized resolved configurations after calibration using the closed allowed-
  difference set `{strategy, fts_candidate_k, lexical_policy_id, fusion_policy_id}`; verify every
  other field—including active Embedding Sets, Gemini configuration/input policy, literal vector
  threshold, vector semantics/budget and Evidence Selection—is identical; verify hybrid values for
  the allowed fields are `hybrid`, `8`, `fts-m3-or-v2`, and `rrf-v2`, while vector-only has its
  corresponding absent/not-applicable lexical/fusion fields.
- Expected: normalized diff contains exactly and only the allowed-difference set; no additional
  difference is tolerated. Hybrid adds the approved lexical branch/fusion semantics only.
- Evidence: machine-readable allowed-difference set, normalized full-configuration diff, resolved
  values and paired provenance.

### TC-12: Unchanged Evidence Selection

- Steps: ordered fused fixtures around adjacent same-ChunkSet overlap ratio .5 and token/count limits.
- Expected: process order; exclude only adjacent same-ChunkSet overlap ≥ .5; stop at five chunks or
  3000 tokens; no merge/fusion cutoff/v2 exception.
- Evidence: selection trace, overlap and budgets.

### TC-13: Direct production retrieval seam

- Steps: normal production Q&A/retrieval for vector, lexical and mixed questions; obtain exact
  `(workspace_id, trace_id)` traces; inspect ID/provenance/branches/ranks/selection; repeat unchanged.
- Expected: only `AnsweringStore.retrieve_candidates`, no evaluation-only/application branch path;
  stable pinned-policy order/provenance.
- Evidence: redacted responses, exact traces, seam and repeat proof.

### TC-14: #51 dependency lifecycle and handback boundary

- Steps: before #56 closure, read #51/#56 dependency and prove #51 TC-02/03/04 remain BLOCKED; after
  every #56 case passes, require explicit human approval and append the #56 Evaluation record;
  re-read dependency/closure evidence and establish only that #51 is eligible to resume
  TC-02/03/04 in its own governed workflow. Do not execute any #51 case or modify #51 guide/history
  from #56 acceptance.
- Expected: pre-closure #51 remains BLOCKED. After independently approved #56 PASS, #51 becomes
  eligible to resume TC-02/03/04 but is not executed automatically. Prior #51 TC-01/05 evidence and
  locked artifacts remain unchanged.
- Evidence: pre/post dependency and #56 closure read-backs, approved #56 Evaluation record, handback
  status, proof no #51 execution occurred, and before/after #51 TC-01/05/guide/history digests.

## Approval and locking

TC-01's exact reviewed-R9 gate and fresh authority revalidation passed on 2026-08-13. This guide is
approved, locked, and immutable. Execution observations append only to
`.agents/manual-tests/milestone-3/56-production-retrieval-v2.evaluations.jsonl`; a semantic change
requires a new revision.
