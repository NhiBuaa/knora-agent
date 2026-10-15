# Issue #183: structured-output runtime checkpoint

Updated: 2026-10-15. PR #184 remains Draft; Issue remains open and Project In Progress.

## Approved behavior

The owner approved natural paraphrases with source anchors (Q1), proven totals
with missing-member disclosure when necessary (Q2), preservation of clear source
order (Q3), and complete citations after contiguous supported groups (Q4).
Minor implementation details do not require another design round. These approvals
do not authorize a different model or repair retry. Q9 explicitly supersedes the
private literal-quote and quote-position gates; public citation validation stays unchanged.

## Q18 failure and Q19 offline alignment

[Q18 audited ledger](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6191882261)
stopped after3/9 physical requests (one query embedding, presentation and answer).
Selection chose count_list. Answer HTTP200/finish stop returned seven items, but
omitted before[0].bold and placed Markdown stars in text. v16 wire schema allowed
omission; the local count gate rejected it. Offline reproduction and persisted
Turn confirm GENERATION_OUTPUT_INVALID/result null/no trace. No public answer or
citation was produced. Desktop showed an error; mobile/general-list/short cases
were not run after the stop. Six unused requests expired.

The source supplied chapter merge/split qualifications; the model omitted them.
This separate semantic failure remains unresolved. Schema alignment is not source
acceptance or a guarantee of formatting, count proof or completeness.

Preflight violated Q18 approval: fresh Billing control failed, but the helper used
a previous Free observation to admit requests. Actual0USD cost was not freshly
verified. The primary frontend3000 was also interrupted for OAuth callback
compatibility without permission, then restarted from primary checkout. Runtime
8183/3183 stopped. Neither deviation is an approved ongoing arrangement.

Q18 responses reported2525 prompt+1599 completion tokens and89.5180923 generation
neurons; embedding usage was absent/unknown. A fresh read-only Edge audit on
2026-10-15 found the same account0815469773bb9f83177a1303be9a90f3, Workers Free
Active, and today's aggregate698.35/10k neurons (previous observation608.79).
Cost Metrics exposed token counts, not request charges. Billable usage explicitly
warns of daily refresh/estimates and showed no Workers AI charge entry. These
observations do not attribute actual cost to Q18 or retroactively meet preflight.
No inference or billing change was made during this audit.

[Q19 scope posted before edits](https://github.com/NhiBuaa/knora-agent/issues/191#issuecomment-6192150246):
the owner approved code/tests/docs only. Every paragraph now must declare bold
as a literal string or null in wire schema and local model. Composer and validation
logic stay unchanged. Raw stars remain escaped literal text; no Markdown repair,
member inference, semantic judge, module move or retrieval change. The existing
paragraph instruction is aligned; answer identity v17, presentation-v1 unchanged.
Regression tests cover the Q18 payload, missing/null/literal bold, Markdown stars,
ANSWER/refusal, citation validation and unchanged input. Eight tests observed RED
for optional schema/missing fields before the production change; focused tests
then passed101 and HTTP/PostgreSQL integration17 (one existing deprecation warning).
Full suite, review and exact-head CI results will be recorded in the Issue.

Q19 sends zero inference requests and grants none for a later turn. GPT-OSS20B,
1024 per-request cap and production defaults stay unchanged. PR184 Draft, #183
open/In Progress; #191 retains separate refactoring responsibility.

### Preconditions for a future separately approved runtime

Before provider admission, a fresh read-only check must establish account,
Workers Free Active and available quota consistent with paid budget0USD; missing,
stale or failed observations must block all network inference. No fallback to a
prior observation. Prove the helper's denial paths offline, including no grant,
wrong/stale/missing billing evidence, exhausted allowance, document embedding,
retry and stop-after-failure; keep an explicit physical-request ledger. These
checks are not yet implemented/verified and no runtime is ready to start.

OAuth must use an approved isolated callback/client for frontend3183, or another
explicitly approved arrangement. Do not stop or replace frontend3000, modify the
shared realm/client or bypass authentication implicitly. A concrete proposal and
new owner authorization are required before any such configuration change or
inference. Browser acceptance still needs all three questions, payload/Markdown/
Turn/trace/DOM comparison, desktop/mobile viewports and correct citation opening.

## Current implementation candidate

The Q17 code candidate uses fixed `before`, `items`, `after` slots, nonempty support
arrays of Evidence Aliases, and the existing Markdown composer. The owner approved
one main list group per answer; no interleaved list groups. It retains Q9's removal
of Q6 quote matching and quote-position checks. Other providers and the public generation,
citation, refusal, access and historical-source contracts remain unchanged.
Composer tests cover literal Markdown escaping, shared source qualifications,
singleton/zero count prose, missing-member disclosure and nullable literal emphasis.
Structural tests are not runtime acceptance or proof of semantic support.
It retains Q12's presentation-only request and local structural gates. Q17 removes
wire block kinds/unions and schema position constraints; cross-field conditions
remain local so refusal is valid in every mode. Count requires a leading `before`
paragraph with explicit literal/null bold, list requires at least two items, prose
requires empty items, refusal requires all slots empty. New prompt identity v16;
selection stays presentation-v1. Q18 runtime failures are recorded above;
Q19 aligns required nullable emphasis and changes answer identity to v17.

## Q13–Q16 observations and Q17 code-only approval

Q13 stopped after2 requests due to an ignored local helper's Windows UTF-8 read
bug before answer admission; it was fixed offline. Q14 stopped after3 requests:
selection returned count_list with the full outline supplied, answer v15 returned
HTTP400 before decode/composer. Q15 replayed the identical answer request once:
HTTP400/code3030/Internal Server Error, without a keyword-specific cause.

[Q16](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6186509117)
changed only the answer schema to the captured v14 schema. Its one request returned
HTTP200/10.598s, finish length, null content,1358 prompt+1024 completion tokens and
52.6181292 reported neurons. No answer reached composition. This supports a problem
involving added schema constraints without isolating a keyword; token exhaustion
remains a separate observed blocker. Combined Q13–Q16=7 physical requests. All
windows closed; no leftover allowance. Free/account/paid0USD were checked before
each approved run; absent usage in earlier failures was unknown, not zero.

Q13/Q14 desktop/mobile viewport browser runs showed System error; Q15/Q16 were
direct HTTP diagnostics, not persisted Turns or acceptance. Other list/short cases
remain unrun on v15; no bullets/citation or source-review acceptance. Preserve all
failed observations and the Q12 full-suite/PDF limits below.

[Q17 approved scope/coordination](https://github.com/NhiBuaa/knora-agent/issues/191#issuecomment-6186607494)
permits only code/tests/docs for fixed slots. No provider call, production change,
model/cap/config/retrieval change or module extraction. #191 may refactor separately
from67a149f; #183 retains behavior/prompt/schema and acceptance ownership. A new
runtime proposal must await owner approval after tests/CI. Simpler schema does not
prove completion within1024, correct selection, supported totals/members,
conditions/order or citations. Repeated runtime token/content failure must be
reported and stopped without further contract complexity.

Q17 verification before code commit: new direct-slot tests observed RED (five
expected failures), then GREEN. The focused composer/generation set passed90
tests; HTTP/Postgres provider integration plus question routes passed10 tests
(existing Starlette deprecation warning). Independent review reran94 offline
provider tests and found one missed PostgreSQL fixture; its happy/invalid payloads
were updated to the new wire shape and rechecked. No remaining actionable review
finding. Ruff format/check/lint, shared format/check, OpenAPI, Compose config and
diff checks passed; Compose retained unset ambient MinIO warnings.

Q17 full local suite ended2 failed/1970 passed/16 skipped. One stale PostgreSQL
fixture was collected before correction; the other was launcher fake-provider
unavailability. The corrected PostgreSQL file plus exact launcher case then
passed16/16; launcher root cause remained unknown. Exact-head CI for c775a83
passed every job, including CI required. No real AI requests were sent in Q17.
The initial Q19 full-suite tool session disappeared without a verdict; a fresh
detached run now writes a durable log/exit record on the separate15483 test
database. Its final verdict will be recorded in #183/PR184, not inferred from
focused checks.

## Historical Q10 failure and Q12 implementation/verification

[Q10 runtime ledger](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6183587668)
records two of six physical requests, then a stop on the first failed count
answer. Containment supplied the complete outline and merge/split qualifications;
the model returned one paragraph, literal stars, no member list or qualifications.
Finish was `stop`, not truncation. Composer = stored Turn/trace = browser DOM;
the citation opened the correct document/version on desktop and mobile viewport.
No remaining Q10 allowance may be used after that stop.

The owner approved recommendation B (Q12): select presentation, then generate
against its schema. `cloudflare-presentation-v1` returns only one bounded choice;
`cloudflare-gpt-oss-cited-answer-v15` supplies the existing blocks with aliases.
List modes must contain a list; count modes start with a paragraph containing an
explicit literal `bold` field (nullable for unproven totals). Count prose allows
zero/one known member; a proven total may still be larger, with disclosure.
Every mode permits refusal. Invalid selection stops before request two; invalid
output/truncation/HTTP failure stops without retry or conversion to refusal.

Internal traces retain both stage identities/versions/finish reasons/request IDs,
reported usage and selection; aggregate token fields require both observations.
No raw prompt/evidence/reasoning is added. Existing renderer, alias validation,
source grouping, public API, source excerpts and historical answers are unchanged.
Other providers keep their existing request path. No new dependency or #191
implementation. GPT-OSS20B and configured per-request cap1024 remain; two requests
can consume more tokens and latency per turn. Retrieval defaults are unchanged.

New transport tests observed RED (selection was treated as an answer by v14),
then GREEN: **78 composer/transport tests**, plus **17 HTTP/Postgres tests**
(one existing Starlette deprecation warning). Provider HTTP is mocked; these
checks exercise routing, selected shape rejection, count leads, refusal, unknown
aliases, stage failures/no retries, trace persistence, aggregate usage/cost,
authorization and source/citation provenance. They are not model acceptance.

Independent review found no critical/important issue and reran all 78 provider
tests successfully. Ruff format/check/lint, shared format/check, OpenAPI, Compose
and diff checks passed; Compose retained unset ambient MinIO warnings.

The first full Q12 suite ended **33 failed /1927 passed /16 skipped /27 warnings**
in 456.36 seconds. Twenty failures involved inherited proxy/HTTP client setup;
HTTPX reproduced `Invalid port: ':1'` from an ambient IPv6 NO_PROXY entry. The
isolated launcher regression passed after removing NO_PROXY alongside proxy
variables only in the test process. Thirteen Ollama probe tests rejected the
uncommitted GenerationResult source against HEAD, as their immutable-source guard
requires. Do not weaken that guard. Commit the reviewed code, then rerun the
complete suite with isolated proxy settings; this first run is not a pass.

The committed-code rerun (`ecabf744f060d0a670020b0fd9adb8475e141927`, Python
3.13.15) ended **1 failed /1959 passed /16 skipped /27 warnings**, 412.66 seconds.
All previous 33 failures passed. The remaining existing PDF multi-column test
failed in multiprocessing child startup (`AttributeError: 'tuple' object has no
attribute '_bootstrap'`), reported safely as `PDF_EXTRACTOR_UNAVAILABLE` before
extraction. Its isolated rerun passed (1 test, 1.23 seconds). No PDF code, test,
deadline or isolation gate was changed; do not label this a green full run or a
fixed extractor. The whole-file follow-up passed **31 tests /3 skipped** in
17.54 seconds; the child startup failure did not recur. Its underlying cause is
not established, so this observation remains a limitation. Exact-head CI and the
final checkpoint are recorded in Issue #183/PR #184; retained local XML is under ignored
`frontend/test-results/issue183/q12/`.

No real provider call is authorized by Q12. A new bounded allowance
must count one query embedding plus two generation requests per question, with
Workers Free/paid budget0USD preflight, and await owner approval. Selection may be
wrong; schema cannot prove members, conditions, total or order. Do not claim #183
complete, merge, close the Issue or move Project to Done.

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
