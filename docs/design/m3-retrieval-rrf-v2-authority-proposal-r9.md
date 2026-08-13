# Proposed authority revision 9: M3 retrieval family v2

Status: final authority approved 2026-08-13. R9 supersedes R8 and prior v2 proposals. It does not
mutate v1 configurations, `m3-corpus-v1`, `m3-dataset-v1`, or locked Issue #51 guide `issue-51-v12`.

Approval record: explicit human approval for Issue #56, including `embedding-gemini-m1-v1`,
`google-gemini-api`, `gemini-api-generativelanguage-googleapis-com-v1beta`,
`gemini-embedding-2`, `gemini-m3-qa-asymmetric-v1`,
`EmbedContentConfig.outputDimensionality=1536`, cosine distance, provider output as returned, and
runtime-only Gemini API credentials. This approved revision is immutable; a semantic change
requires a later revision rather than editing R9.

## Provider and calibration lifecycle

`m3-dataset-v1` is development-exposed for retrieval improvement. It remains valid for #51
evaluator mechanics, but cannot be reported as unbiased v2 improvement evidence. Calibration and
held-out data must not copy, rephrase or derive its questions/content.

```text
authority pins non-secret provider/deployment identity
→ immutable embedding configuration
→ freeze calibration artifact
→ re-embed calibration corpus on existing Chunk Sets
→ calibration gates and observed-boundary threshold selection
→ numeric threshold pin
→ immutable vector-v2 and hybrid-v2 configurations
→ production M3 corpus re-embedding/activation on existing Chunk Sets
```

Raw Gemini API keys are runtime-only and must not be written to artifacts, logs, or provenance. A
provider, deployment, API contract, model, dimension, input policy, normalization or distance
change creates a new embedding configuration, invalidates old calibration, and requires
re-embedding. V2 never rechunks. This provider/configuration change is semantic, not
credential-only, and must not reuse `embedding-openai-m1-v1` or any of its vectors.

```yaml
embedding_configuration_id: embedding-gemini-m1-v1
provider_kind: google-gemini-api
deployment_identity: gemini-api-generativelanguage-googleapis-com-v1beta
api_contract_version: gemini-api-v1beta-models.embedContent-v1
model: gemini-embedding-2
model_resource: models/gemini-embedding-2
endpoint: https://generativelanguage.googleapis.com/v1beta/{model=models/*}:embedContent
embed_content_configuration:
  type: EmbedContentConfig
  outputDimensionality: 1536
dimensions: 1536
input_normalization: utf8-nfkc-v1
embedding_input_policy_id: gemini-m3-qa-asymmetric-v1
request_shape: one-text-Content-per-embedding-v1
vector_normalization: gemini-embedding-2-provider-auto-normalized-truncated-output-v1
distance_metric: cosine
```

`gemini-m3-qa-asymmetric-v1` is immutable and applies to calibration, production document
embedding, and production query embedding:

```yaml
query:
  raw_content: raw question
  normalization: utf8-nfkc-v1
  provider_text: "task: question answering | query: {content}"
document_chunk:
  raw_content: raw chunk text
  normalization: utf8-nfkc-v1
  provider_text: "title: none | text: {content}"
```

`{content}` is the respective NFKC-normalized raw value with no other text or metadata added.
Document input must never use `source_key`, a database identity, or evaluation gold metadata as a
title or any other provider input. Document/query vectors share the same embedding space, provider,
model, deployment, API contract, `EmbedContentConfig.outputDimensionality`, dimension, base input
normalization, provider-output normalization and cosine distance contract, while intentionally
using role-specific asymmetric formatting under this single input-policy ID. Changing the policy
creates a new embedding configuration/version, invalidates calibration, and requires re-embedding.

The adapter sends exactly one text `Content` per embedding call and configures
`EmbedContentConfig.outputDimensionality=1536` on every document and query call; it must not use a
deprecated request-level output-dimension field. It validates exactly 1536 response values before
persistence, stores Gemini Embedding 2 output as returned, and does not client-normalize it.
Exactly one text `Content` prevents Gemini multi-input aggregation from changing Chunk or query
identity. Embedding configuration, input-policy and active Embedding Set identities are recorded
in calibration, binding and evaluation provenance.

## Calibration artifact `m3-retrieval-calibration-v1`

The checksummed immutable artifact contains a corpus/source/chunk manifest; calibration cases with
applicability and canonical gold judgments; hard-negative/near-negative judgments; and the policy
below. It represents M3 support/knowledge natural-language retrieval and shares M3 production
parser, chunking and tokenization family. Its source keys, facts, content and questions are
distinct from `m3-dataset-v1`; no component may copy, rephrase or derive from it.

The candidate universe has more than eight chunks. Each applicable case has at least eight non-gold
retrieval-eligible distractors. Cases include multi-relevant gold sets, semantic near-negatives,
unrelated negatives and hard-negative/no-hit controls. Freeze all components before first
execution. Any post-result edit/add/remove requires a new artifact version.

Run vector retrieval without eligibility threshold and with `vector_candidate_k=8` to establish
per-case vector Recall@8 baselines. Candidate thresholds are all observed top-8 similarity
boundaries plus an empty boundary above the maximum observed similarity. Calibration passes only if:

1. Mean no-threshold vector Recall@8 is at least `0.90`.
2. At least `90%` of applicable cases have a gold Chunk in top-2.
3. Every hard-negative maximum similarity is strictly below P10 first-gold similarity over
   applicable cases.
4. A largest candidate threshold preserves every applicable case's no-threshold Recall@8 and
   excludes all hard-negative vector candidates.

Before execution, policy pins score precision, percentile method, candidate population, canonical
identity and boundary inclusion. Failure pins no numeric threshold and makes v2 unimplementable.
A passed review pins literal `vector_min_similarity` in both v2 configurations.

## Lexical policy `fts-m3-or-v2`

Document indexing is `to_tsvector('simple', content)`. PostgreSQL `simple` is the pinned
dictionary/configuration: no stemming and no dictionary stopword removal.

1. Apply Unicode NFKC and case-fold.
2. Split on the pinned Unicode punctuation/separator classifier; collapse whitespace.
3. Remove exactly: `a, an, and, are, as, at, be, by, for, from, how, in, is, it, of, on, or,
   that, the, to, was, what, when, where, which, who, why, with`.
4. Retain numeric/remaining non-empty tokens; deduplicate and sort codepoint-wise.
5. Build typed structural OR tsquery AST. Bind tokens as data via a safe compiler helper; never
   raw-interpolate user-derived tokens. Omit an unrepresentable token and record normalization.
6. With no lexemes, return zero lexical candidates/contribution, do not issue SQL or raw fallback,
   and trace policy ID, empty lexeme set, and normalization/ineligibility observation.
7. Compile non-empty AST under `simple`; eligibility is `search_vector @@ compiled_query`.
8. Rank `ts_rank_cd(search_vector, compiled_query, 0) DESC`, then source key and ordinal ascending.

`What is the refund period?` becomes `OR(period, refund)`; `30 days` becomes `OR(30, days)`.

## Retrieval family and Evidence Selection authority

Canonical Architecture/CONTEXT Evidence Selection authority for both v2 configurations is:

```yaml
max_evidence_chunks: 5
max_evidence_tokens: 3000
overlap_policy: adjacent-token-overlap-v1
selection_semantics:
  - process ordered candidates in order
  - exclude adjacent same-ChunkSet candidates when token overlap ratio is >= 0.5
  - otherwise select until chunk count or token budget limit
```

The existing `select_evidence` is conformance evidence, not the source of this authority. #56 must
preserve it and cannot change downstream selection semantics to make v2 pass.

```yaml
retrieval-m3-vector-v2:
  embedding_configuration_id: embedding-gemini-m1-v1
  vector_min_similarity: <literal from passed calibration>
  vector_candidate_k: 8
  max_evidence_chunks: 5
  max_evidence_tokens: 3000
  overlap_policy: adjacent-token-overlap-v1
  strategy: vector-only
  vector_order: cosine_distance ASC, source_key ASC, ordinal ASC

retrieval-m3-rrf-v2:
  embedding_configuration_id: embedding-gemini-m1-v1
  vector_min_similarity: <same literal as vector-v2>
  vector_candidate_k: 8
  fts_candidate_k: 8
  lexical_policy_id: fts-m3-or-v2
  fusion_policy_id: rrf-v2
  max_evidence_chunks: 5
  max_evidence_tokens: 3000
  overlap_policy: adjacent-token-overlap-v1
  strategy: hybrid
```

Hybrid receives at most eight eligible candidates from each branch before canonical identity dedup
and fusion. Paired vector/hybrid runs share active Embedding Sets, provider/config identity, vector
semantics/threshold/budget and Evidence Selection. Hybrid differs only in lexical branch and `rrf-v2`.

`rrf-v2` deduplicates canonical Chunk identity and sums `1/(60+branch_rank)` over eligible branch
contributions. Final order is `fusion_score DESC → source_key ASC → ordinal ASC`. Vector ties are
cosine distance then source/ordinal; lexical ties follow the lexical policy.

## Ownership

#56 owns v2 retrieval/calibration/production verification. Then a separate dataset-governance slice
creates/freezes held-out evaluation data. #52 only consumes it. #51 remains BLOCKED until #56 is
independently verified and cannot alter retrieval semantics for acceptance.

## External provider contract evidence

- Gemini Embedding 2 specifies `task: question answering | query: {content}` for an asymmetric
  question-answering query and `title: {title} | text: {content}` for its document; `title: none`
  is specified when no title exists.
- Gemini Embedding 2 aggregates multiple direct inputs, so this policy permits exactly one text
  `Content` per embedding call.
- The non-deprecated `EmbedContentConfig.outputDimensionality` controls reduced output dimension.
- Gemini Embedding 2 automatically normalizes truncated output dimensions, including 1536.

These claims are pinned from official Gemini documentation at approval time:
https://ai.google.dev/gemini-api/docs/embeddings and https://ai.google.dev/api/embeddings.
