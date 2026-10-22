# Retrieval V3 S1 — approved implementation A

Authority: [#153 Q1–Q5](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6163539042),
[scope A/B](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6163620843), and
[Q6 amendment](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6163913631).

Prepare one Knora corpus of 16 PDFs and 60 source-anchored cases for owner review,
reviewed exact-match derivation bindings, and production HTTP observations. A performs
local deterministic tests only. B requires owner approval of corpus/gold, a verified
Cloudflare Free plan/quota, reviewed bindings before scoring, and owned resources.
Paid budget is **0 USD**. No upgrade, paid overage, auto merge, deployment, or Done.

Baseline: pypdf layout-v2, Qwen3 Embedding 0.6B 1024d, GPT-OSS 20B
max_tokens=1024, retrieval-evidence-containment-v1 threshold 0.65. Preserve all 16/60
and report extraction/observation/provider failures separately; no tuning to pass.
Docling/OCR/LangChain belong to later S1–S8 slices; #147 direction only.

PDF distribution: 2 clean, 3 hierarchy, 2 multi-column, 3 difficult tables,
3 scan/mixed, 3 academic Vietnamese/English. Cases: 8 simple, 10 comparison,
10 table/hierarchy, 8 follow-up, 10 typo/no-accent/identifier, 6 true multi-hop,
8 no-answer. Synthetic edge fixtures must be labelled. Real PDF redistribution
rights and source versions must be evidenced. Corpus composition is a review candidate.

Gold stores source SHA-256, 1-based PDF page/visible region, verbatim source anchors,
reference/facts, AND groups of OR alternatives, follow-up parent and no-answer scope.
Owner approval is explicit and hash-bound; draft material is not frozen gold.
Exact match proposes mappings only. Repetition/ambiguity and extraction misses are
visible. Reviewed binding is bound to the source and persisted derivation digest.

#153 owns new PDF corpus/gold/binding and read-only evaluation-reader projection.
#158 owns existing runner durable correlation, tools/judges/export. Reuse existing
public-response/citation validation and Knora observations, not a second framework.
Judge unavailable is not_run; semantic review is tied to exact response digest.

Use isolated worktree, database/object root and runtime ownership. Never borrow or
restart another session's runtime. Reasonable persisted dispatch counters include
retries/timeouts; quota exhaustion pauses until reset without resetting the baseline.
No general budget service. A does not query live Cloudflare credentials or run models.

Deliver A through a PR with local verification and review packets. Owner review and
B quality evidence remain pending after A code tests pass.
