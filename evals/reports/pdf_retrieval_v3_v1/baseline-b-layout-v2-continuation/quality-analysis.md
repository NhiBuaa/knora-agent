# Baseline B quality analysis

This is a derived review artifact for Baseline B. It reads only the saved captures, the frozen human packet, the frozen binding, and the deterministic report. It does not rerun retrieval, call a model, alter the corpus or Gold Dataset, change threshold `0.65`, or make a semantic PASS claim.

## Scope and invariants

- Frozen corpus: `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`
- Frozen Gold Dataset: `2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae`
- Runtime proposal: `3796d4228f8bd5d6677b162125c34d551e644fe5488133c31df8b0f306488a9d`
- Derivation: `fd5711d2ce76e40dae231cc441feddce61aa36451ae073e4a55f3bbfda3f46f2`
- Approved binding: 61 mapped anchors, 25 missing anchors; the missing set is unchanged.
- Baseline configuration: pypdf layout-v2, Qwen3 Embedding 0.6B (1024d), GPT-OSS 20B, `max_tokens=1024`, threshold `0.65`.
- Denominator remains 60 cases: 35 retrieval-evaluable, 17 extraction/mapping-missing, and 8 no-answer controls. No case was removed.

The observations below are agent observations from artifacts. “Owner decision” is deliberately left separate; it is not a semantic verdict or a replacement for human approval.

## 1. Human review packet: the 15 cases with generation

The full response, citation and provenance records remain in [human-review.md](human-review.md). The capture named in each row is the immutable source for the observation.

### 9 ANSWER decisions

| Case | Artifact observation | Owner decision needed |
| --- | --- | --- |
| `001` | Expected `24 giờ`; answer states 24 hours and cites `E1` from `clean-02`. The selected same-attempt overlay is used; the historical `CITATION_STRUCTURAL_ERROR` remains recorded on the original observation. | Confirm the citation is acceptable for the final human review despite the preserved historical structural flag. |
| `004` | Expected 15 minutes; answer states 15 minutes and cites `E1` from `hierarchy-03`. | Confirm fact, scope and citation. |
| `005` | Expected only `14 lượt`; answer contains 14 and also rollover ordering, the 28-limit and Monday 09:00 check, all in the cited excerpt. | Decide whether the extra facts are useful supported context or over-answering. |
| `012` | Expected 30 days and that 90 days replaces 30 days for disputes; answer states 30 and 90 days but does not explicitly say “thay cho 30 ngày”. | Decide whether the missing condition is a completeness failure. |
| `014` | Answer is in Vietnamese to an English question, cites `E1`, and has a missing approved evidence group (`extraction_or_mapping_missing`). | Decide language acceptability and whether the response is complete with the missing group. Do not infer quality from the answer alone. |
| `029` | Follow-up answer states continuous counting, including weekends, and no confirmation fee; both required facts are present with `E1`. | Confirm fact and parent/follow-up context. |
| `032` | Answer says outside hours cannot change P1 to P2. Gold is narrower: not changing only because it is outside hours. | Decide whether the wording overstates the condition. |
| `033` | Answer gives 28 rollover uses and the Monday 09:00 check, with both required facts in the selected evidence. | Confirm fact, formatting and citation. |
| `045` | Answer attributes Apache License 2.0 to PhoNLP/toolkit and cites `E3` from `academic-phonlp`; it does not attribute the license to the PDF. | Confirm the toolkit-versus-PDF distinction and citation. |

### 6 REFUSAL decisions with generation

| Case | Artifact observation | Owner decision needed |
| --- | --- | --- |
| `007` | One post-threshold candidate from `scan-02`; the persisted chunk contains only title/footer text, not the required page count/date. Generation refused `INSUFFICIENT_EVIDENCE` without a citation. | Confirm that refusal is the appropriate behavior for unavailable image facts. Semantic quality is unknown from this trace. |
| `016` | Eight candidates, five selected, from academic PDFs. The case is `extraction_or_mapping_missing`; required approved groups are not all mapped. | Decide only whether the refusal wording/scope is acceptable. Do not label this a generation failure with sufficient evidence. |
| `017` | Four candidates, four selected, also `extraction_or_mapping_missing`; required groups remain unavailable. | Same boundary: review refusal behavior, while evidence sufficiency remains unknown. |
| `028` | One `scan-02` candidate with title/footer only; required photo-appendix facts are unavailable. Generation refused without citation. | Confirm refusal behavior for scan extraction loss; semantic answer quality is unknown. |
| `053` | One `clean-02` candidate and generation call; Gold expects refusal because the corpus has a confirmation SLA but no completion SLA. | Confirm that the refusal scope is precise and that omission of a citation is acceptable for this no-answer control. |
| `056` | One academic candidate and generation call; Gold expects refusal because no USD training cost is present. | Confirm refusal scope and absence of unsupported inference/citation. |

The six rows above are generation observations only. The deterministic label match for `053` and `056` does not establish semantic PASS; the four missing-evidence rows cannot establish that generation would have answered correctly with complete evidence.

## 2. Retrieval diagnostics from saved traces

### What is directly observed

- `45/60` captures have an empty **post-threshold** candidate list; `39` are Gold `ANSWER` cases and `6` are Gold no-answer controls.
- The 35 retrieval-evaluable cases have complete approved mapping for their required groups. Only `8/35` have every required group in the saved candidate pool, and `8/35` in selected evidence. These are separate coverage measures, not semantic scores.
- The 17 extraction/mapping-missing cases are exactly: `006, 007, 008, 014, 015, 016, 017, 028, 034, 035, 036, 041, 042, 043, 044, 046, 049`. Five of them still have candidates (`007`, `014`, `016`, `017`, `028`); twelve have none.
- `scan-02`’s persisted chunk in [captures/chunks.json](captures/chunks.json) contains the title and footer only. The `007` and `028` captures therefore show a parser/extraction limitation before evidence selection, not proof that the source image lacks the facts.
- `016` and `017` have candidates and non-zero evidence-selection phases, but the approved mappings are incomplete. The trace supports “candidate evidence exists while required mapping is unavailable”; it does not support a semantic generation diagnosis.
- For empty cases such as `002` and `006`, the capture stores the original question as `provider_metadata.conversation_context.retrieval_query`, an embedding provider request ID/model, retrieval latency, and phase timings. Generation duration is zero. There is no rewrite, decomposition or multi-query record.

### What is not stored and must remain unknown

- The captures do not store pre-threshold hit counts, scores, score margins, or rejected candidates. Therefore an empty final list cannot be separated into “no vector hit” versus “hit below `0.65`”. Threshold causality and calibration are unknown.
- No query-understanding rewrite/decomposition trace is present. Because the recorded retrieval query is the original question, a failure cannot be attributed to query understanding versus embedding/retrieval.
- Candidate objects do not include scores or a discard reason. For cases with candidates, selected IDs and timing prove that selection ran; they do not prove that selection caused a missing group or why a candidate was dropped.
- No parser alternative, OCR output, chunk boundary comparison or pre-threshold retrieval trace exists in this Baseline B packet. Those must be measured by a future controlled experiment.

### Evidence-backed cause and impact list

| Suspected cause | Evidence in this packet | Impact | Confidence |
| --- | --- | --- | --- |
| Scan/image extraction loss | `scan-02` chunk is title/footer only; `007`/`028` retrieve it but cannot answer image facts; 17 cases are marked extraction/mapping-missing. | High for scan-backed questions; blocks retrieval evaluation and generation for affected facts. | High for the observed extraction gap; not proof of source content absence. |
| Gold-anchor mapping gap | 25 frozen anchors are missing; 17 cases are excluded from retrieval evaluation, including academic/table/scan cases. | High for the 17 cases; prevents a complete evidence sufficiency judgment. | High. |
| Empty post-threshold retrieval | 45 final candidate lists are empty, including 39 expected answers and all six multi-hop answer cases `047–052`. | High observed false-refusal signal; candidate recall cause is not isolated. | High for the symptom, unknown for the mechanism. |
| Threshold/score calibration | Threshold is fixed at `0.65`, but no pre-threshold scores or margins were archived. | Potentially high, but cannot be quantified from this run. | Unknown. |
| Query understanding | Original questions are the only recorded retrieval queries; no rewrite/decomposition trace. | Potentially affects comparisons, typos, identifiers and multi-hop queries. | Unknown. |
| Evidence selection | Candidate and selected IDs plus timings exist; scores and discard reasons do not. Candidate/selected full-group totals are both `8/35`. | Possible local loss in cases such as `016`; aggregate selection loss is not measurable. | Unknown. |
| Generation behavior | 9 answers and 6 generated refusals are visible with model/prompt/usage metadata; four refusals lack complete evidence. | Human review is required for conditions, language, refusal scope and citations. | Observed behavior only; semantic quality unknown. |

No row above authorizes changing the baseline or accepting a cause without a controlled test.

## 3. S2–S8 experiments to prioritize

The labels and order below keep the approved S1–S8 plan. These are proposals only. Each row identifies one primary factor for a controlled comparison and keeps the frozen corpus, Gold Dataset, approved binding, 60-case denominator and provenance intact. None was run while preparing this report.

| Experiment | Single changed factor | Keep fixed | Measurable comparison | Gate before running |
| --- | --- | --- | --- | --- |
| **S2 — Qdrant BM25-only + lifecycle** | Retrieval backend/mode: Qdrant native BM25-only, including the contract that it makes zero query-embedding calls. | Same extracted documents, gold, query text, authorization filters, evidence policy and generation. | Query embedding calls (`0` expected), lexical candidate presence, group coverage, citation provenance, stale/reconcile/retry behavior. | Pin server/client and lifecycle contract; preserve the pypdf baseline as comparison and run the same saved gold cases. |
| **S3 — Document Understanding** | Document extraction/chunking path: Docling/OCR only where required, compared with pypdf layout-v2. | Queries, retrieval/ranking, threshold, selector and generation. | Text/page/reading-order/table coverage, missing-anchor count, binding completeness, then candidate/group coverage on the same questions. | New projection and binding review; retain all 16 PDFs including scans; no gold edits. |
| **S4 — Dense/hybrid** | Dense/hybrid retrieval configuration (Qdrant HNSW/DBSF path) versus the current retrieval path. | Source projection, query text, threshold policy, evidence selector and generation. | Candidate recall/group coverage, filtered authorization behavior, ranking/latency/RAM; keep BM25-only as its own control. | Verify Qdrant API/version, trusted prefilters, float32/quantized provenance and rollback. |
| **S5 — SDM** | Sequential Dependence scoring on the same fused candidate pool. | Candidate IDs and scores before SDM, corpus, query, threshold, selector and generation. | Ranking changes, phrase/ordered evidence retention, group coverage and deterministic tie-breaks. | Persist pre/post ranks and formulas; no candidate-pool or gold changes. |
| **S6 — AI reranking/evidence** | Configurable multilingual cross-encoder/evidence-ranking stage (including its explicit fallback). | Fixed authorized candidate pool, source chunks, query, threshold and generation contract. | Candidate versus selected coverage, per-group retention, citations, latency and fallback behavior. | Provider/model/license/resource approval; preserve deterministic fallback and do not use a judge to hide missing evidence. |
| **S7 — Query Understanding/coverage** | Bounded rewrite/decomposition/multi-query/typo policy. | Chunks, embeddings, retrieval/ranking, threshold, selector and generation. | Original versus rewritten query traces, candidate presence, multi-hop/identifier/typo coverage, fan-out and false-correction counts. | Record every derived query and cap fan-out; preserve the original question and no-answer controls. |
| **S8 — Integrated rollout/acceptance** | One cutover/recovery orchestration profile for the already selected retrieval configuration. | The selected parser, retrieval, SDM, reranker, query policy, corpus/gold and metrics. | Reconciliation, activation/CAS, revoke/delete/rebuild, rollback and held-out/legacy gates on one immutable run. | CI/Runtime Verification and owner acceptance; no production cutover or Done transition from this report. |

The evidence suggests starting with S3’s extraction/mapping seam, then S2/S4–S7 as their traces become available, and using S8 only after the component evidence is reviewable. This ordering is a recommendation, not an automatic change to S1 or a reason to defer evaluation.

## Review boundary and next approval

- This report does not freeze new data, change any metric contract, rerun a model, call DeepEval/Ragas, or export to Langfuse.
- Human review should approve or reject the owner-decision cells above using the existing saved captures. Any semantic PASS remains pending.
- The retrieval findings are diagnostic. A follow-up experiment requires its own proposal, quota/resource preflight and CI/review gate while retaining Baseline B as the comparison point.
- PR #189 remains Draft; no merge, deployment or Done transition is implied by this artifact.
