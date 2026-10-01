# Issue 105: controlled evidence extraction sampling

Status: **both profiles failed preliminary acceptance; thinking also failed the runtime
deadline gate**. This is evaluation evidence, not a
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
The earlier thinking run used the old public answer format and passed only 9/11. Its score
does not transfer to the new extraction format.

The real seed-105 run used commit `c140abf7cc08e7036fbbaad605f7ee92d1981d1b`, tree
`e2bd09c0b9f4347812616aaf0888ed4f5cc785c0`, with unchanged prompt, schema, fixture,
renderer and scoring. All eleven request records verify thinking requested, temperature
0.6, top-p 0.95, top-k 20, min-p zero, context 8192 and output 2048. A nonempty returned
thinking field was not recorded. Raw thinking is excluded from results and artifacts.

| Check | Result |
| --- | --- |
| Actual requests / observations | 11 / 11 |
| Valid normalized results | 9/11 |
| Literal checks | 7/11 |
| Independent semantic review | 7/11 |
| Returned-result latency | 21.60–149.52 seconds |
| All-observation latency | 21.60–451.91 seconds; median 39.27 seconds |

Failures are `metadata_year` (provider error), `explicit_prohibition` (invalid
extraction), `prohibited_requirement` (weakened prohibition) and
`caveat_after_distractor` (ordinary rule omitted, although conditional exception is
now preserved). The reviewer and coordinator verified all eleven response bindings,
six answer hashes, three null answers and two error records. Nine returned results
have finish reason `stop`. Seeds 106/107 and full PDF were not run.

Reports:
- `../vietnamese_rag/issue105_evidence_first_thinking_seed105_literal.json`
- `../vietnamese_rag/issue105_evidence_first_thinking_seed105_semantic_review.json`

## Runtime deadline finding

The configured 240-second asyncio deadline did not establish a hard elapsed bound:
`metadata_year` took 451.90649 seconds. It is a failed runtime observation, not an
acceptable latency trade-off. The sanitized provider error does not prove its cause.
Earlier statements that the configuration guarantees a hard 240-second bound are
superseded by this finding; historical literal reports retain their original fields.

A separate controlled diagnostic used the existing timeout wrapper with a 10ms deadline
and a provider whose cancellation cleanup awaited 200ms. It returned the safe error after
218ms. This proves that cooperative cancellation can outlast the configured deadline;
it does not establish why the real call took 451.9 seconds. No inference rerun, score
repair, validator relaxation, larger model download or timeout-bound change was made.

The new thinking profile reproduced a failing request test before implementation, then
passed 27 focused tests with one live opt-in skip. Independent review verified both Qwen
profiles across all three seeds and the legacy greedy default, unchanged extraction code,
single-call bounds and thinking exclusion. Fresh isolated PostgreSQL full gate: 1392
passed, 16 skipped, 28 dependency warnings; Ruff, Compose config, OpenAPI and diff checks
passed. No frontend file changed.

Keep #105 open, PR #135 draft and #116 as the final release gate. These probes are not
Conversation/browser acceptance, and no deployment or local codex/test integration is made.
