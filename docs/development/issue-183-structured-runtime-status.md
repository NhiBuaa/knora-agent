# Issue #183: structured-output runtime checkpoint

Updated: 2026-10-15. PR #184 remains Draft; Issue remains open and Project In Progress.

## Approved behavior

The owner approved natural paraphrases with source anchors (Q1), proven totals
with missing-member disclosure when necessary (Q2), preservation of clear source
order (Q3), and complete citations after contiguous supported groups (Q4).
Minor implementation details do not require another design round. These approvals
do not authorize a different model or repair retry. Q9 explicitly supersedes the
private literal-quote and quote-position gates; public citation validation stays unchanged.

## Current implementation candidate

The Q9 candidate uses private Cloudflare paragraph/list blocks, nonempty support
arrays of Evidence Aliases, and Markdown composition. It removes Q6's quote
matching and quote-position checks. Other providers and the public generation,
citation, refusal, access and historical-source contracts remain unchanged.
Composer tests cover literal Markdown escaping, shared source qualifications,
singleton/zero count prose, missing-member disclosure and optional literal emphasis.
Structural tests are not runtime acceptance or proof of semantic support.

## Historical v12 provider observations

These diagnostics use the original #169 PDF's full extracted pages 1 and 10 as
two evidence aliases. They call the actual configured Cloudflare GPT-OSS 20B
provider, but do not run normal retrieval, store a Turn or establish browser
acceptance. Source text, credentials and raw payloads stay in ignored local files.

The unmodified v12 adapter/schema/prompt probe used the production
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

At this historical checkpoint, browser acceptance was pending actual Keycloak login at
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

## Q7/Q8 — real retrieval/provider/browser verification, v13 not accepted

The owner approved at most eight physical Cloudflare requests, paid budget zero,
no retries, the original #169 PDF and three new Edge questions at production
20B/1024. The first ingestion attempt failed in the ignored local helper before
any provider request because its Windows multiprocessing entry point lacked a
main guard. The helper was corrected and self-checked offline; the owner then
approved exactly one recovery attempt (Q8) on the same job/PDF.

Recovery succeeded with 23 chunks and one document embedding batch. Three query
embeddings and three generations followed through UI-submitted turns: seven
physical requests total, all HTTP 200, no retry. Preflight confirmed the configured
account's Workers Free plan and 4.14k/10k daily allocation already used; no
upgrade/Gateway/paid calls. Generation results all finished with `stop`, not token
truncation.

| New UI question | Result | Input/output tokens | Generation HTTP latency |
| --- | --- | --- | --- |
| Báo cáo dự án phần mềm được gợi ý trình bày bao nhiêu chương? | Valid refusal: selected evidence ends partway through Chapter 2 and does not prove a total | 934/327 | 3.628 s |
| Báo cáo cần có những phần nào ngoài các chương nội dung? | Invalid literal anchor capitalization; multiple items in one paragraph; omitted qualification and changed modality | 1354/849 | 10.109 s |
| Mục tiêu chung của mọi báo cáo là gì? | Supported short prose rejected for changed capitalization in its quote | 925/572 | 6.276 s |

Generation usage totaled 3213 input/1748 output tokens and 106.090803 neurons.
Embedding usage was not returned and is unknown. The count turn/trace matched the
accepted refusal; the two failed turns have an error code and null result, no
QuestionTrace. Source, wire and DB captures stay local and private.

Edge at desktop 1440×960 and mobile viewport 390×844 displayed the stored refusal
or system error. No public answer/citation succeeded, so neither list presentation
nor opening the correct citation source/chip grouping was accepted. Mobile
viewport is not a physical phone. No renderer diagnosis follows from screenshots.
See the [full Q7/Q8 report](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6172692531)
and [first helper failure](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6172405428).

### Follow-up diagnosis of the count evidence selection (2026-10-15)

Read-only corpus/trace inspection found the complete seven-chapter outline and
its merge/split qualifications in chunk ordinal 1. The original seventh heading
is spelled `Chuong 7`; its spelling is preserved in the source. Q7 retrieved this
chunk at rank 2 (similarity 0.6837950), then removed it as `REDUNDANT_OVERLAP` after
selecting ordinal 0 at rank 1 (0.7008005). The trace records `retrieval-m1-v1`.
This identifies evidence selection as the reason that generation lacked the full
outline; extraction retained it. It does not change the failed count observation.

Offline replay of the saved two candidates reproduces M1's selection (650 tokens).
The existing opt-in `retrieval-evidence-containment-v1` selects both candidates
(1162/3000 tokens), preserving the complete outline and conditions. Both profiles
retain candidate count 8, similarity 0.65 and evidence limit 5. Only the overlap
policy differs; no new algorithm is proposed here.

Containment came from [PR #137](https://github.com/NhiBuaa/knora-agent/pull/137).
[Issue #136](https://github.com/NhiBuaa/knora-agent/issues/136) preserves existing
defaults and requires verification before daily opt-in; the published live gate
was still blocked. No inspected #169/#178 decision approves activation. Current
primary `.env` omits a retrieval override, matching the default used by Q7.
A historical #169 helper required that key but did not retain its value; its old
database was unavailable. Do not label a switch as restoration of a proven
accepted configuration. Q9 changes neither profile nor retrieval settings.
Activating containment requires a separate owner decision; offline replay is not
generation/browser acceptance and used no provider calls.

## Q9 — owner approved alias-only support, code/tests only

The owner selected A: retain private paragraph/list blocks with text and supplied
Evidence Aliases; stop asking the model to copy supporting quotes. Remove literal
quote matching and source-position checks rather than adding source-unit catalogs,
casefold repair or semantic machinery. Each paragraph/item still needs at least
one known alias. Backend Markdown bullets, optional literal emphasis, source
grouping, public citation validation/mapping and refusal stay intact.

Prompt v14 describes alias-only support. Clear source order, proven totals,
missing-member disclosures, all required sources and important conditions remain
prompt and manual source-review obligations under Q2–Q4. Passing alias validation
does not prove any of those properties or even correct paragraph/list selection.
Q9 does not fix count evidence coverage or authorize retrieval/model/config changes.

Composer/transport RED: 18 failed/28 passed against the v13 implementation;
GREEN: 46 passed after the change. Focused provider tests, including the existing
Postgres HTTP/trace test parameterized for the alias-only Cloudflare path: 52 passed,
one existing Starlette deprecation warning. No real provider/browser calls were
made for Q9. Review found no actionable issues; the reviewer independently ran
the 46 composer/transport tests and checked the remaining Cloudflare/Postgres
fixture update offline. This is not runtime or database acceptance.

The first full Q9 suite finished with 21 failed, 1907 passed and 16 skipped:
20 failures encountered an inherited SOCKS proxy without the optional `socksio`
package, and one Cloudflare/Postgres fixture still returned the obsolete quote
object. The fixture now returns aliases. Removing proxy variables only within a
test process made the isolated launcher regression pass; no dependency or
production launcher change was added. A subsequent full run was interrupted
because the dedicated Postgres container was stopped after Docker restart.
The container was started and readiness verified before a fresh complete run.
Keep these failed/interrupted observations; they are not successful full runs.
The fresh full suite completed with **1928 passed, 16 skipped, 27 existing
warnings**, exit 0, in 436.40 seconds. This includes the corrected PDF/Postgres
Cloudflare fixture. Ruff format/check/lint, shared format/check, OpenAPI and diff
checks passed. Compose validation passed with unset ambient MinIO variable
warnings. No maintained frontend files changed. Required CI must verify the new
committed head; its result will be recorded in PR #184 and Issue #183. A separate
bounded runtime allowance is still required.

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
