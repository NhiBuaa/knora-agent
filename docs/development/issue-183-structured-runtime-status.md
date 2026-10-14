# Issue #183: structured-output runtime checkpoint

Date: 2026-10-14. PR #184 remains Draft; Issue remains open and Project In Progress.

## Approved behavior

The owner approved natural paraphrases with source anchors (Q1), proven totals
with missing-member disclosure when necessary (Q2), preservation of clear source
order (Q3), and complete citations after contiguous supported groups (Q4).
Minor implementation details do not require another design round. These approvals
do not authorize a different model, repair retry, or weaker evidence validation.

## Current implementation candidate

The Q6 candidate uses private Cloudflare paragraph/list blocks, quote
anchors, and Markdown composition. Other providers and the public generation,
citation, refusal, access and historical-source contracts remain unchanged.
Composer tests cover literal Markdown escaping, shared source qualifications,
singleton/zero count prose, missing-member disclosure and optional literal emphasis.
Structural tests are not runtime acceptance or proof of semantic support.

## Real provider observations

These diagnostics use the original #169 PDF's full extracted pages 1 and 10 as
two evidence aliases. They call the actual configured Cloudflare GPT-OSS 20B
provider, but do not run normal retrieval, store a Turn or establish browser
acceptance. Source text, credentials and raw payloads stay in ignored local files.

The latest unmodified v12 adapter/schema/prompt probe uses the production
`max_tokens=1024` and no experimental inline schema. All three questions return
HTTP 200, `finish_reason=length`, and empty message content. Completion usage is
1024 tokens for each. The adapter rejects each as `GENERATION_OUTPUT_INVALID`:

| Question type | Result |
| --- | --- |
| Chapter count, without asking to list | Invalid output; no JSON content |
| Other report parts | Invalid output; no JSON content |
| Short common-purpose question | Invalid output; no JSON content |

This establishes truncation at the provider boundary for these requests, not a
renderer fault. The response's metadata does not establish why tokens were
consumed; private reasoning content was not recorded or inspected.

Earlier probes at 2048/4096 tokens still omitted members/conditions, selected
unsupported or invented quotes, or produced malformed private blocks. Larger
budgets alone have not established a sufficient fix. Flattened schemas and
temporary numbered-line anchors also failed count/general-list checks. A short
paragraph passed selected probes; those successes do not erase failed cases.
Experimental reference formats have not been installed in maintained code.

Browser acceptance is pending actual Keycloak login in the isolated runtime at
`http://127.0.0.1:3000/workspaces`. The documented dev credentials were rejected.
No password, account, permission or source-history changes were made.

## Six-request comparison — owner approved and completed

The owner approved precisely six requests, the same questions/evidence/v12
contract, and a diagnostic cap of 4096. Paid budget is zero. Before sending, the
live dashboard showed Workers Free Active and 3.51k/10k daily neurons. The direct
Workers AI account endpoint matched that account; no AI Gateway, plan upgrade,
production configuration change or automatic retry was used. Free-plan exhaustion
fails instead of incurring Workers Paid overage, according to the pricing policy.

| Model / question | Result and manual source review | Input / completion tokens | Neurons | Seconds |
| --- | --- | --- | --- | --- |
| 20B / count | Generated 7 correctly ordered bullets and bold count; omitted suggested-outline context and merge/split qualifications; incorrectly labelled member-derived evidence explicit | 2437 / 3165 | 130.627 | 35.200 |
| 20B / other list | Invalid quote references; selected an unrelated chapter anchor for the table of contents, omitted conditions and asserted an unsupported total | 2432 / 1889 | 95.736 | 18.121 |
| 20B / short | Invalid output: duplicated the fact as list items, added a count, and supplied a nonmatching quote | 2428 / 1883 | 95.500 | 18.070 |
| 120B / count | Provider timeout at the existing 60-second boundary; no response metadata received | Unknown | Unknown | 60.019 |
| 120B / other list | Structurally valid 6 bullets, E1 anchors exist and conditional index wording retained; unsupported total 6, overlapping appendix membership and ordering not established; detailed E2 condition not represented | 2426 / 1505 | 179.804 | 35.676 |
| 120B / short | Structurally valid but 2 bullets and unrelated report-content enumeration; second item's anchor does not support all added concepts | 2422 / 731 | 126.904 | 13.841 |

Neither model meets all three cases. Valid aliases resolve to supplied pages;
the review does not treat reference existence as entailment or browser citation
acceptance. The timeout counts as one of the six attempts, with no retry. Observed
usage from five responses is 12145 input tokens, 9173 completion tokens
and 628.571 neurons; the timeout's server-side usage is unavailable, not zero.

No additional model calls follow this comparison. Raw response content and hashes,
the evidence/prompt/schema hashes and request admissions remain in ignored local
artifacts. A larger model was not selected for production.

The full local v12 suite returned 1917 passed, 16 skipped and 2 launcher failures
with `PDF_ISOLATION_UNAVAILABLE`. Both failed launcher tests passed individually
on rerun; the intermittent cause remains unconfirmed. Do not report full-suite
success. Focused provider/composer/Postgres application tests: 58 passed. Local
changes are uncommitted; old v8 CI success does not verify this candidate.

## Q6 — owner approved, code/tests authorized

The owner approved simplifying the private formatting contract to paragraph/list blocks with natural
text and per-item source anchors. Represent optional emphasis as a literal phrase
within paragraph text, so the adapter can render a count lead such as bold number
and unit without dedicated count proof fields. Remove the private count block's
basis, repeated witnesses and member-length checks; missing-member disclosures
remain natural prose required by the approved prompt and source review.

Keep strict shape/anchor checks, server-owned bullets, citation grouping and the
accepted public validator. Preserve the source-order instruction and inspect it
against actual sources. Do not introduce a semantic judge, membership catalogue,
repair retry, new dependency, framework or regex reconstruction. Semantic quality
and source-gold infrastructure remain with #153/#158; this issue keeps a bounded
manual review of its requested regression examples.

Prompt v13 implements this simplification. The behavioral composer test cycle
returned 8 failed / 20 passed before the change, then 28 passed after it. The
provider transport fixture covers prose, composed count/list and refusal with the
existing public validator. These mock results do not establish runtime reliability.
Focused provider/composer/Postgres application tests: 62 passed. Full Q6 pytest:
1923 passed, 16 skipped, 27 existing warnings in 357.55 seconds. Ruff format/check/lint,
shared formatting/check, OpenAPI check and Compose validation passed; Compose
warned about unset ambient MinIO variables. The earlier v12 failures remain above.
Final review found one Markdown escaping edge case: a tab after a numbered marker.
Its paragraph/list regression failed before the one-line fix, then all 43
composer/transport tests passed. The reviewer independently reran that regression
(1 passed) and reported no remaining actionable findings. The full 1923-pass run
preceded this fix; required CI must verify the final committed head. No provider
or browser calls were made during Q6 implementation.
Keep GPT-OSS 20B and production cap 1024 unchanged. Any further inference needs an
explicit bounded owner-approved allowance under the zero-paid-budget condition.

## Historical proposal for the approved comparison

Compare the current GPT-OSS 20B with Cloudflare GPT-OSS 120B on the same three
questions, source evidence, v12 private contract and a 4096-token diagnostic cap:
six requests, no automatic retries, no selection of only successful runs. Check
shape, retained conditions, member completeness/order, count basis and all source
anchors manually. Record failures and latency/usage as well as successes.

This is a capability comparison, not a production model/budget change. A passing
candidate must still be proposed for approval and tested through normal retrieval,
stored traces/Turns and real desktop/mobile browser citation interactions. If
neither model passes, keep the PR Draft and report the remaining limit instead of
adding a repair pipeline or weakening validation.

Cloudflare documents both models' Chat Completions support. Model pages advertise
output rates of $0.30/M tokens for 20B and $0.75/M for 120B; the latter is 2.5 times
the former per output token. This is a pricing comparison, not a guarantee of
better adherence. JSON Mode documentation does not guarantee schema compliance.

Sources: [20B model](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/),
[120B model](https://developers.cloudflare.com/workers-ai/models/gpt-oss-120b/),
[Chat Completions support](https://developers.cloudflare.com/workers-ai/changelog/#2026-02-17),
[JSON Mode](https://developers.cloudflare.com/workers-ai/features/json-mode/).
Context7 and these official pages were checked; Context7 did not establish a
model-specific Chat Completions reasoning-effort parameter for GPT-OSS.
