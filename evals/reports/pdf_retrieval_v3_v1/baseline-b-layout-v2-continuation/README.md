# Baseline B — Retrieval V3 layout-v2 continuation

Run `s1-runtime-binding-20261015-01` completed under the approved Issue #153 allowance. This is a deterministic runtime report; semantic quality review remains pending.

## Frozen inputs and provenance

- Corpus SHA: `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`
- Gold Dataset SHA: `2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae`
- Runtime proposal SHA: `3796d4228f8bd5d6677b162125c34d551e644fe5488133c31df8b0f306488a9d`
- Derivation SHA: `fd5711d2ce76e40dae231cc441feddce61aa36451ae073e4a55f3bbfda3f46f2`
- Binding review SHA: `7d7efbb47e548392eca3846a576552d238eb850f862bda7f9e16f7dc7bfb3288`
- Revalidation selection SHA: `c11b02c68114e5c1d65678c5d25cb35af9eaff4069d8841969d0c8fe02d6c799`
- Configuration: pypdf layout-v2 baseline, Cloudflare Qwen3 Embedding 0.6B (1024d), GPT-OSS 20B, `max_tokens=1024`, threshold `0.65`.

The persisted runtime was reused: 16 documents, 16 versions, 47 chunks and 47 completed 1024-dimensional vectors. The approved binding remains 61 mapped anchors and 25 missing anchors. No ingestion was performed during Baseline B.

## Execution and deterministic results

| Measure | Result |
| --- | ---: |
| Gold cases | 60 / 60 |
| Query embedding attempts | 60 / 60 |
| Generation attempts | 15 / 60 |
| Observed cases | 60 |
| Not run | 0 |
| Technical/provider failures | 0 |
| Decisions | 9 ANSWER, 51 REFUSAL |
| Retrieval-evaluable | 35 |
| Extraction/mapping missing | 17 |
| Candidate groups fully covered | 8 / 35 (22.857%) |
| Selected groups fully covered | 8 / 35 (22.857%) |
| Paid budget | 0 USD |
| Judge/export/automatic retry | 0 |

Candidate coverage and selected-generation evidence coverage are reported separately in [candidate-vs-selected-coverage.json](candidate-vs-selected-coverage.json). Both are based on the saved post-threshold candidate pool and are not semantic quality scores.

Generation usage saved in captures was 14,779 prompt tokens and 3,552 completion tokens (18,331 total). At the approved published rates this is an estimated 365.585474 neurons for generation only; embedding usage is not present in provider metadata and the value is not an invoice or complete account usage. Cloudflare remained Workers Free / Current plan ($0), with the dashboard showing 202.67 / 10,000 neurons at the final checks. No paid gateway or upgrade was used.

## Quality findings for owner review

- 43 cases did not match the Gold expected decision at the deterministic decision layer; this is a diagnostic signal, not a semantic PASS/FAIL judgment.
- 17 cases could not be retrieval-evaluated because at least one required evidence group had no approved chunk mapping. The 25 frozen missing anchors are unchanged.
- The remaining 35 cases are retrieval-evaluable; only 8 had every evidence group in both the saved candidate pool and selected evidence.
- Saved responses, citations, refusal reasons, parent/follow-up identities, missing cases and all 60 denominators are retained in [human-review.md](human-review.md). No case was removed to improve a metric.
- Semantic review and DeepEval/Ragas/Langfuse work remain pending under Issue #158. This report does not declare semantic quality PASS.

## Validation and operational evidence

The report builder accepted the packet with all 60 cases. The archive manifest contains byte hashes for captures, dispatches, source artifacts and checkpoint/quota records. `persistence-after-continuation.json` confirms the same 16-document / 47-vector persisted derivation, the approved proposal/derivation/binding hashes, 61 mapped and 25 missing anchors, and unchanged original trace identity. The owned Postgres container was stopped after the run; its volume and objects were retained. PR #189 remains Draft.
