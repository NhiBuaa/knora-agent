# Issue 105: controlled evidence extraction sampling

Status: **non-thinking preliminary gate failed**. This is evaluation evidence, not a
production selection. The first extraction run remains separately recorded as 6/11.

## Non-thinking seed 105

The measured code commit is `5f45623c3d5569f6176a734a4b83370e552bff01`, tree
`47a6e520e7d11000ba858f4c458eaf1e4945a937`. Qwen3 8B is pinned by the existing digest.
The prompt, extraction schema, renderer, fixture and scoring are unchanged. All eleven
actual request records verify thinking disabled, temperature 0.7, top-p 0.8, top-k 20,
min-p zero, seed 105, context 8192 and output limit 2048. The wall deadline remains 240
seconds per call. The profile follows the official
[Qwen3 8B recommendations](https://huggingface.co/Qwen/Qwen3-8B#best-practices).

| Check | Result |
| --- | --- |
| Actual requests / observations | 11 / 11 |
| Valid normalized results | 10/11 |
| Literal checks | 6/11 |
| Independent semantic review | 6/11 |
| Per-case latency | 5.96–22.48 seconds; median 14.64 seconds |

The same five cases fail: `metadata_year`, `metadata_count`, `explicit_prohibition`,
`prohibited_requirement` and `caveat_after_distractor`. Unsupported metadata inference,
invalid extraction, weakened prohibition and omitted conditions remain. These normalized
results do not reveal the precise rejection cause of the invalid extraction.

The reviewer verified code, fixture, prompt, schema, declared model pin, all eleven
request-message/option records, eight answer hashes, two null answers and one error. Both
reviewer and coordinator reproduced all eleven result/error response bindings. Seeds 106
and 107 were not run because the first seed failed. No full PDF rerun was performed.

Reports:
- `../vietnamese_rag/issue105_evidence_first_nonthinking_seed105_literal.json`
- `../vietnamese_rag/issue105_evidence_first_nonthinking_seed105_semantic_review.json`

## Thinking with the approved extraction design

The owner already approved bounded Qwen3 8B thinking and the single-call extraction design.
The earlier thinking run used the old public answer format and passed only 9/11. Combining
thinking with the new extraction format has not yet been measured; no score transfers.

The next closed profile keeps prompt, schema, fixture, renderer and scoring unchanged.
It sets thinking enabled, temperature 0.6, top-p 0.95, top-k 20 and min-p zero, with the
same context/output/deadline bounds. Profile and seed are bound in the request-policy ID.
Raw thinking remains excluded from returned results and artifacts. Seed 105 is measured
first; any failure stops this profile. A pass requires independent review and passing
seeds 106/107 before any new original36/revised36 or browser Conversation measurement.

The new thinking profile reproduced a failing request test before implementation, then
passed 27 focused tests with one live opt-in skip. Independent review verified both Qwen
profiles across all three seeds and the legacy greedy default, unchanged extraction code,
single-call bounds and thinking exclusion. Fresh isolated PostgreSQL full gate: 1392
passed, 16 skipped, 28 dependency warnings; Ruff, Compose config, OpenAPI and diff checks
passed. No frontend file changed.

Keep #105 open, PR #135 draft and #116 as the final release gate. These probes are not
Conversation/browser acceptance, and no deployment or local codex/test integration is made.
