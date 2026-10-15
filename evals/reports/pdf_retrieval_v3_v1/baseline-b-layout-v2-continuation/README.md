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

The 60-case denominator comprises 35 retrieval-evaluable positive cases, 17 positive cases with extraction/mapping missing and 8 no-answer controls. Observed=60 includes those17missing cases; these counters are not disjoint. The report retains the legacy `acceptance=pending_owner_review_and_B` label from the existing builder; execution is complete and semantic acceptance remains pending.

Candidate coverage and selected-generation evidence coverage are reported separately in [candidate-vs-selected-coverage.json](candidate-vs-selected-coverage.json). Both are based on the saved post-threshold candidate pool and are not semantic quality scores.

Generation usage saved in captures was 14,779 prompt tokens and 3,552 completion tokens (18,331 total). At the approved published rates this is an estimated 365.585474 neurons for generation only; embedding usage is not present in provider metadata and the value is not an invoice or complete account usage. Cloudflare remained Workers Free / Current plan ($0), with the dashboard showing 202.67 / 10,000 at the last admission and 608.79 / 10,000 at the post-run refresh (14:32 Vietnam time). Daily delta 406.12 may include shared-account traffic and dashboard lag; it is not attributed entirely to this run. No paid gateway or upgrade was used.

## Quality findings for owner review

- 43 cases did not match the Gold expected decision at the deterministic decision layer; this is a diagnostic signal, not a semantic PASS/FAIL judgment.
- 17 cases could not be retrieval-evaluated because at least one required evidence group had no approved chunk mapping. The 25 frozen missing anchors are unchanged.
- The remaining 35 cases are retrieval-evaluable; only 8 had every evidence group in both the saved candidate pool and selected evidence.
- Saved responses, citations, refusal reasons, parent/follow-up identities, missing cases and all 60 denominators are retained in [human-review.md](human-review.md). No case was removed to improve a metric.
- Semantic review and DeepEval/Ragas/Langfuse work remain pending under Issue #158. This report does not declare semantic quality PASS.

### Concrete Retrieval/Generation issues

- **Empty retrieval:** 45/60 cases have no post-threshold candidate; generation is correctly skipped for those cases. Of52expectedANSWER cases,39 take this path. For example002/009 ask about clean text whose relevant source binding exists, but retrieve nothing. All six multi-hop cases047–052 refuse;047/048/050–052 have complete approved mapping but no candidates.
- **Missing extracted evidence:**007/028 retrieve the scan-02 title/footer chunk and then refuse; the required image facts are missing.016/017 retrieve8/4candidates (5/4selected) but refuse while at least one gold evidence group is unmapped. This does not establish a generation failure with sufficient evidence. No parser, mapping or gold was altered.
- **Typo/identifier weakness:** only045 answers among10typo/identifier cases;037–040 have approved bindings but no candidates. The intentional unaccented/misspelled queries remain unchanged.
- **Generation review flags:**005 answers14correctly at the decision layer but adds rollover rules and a28limit; owner should check relevance/over-answering.032 says no P1→P2 change outside hours without the narrower “only because outside hours” condition present in gold; owner should check overstatement.014 answers the English question in Vietnamese and has a missing gold group despite returning an answer. These are human-review flags, not agent-issued semantic verdicts.
- **Refusal controls:**053–060 all refuse;053/056 call generation with evidence and return refusal, while the other six have no candidate. Correct decision labels do not by themselves prove the reasoning or hallucination safeguards are semantically accepted.
- **Decision accounting:** expected52ANSWER/8REFUSAL versus actual9ANSWER/51REFUSAL gives9positive decision matches,43false-refusal labels and8no-answer decision matches (17/60total). All9answers require human review for facts, completeness, conditions and citations. SemanticPASS remains unclaimed.

## Review sequence

Use the same [60-case human packet](human-review.md) and saved captures for owner review, prioritizing the9answers and6generation-refusals, then inspect empty retrieval and extraction/mapping groups. Issue#158 may consume these same captures through its existing tools when separately authorized; no re-answer, judge or export was run here. The retrieval coverage of8/35does not meet a broad RetrievalV3 acceptance claim; keep threshold0.65 and preserve this baseline for later S2–S8 comparisons.

## Validation and operational evidence

The report builder accepted the packet with all 60 cases. The archive manifest contains byte hashes for captures, dispatches, source artifacts and checkpoint/quota records. A packet-local `.gitattributes` preserves raw archived bytes across checkouts; the initial report commit normalized21files, corrected in the follow-up without modifying canonical inputs. The original001failed raw capture and previous partialreport remain unchanged; the selected record is an explicit overlay for this sameattempt, not a rewrite of failure history. Canonical source remains `.verification/issue153/run`; these files are review mirrors of that same run, not a second capture authority. `persistence-after-continuation.json` confirms the same 16-document / 47-vector persisted derivation, the approved proposal/derivation/binding hashes, 61 mapped and 25 missing anchors, and unchanged original trace identity. The owned Postgres container was stopped after the run; its volume and objects were retained. The post-run read-only count check initially assumed every case used Conversations. Actual60trace IDs,8conversation IDs and16turn IDs reconcile exactly to saved captures:8parents plus8follow-ups use Conversations and44cases use direct Q&A. This was a diagnostic assertion error, corrected without inference or DB writes.

`validate_approval` checks owner/status/the twoSHA values; `approved_commit` is recorded metadata, checked separately through Git frozen-byte comparison. PR #189 remains Draft; no merge/deploy/Done. CI required succeeded on code2787eb9beforelive and initial report0f88e0d; follow-up report-head CI is tracked separately.
