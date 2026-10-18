# Issue #188 — Cloudflare P1 research

Current implementation sequencing and approval state belong only to the
[Issue #188 Master Implementation Plan](../superpowers/plans/2026-10-16-issue-188-master-plan.md).
This file preserves dated source findings, not a parallel implementation plan.

Researched: 2026-10-15. Status: proposal evidence, no inference or account modification.
Owner direction: local development; public/synthetic PDFs; P1 FLAG only; implementation,
Gateway activation, inference and budget require approval. PR #199 remains Secrets Detection.

## Verified public contracts

### Routing and configuration

Workers AI can use the existing account REST URL
`/client/v4/accounts/{account_id}/ai/v1/chat/completions` with an explicit
`cf-aig-gateway-id` header. The `api.cloudflare.com` hostname alone does not demonstrate
Gateway bypass. The documented Workers AI Gateway route requires this header; model IDs
retain `@cf/`. Inference requires Workers AI Read; Gateway configuration/log management
uses separate AI Gateway permissions. No Worker deployment is necessary for this REST path.
[REST API](https://developers.cloudflare.com/ai-gateway/usage/rest-api/).

Proposed category configuration, **not applied**:

```json
{"guardrails":{"prompt":{"P1":"FLAG"},"response":{}}}
```

The API accepts FLAG/BLOCK; omitted categories mean Ignore. Gateway updates use PUT and
require AI Gateway Write. Read the current configuration and preserve other settings;
omitting the whole `guardrails` property disables/removes its configuration. Use a dedicated
trial Gateway rather than changing a shared/default Gateway.
[Guardrails setup](https://developers.cloudflare.com/ai-gateway/features/guardrails/set-up-guardrail/).

### Detection scope and streaming

P1 uses hosted `@cf/meta/prompt-guard-2-86m`, separate from the Llama Guard 3 8B used for
S1–S13. FLAG permits requests to proceed when detector evaluation is unavailable. Long
content is segmented, potentially producing several internal evaluations. Cloudflare does
not document P1-specific role selection, serialization, chunk size/overlap, truncation,
threshold or Vietnamese accuracy on this page. The stated language list and typical
latency refer to Llama Guard, not a Vietnamese P1 guarantee.
[Usage considerations](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/).

Guardrails inspects proxied text prompts/responses; the public contract does not promise PDF
file parsing or retrieving linked files. Therefore the trial should send Knora's saved,
extracted retrieved evidence text inside the same user-message representation as generation.
This is an integration inference, not proof that all evidence bytes/roles are evaluated.
An evidence-only attack, a quotation negative, and a long/split attack must check that boundary.
[Guardrails overview](https://developers.cloudflare.com/ai-gateway/features/guardrails/).

For `stream:false`, prompt/response checks apply. With `stream:true`, the account REST API
still streams but response checks only log and do not enforce; the
`gateway.ai.cloudflare.com/v1/*` surface buffers the response into one non-streamed payload.
Use non-streaming requests for the first trial. Application SSE transport is a separate
question from upstream inference streaming.
[Streaming behavior](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/).

### Observations and API gaps

Guardrail evaluation logs include passing requests, linked by `eventID` in the dashboard.
Do not interpret a normal HTTP 200 as a completed clean evaluation.
[Guardrails logs](https://developers.cloudflare.com/ai-gateway/features/guardrails/set-up-guardrail/).

Capture `cf-aig-event-id`, `cf-aig-log-id`, request hash and trial/case metadata for correlation.
These identifiers are documented, but no P1 FLAG score/result response header is specified
in the glossary.
[Header glossary](https://developers.cloudflare.com/ai-gateway/glossary/).

`GET /accounts/{account_id}/ai-gateway/gateways/{gateway_id}/logs/{id}` exposes model,
provider, status, cost, tokens, metadata, `request_head`, `response_head` and completeness
flags. Its published schema does **not** expose a typed P1 verdict or `eventID` linkage.
Machine-readable verdict and successful-evaluation status remain trial gates; neither a
missing verdict nor a truncated payload may become TN. Confirm the actual result shape
before building an importer; if absent, retain raw evidence/manual review and stop automated
confusion metrics.
[Get log detail API](https://developers.cloudflare.com/api/resources/ai_gateway/subresources/logs/methods/get/).

Logs may retain prompts/responses and internal evaluation calls. `cf-aig-collect-log` controls
the entire entry; `cf-aig-collect-log-payload:false` retains metadata but suppresses raw bodies.
For a diagnostic trial, explicitly approve public/synthetic payload logging and its retention;
do not suppress the only usable detector evidence unknowingly.
[Logging](https://developers.cloudflare.com/ai-gateway/observability/logging/).

## Quota, billing and log retention

| Item | Current public documentation | Consequence |
| --- | --- | --- |
| Core Gateway | Analytics/cache/rate limiting free; Guardrails incurs Workers AI usage | FLAG is not a zero-cost mode |
| P1 unit price | No P1 model-specific rate found in the reviewed public pricing/model pages; Gateway pricing discusses Llama Guard | Obtain a verified P1 billing basis before approving live spend; do not substitute Llama Guard pricing |
| Standard Workers AI | 10,000 neurons/day allocation, reset 00:00 UTC; Paid excess $0.011/1,000 neurons | Account-wide remaining allowance is unknown; do not borrow another session's allocation |
| Generation | GPT-OSS 20B lists $0.200/M input and $0.300/M output tokens | A FLAG proxy trial also generates an upstream answer; count both costs |
| Request count | 16 external requests may produce more than 16 internal detector evaluations | Bound bytes/tokens, concurrency, retries and total approved spend separately |
| Unified Billing | Optional prepaid Workers AI billing; 5% credit purchase fee | No purchase, billing switch or auto recharge authorized |

Sources: [Gateway pricing](https://developers.cloudflare.com/ai-gateway/reference/pricing/),
[Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).

Gateway limits are 10 gateways on Free / 20 on Paid and five custom metadata entries per
request. The 200 requests/60 seconds Unified Billing limit is not a blanket BYOK limit.
Workers AI publishes task defaults (text classification 2,000 RPM; generation 300 RPM), but
no P1-specific guarantee was found. Use serial requests; honor 429 and stop without retries.
[Gateway limits](https://developers.cloudflare.com/ai-gateway/reference/limits/),
[Workers AI limits](https://developers.cloudflare.com/workers-ai/platform/limits/).

Logging depends on the date the account created its **first** Gateway. Before 2026-09-24:
Legacy Logs, Free 100,000 total logs across gateways / Paid 10 million per gateway. On/after
that date: Workers Logs pricing/retention. Confirm the account cohort and whether the legacy
Gateway Logs API exposes this account's new logs; do not assume API compatibility.
[Gateway pricing](https://developers.cloudflare.com/ai-gateway/reference/pricing/),
[Logging](https://developers.cloudflare.com/ai-gateway/observability/logging/).

Current Workers Logs: Free 200,000 events/day, three-day retention; Paid 20 million/month
included, then $0.60/million, seven-day retention. Single events over 256 KB are truncated.
Pricing changes again from 2026-12-01. Pin date/cohort and collect any approved trial evidence
before expiration.
[Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/).

Spend limits are eventually consistent and check completed spend; they can overshoot under
concurrency. It is not documented here whether the P1 internal evaluation cost is included
in the generation Gateway spend rule. A Gateway limit alone is insufficient proof of a
hard combined trial budget.
[Spend limits](https://developers.cloudflare.com/ai-gateway/features/spend-limits/).

## Next cloud candidates

| Group | Candidate to investigate next | Boundary to test |
| --- | --- | --- |
| PII | AI Gateway DLP in FLAG, request/response scanning | Profiles and Vietnamese identifiers are not universal PII coverage; non-Zero-Trust accounts have only Financial and Social/Insurance/National Identifier predefined profiles |
| Dangerous Output | AI Gateway response S1–S13 FLAG on hosted Llama Guard | Explicit category mapping and Vietnamese false positives required; S14 code-interpreter abuse is absent |

DLP response scanning buffers SSE; request-only scanning does not. DLP scans are free on
all plans, while broader profiles depend on the account's Zero Trust subscription.
[DLP](https://developers.cloudflare.com/ai-gateway/features/dlp/),
[DLP pricing](https://developers.cloudflare.com/ai-gateway/reference/pricing/).
S categories are documented in
[Usage considerations](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/).
These are research candidates only; no PII/Dangerous Output enablement is proposed in the P1 trial.

## Explicitly unresolved

- Parent read-only preflight on 2026-10-15 used this checkout's configured account/token:
  GET Gateway list and GET account subscriptions both returned HTTP 403 / code 10000.
  No token was printed. No configuration was changed and no inference request was made.
  Account plan, first-Gateway cohort, remaining allowance and billing mode remain unknown;
  403 does not establish that the account is Free or that a Gateway does not exist.
- P1 role/context handling, Vietnamese quality, threshold and exact price remain unverified.
- Exact retrievable FLAG verdict/evaluation-complete schema and new-log API compatibility
  must be proven by the approved canaries before spending the rest of the 16-case budget.
- The documentation establishes no standalone Guardrails-only endpoint that can classify
  saved text without forwarding a request to an upstream generation model.

## 2026-10-16 — P2 public source refresh

Scope: public documentation and the already recorded historical 403 facts only. Context7
library resolution preceded separate configuration, observation and pricing queries; live
official HTTP references were then checked because generated examples can differ from the
wire contract. No owner snapshot has been supplied. No account, token, environment,
configuration, native capture or inference request was accessed in this refresh. Earlier
sections remain dated findings; the clarifications below take precedence where more precise.
This section is evidence for the Master Plan, not authorization or a second execution plan.

### Configuration contract and controls requiring readback

The current endpoints are `POST /accounts/{account_id}/ai-gateway/gateways` and
`PUT /accounts/{account_id}/ai-gateway/gateways/{id}`, both requiring AI Gateway Write.
Both bodies require `cache_invalidate_on_update`, `cache_ttl`, `collect_logs`,
`rate_limiting_interval` and `rate_limiting_limit`; create additionally requires `id`.
The three numeric fields have a minimum of zero. Authentication, retry, billing, DLP,
Guardrails, logging/export and default-Gateway settings are additional fields, not safe
defaults inferred from sample values.
[Create](https://developers.cloudflare.com/api/resources/ai_gateway/methods/create/),
[Update](https://developers.cloudflare.com/api/resources/ai_gateway/methods/update/).

The earlier `guardrails` JSON is only a semantic fragment, not a complete executable PUT.
The HTTP keys are uppercase `P1`/`S1` etc. Prompt `P1: "FLAG"` with every other prompt
category omitted and `response: {}` means those other checks are Ignore; `IGNORE` is not
an accepted action value. Omission of the entire `guardrails` field removes/disables it.
A future approved PUT therefore needs a reviewed full body and readback, preserving the
selected Gateway's unrelated settings and billing mode. DLP is a separate setting and is
not disabled merely by omitting Guardrails categories.
[Guardrails setup](https://developers.cloudflare.com/ai-gateway/features/guardrails/set-up-guardrail/).

| Control | Verified public behavior | Remaining account-specific fact |
| --- | --- | --- |
| Authentication | `authentication: true` enforces Gateway authentication. Account REST uses `Authorization`; provider-native Gateway URLs use `cf-aig-authorization`. AI Gateway Run permissions cover all Gateways in the account, including their stored provider credentials. | Selected account/resource scope and effective permissions; no single-Gateway token isolation is documented. |
| Default Gateway | Omitting the Gateway ID selects the default; the first authenticated request can automatically create it. Auto-created defaults have authentication/logs on, cache/rate limiting off and standard Workers AI billing. | Freeze the explicit dedicated Gateway identity before any approved request; auto-created defaults are not proof of existing account settings. |
| Cache | Gateway caching defaults off; `cf-aig-skip-cache: true` bypasses it. A custom `cf-aig-cache-key` can opt a request into caching even when globally off. | Review both stored configuration and request overrides; cache HIT cannot establish a fresh P1 evaluation. |
| Retries | Published HTTP schema gives `retry_max_attempts` a range of 1–5; zero is not an accepted disabled value. Request headers can override retry settings. | Exact serialized retry-OFF state and its readback are unresolved; omission or an SDK nullable type alone does not prove OFF. |

Sources: [Authentication](https://developers.cloudflare.com/ai-gateway/configuration/authentication/),
[Manage gateways](https://developers.cloudflare.com/ai-gateway/configuration/manage-gateway/),
[Caching](https://developers.cloudflare.com/ai-gateway/features/caching/),
[Request handling](https://developers.cloudflare.com/ai-gateway/configuration/request-handling/),
[HTTP update schema](https://developers.cloudflare.com/api/resources/ai_gateway/methods/update/).

The Gateway request timeout measures arrival of the first response part, not a complete
request deadline; the documented final retry waits for completion. A future caller needs
an outer total deadline and must treat timeout/unknown outcome as indeterminate rather than
automatically resending. Universal-endpoint request arrays add provider fallbacks; dynamic
routes can also select fallbacks. Neither belongs implicitly in a one-provider trial.
[Request handling](https://developers.cloudflare.com/ai-gateway/configuration/request-handling/),
[Fallbacks](https://developers.cloudflare.com/ai-gateway/configuration/fallbacks/).

Model/provider fallback and billing fallback are distinct. On Unified Billing endpoints,
including `/ai/v1/chat/completions`, only the default BYOK alias is consulted; if absent,
requests can fall through to Unified Billing. The schema's `byok_only` prevents fallback
to Unified Billing for customer-provided provider credentials; it is not documented as a
general hard budget guard for first-party Workers AI. `workers_ai_billing_mode` distinguishes
`postpaid` from `unified`. Preserve the actual selected mode; no billing switch, credit
purchase or recharge follows from these findings.
[BYOK credential precedence](https://developers.cloudflare.com/ai-gateway/configuration/bring-your-own-keys/),
[Gateway billing configuration](https://developers.cloudflare.com/ai-gateway/configuration/manage-gateway/),
[HTTP update schema](https://developers.cloudflare.com/api/resources/ai_gateway/methods/update/).

### Native positive and completed-negative evidence remain unproven

The dashboard links Guardrails evaluations, including passing requests, using an event ID.
The published log-detail API exposes `success`, `status_code`, `metadata`, model/provider,
cost/tokens, and request/response heads with completeness flags. It still does not specify
a typed P1 verdict, evaluation-complete flag, event-ID join or all-segments coverage.
`request_head_complete` and `response_head_complete` describe those payload heads; they do
not certify completion of every internal detector evaluation. HTTP 200, log `success`,
absence of a flag, or absence of a log cannot establish a completed negative.
[Guardrails evaluation logs](https://developers.cloudflare.com/ai-gateway/features/guardrails/set-up-guardrail/),
[Log-detail schema](https://developers.cloudflare.com/api/resources/ai_gateway/subresources/logs/methods/get/).

The unresolved native mapping must eventually demonstrate both a positive and an explicit
completed-negative evaluation correlated to the exact request, model/category and all
segments. Missing, unavailable, truncated, cached or uncorrelated evidence stays unknown.
This is a required evidence distinction, not a newly discovered Cloudflare field/schema.
No importer or score/header should be invented from the current public contract.
Raw payload suppression retains metadata, but the documentation does not promise that
metadata alone includes a usable P1 verdict. Payload/retention approval therefore remains
separate from approval to view configuration metadata.
[Logging controls](https://developers.cloudflare.com/ai-gateway/observability/logging/).

P1 remains the hosted Prompt Guard model; the language list and latency statement on the
usage page describe Llama Guard. Long-content segmentation can multiply internal requests,
but P1 role selection, serialization, segment size/overlap, truncation, thresholds and
Vietnamese quality remain undocumented in the reviewed contract. FLAG proceeds if evaluation
is unavailable. With streaming enabled, account REST response checks only log; the Gateway
hostname buffers responses. Non-streaming is necessary for the proposed first canaries but
does not resolve role/coverage or completion. No protection or completed-detection claim
follows from the feature being configured.
[Usage considerations](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/).

### Pricing and conservative-bound gaps

Live pricing checked on 2026-10-16 still lists GPT-OSS 20B generation at $0.200/M input and
$0.300/M output tokens. The model page gives `max_tokens` a default of 256; an explicit
request limit is preferable to relying on that default. Workers AI has a 10,000-neuron daily
allocation and paid excess at $0.011/1,000 neurons, but the selected account's remaining
allocation is unknown. Guardrails is billed as Workers AI inference. Its Gateway pricing
paragraph names Llama Guard, while the usage page assigns P1 to Prompt Guard; no P1-specific
rate was found in the reviewed current pricing tables. Llama Guard's rate cannot fill that
gap. A numerical combined bound therefore remains unavailable.
[Gateway pricing](https://developers.cloudflare.com/ai-gateway/reference/pricing/),
[Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/),
[GPT-OSS 20B model](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/).

For known generation token counts, generation cost alone is
`(0.200 * input_tokens + 0.300 * output_tokens) / 1_000_000` USD. It excludes P1
segmentation/evaluation, retries/fallbacks and logging. A conservative combined bound needs
verified billable input/output limits, detector price and maximum internal evaluations,
retry/fallback OFF readback, log cohort/volume and the account's applicable billing basis.
Sixteen external requests or a 256-token output setting alone cannot supply those facts.

Gateway spend limits check known-model estimated cost before forwarding and update recorded
cost after requests complete. Eventual consistency can overshoot, and a configured dynamic
route can fall back rather than stop at the limit. Inclusion of internal P1 costs is still
not documented. A spend rule is therefore a secondary control, not evidence of a hard
combined ceiling, even with sequential requests.
[Spend limits](https://developers.cloudflare.com/ai-gateway/features/spend-limits/).

The first-Gateway creation date controls the log cohort: before 2026-09-24 is Legacy Logs;
on/after is Workers Logs. Legacy Logs explicitly provides the dashboard and Logs API,
retains records until deletion, and can stop insertion or delete oldest records at capacity;
oversized logs above 10 MB are not stored. This corrects any assumption of a fixed legacy
retention period. Whether the reviewed legacy API exposes a new-cohort account's evidence
still requires an owner snapshot or separately approved capability check.
[Logging cohort](https://developers.cloudflare.com/ai-gateway/observability/logging/),
[Legacy Logs](https://developers.cloudflare.com/ai-gateway/observability/logging/legacy-logs/).

Workers Logs currently lists Free 200,000 events/day with three-day retention and Paid
20 million/month included, then $0.60/million with seven-day retention; single events above
256 KB are truncated. A change is announced for 2026-12-01. These published rates do not
identify this account's cohort, current usage, actual Guardrails event count or retrievable
native schema. Truncation/retention loss must not become negative detection evidence.
[Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/).

### Historical 403: documentary hypotheses, no root cause

The two historical HTTP 403/code 10000 responses remain the only recorded observations.
Account-subscriptions GET accepts API Tokens with Billing Read or Billing Write; the
account-owned-token compatibility table includes Billing, Workers AI and AI Gateway.
Consequently neither endpoint requires a blanket move to Global API Key, and token type
alone is not an established explanation.
[Subscriptions GET](https://developers.cloudflare.com/api/resources/accounts/subresources/subscriptions/methods/get/),
[Account-owned token compatibility](https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/).

Relevant hypotheses are wrong permission/resource scope, the owner's effective role,
wrong authentication scheme, validity times, client-IP restrictions or effective Enterprise
API-access policy. They are not findings about this account. Code 10000 is not enough to
separate them; the full sanitized error context matters. Token verification exempts IP
restrictions, so a successful verification alone would not prove endpoint access.
[Troubleshooting](https://developers.cloudflare.com/fundamentals/api/troubleshooting/),
[Token restrictions](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/),
[API-access policy](https://developers.cloudflare.com/fundamentals/api/how-to/control-api-access/),
[Contextual 403s](https://developers.cloudflare.com/changelog/post/2026-08-20-contextual-403s/).

The smallest owner-provided snapshot can report the historical UTC/method/path/status and
sanitized error code/message/docs URL; token kind and authentication scheme; booleans for
intended-account match, relevant resource/permission/role coverage, active validity window,
allowed historical client IP and effective API-access policy if applicable. No credential,
token fingerprint, raw authorization header, IP address, email or unrelated account details
are needed. No such snapshot has been received or searched for, and no fresh account
request is authorized by this public-source refresh.

## 2026-10-17 focused refresh — bounded capability discovery

This refresh uses public sources only; it does not change the Master Plan's authority
or authorize account access, Gateway changes, inference or spend. Sources were checked
against Cloudflare Docs revision
[`c7e5b29`](https://github.com/cloudflare/cloudflare-docs/tree/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8)
and the generated Python SDK revision
[`6992be9`](https://github.com/cloudflare/cloudflare-python/tree/6992be906720834c83357ba99f4704c9f0ad7bd1).
Context7 returned conflicting historical pricing excerpts; the current first-party
source below governs this refresh. No P1 rate or segmentation bound was invented.

### Conditional route to a USD 0 paid-usage envelope

The current Workers AI pricing contract says Workers Free includes 10,000 neurons
per day, exceeding the allocation requires Workers Paid, and further operations fail
when the free limit is exceeded. Therefore an exact P1 per-unit price is not necessarily
a prerequisite for a **zero paid-usage** capability trial: a Free account using only
standard Workers AI billing may instead stop at its free quota. This is conditional,
not proof about the currently selected account or about availability of P1 on that
account. Shared free quota can be exhausted by this trial or other activity.
[Pinned Workers AI pricing](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/workers-ai/platform/pricing.mdx).

Before adopting that route, verify current Workers Free status, standard/postpaid
Workers AI billing, no Unified Billing credit use or fallback, and the log cohort's
applicable free allocation. Do not upgrade, add credits or change billing to make the
trial run. Workers Logs currently includes 200,000 events/day with three-day retention
on Workers Free; Legacy Logs has a 100,000-record Free storage limit and persists
records until deletion. These are shared limits, not a reservation. A free-tier trial
can fail or lose logs at quota/retention limits and must report that as unavailable.
[Billing modes](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/ai-gateway/configuration/manage-gateway.mdx),
[Workers Logs pricing](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/partials/workers/workers_logs_pricing.mdx),
[Legacy Logs](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/ai-gateway/observability/logging/legacy-logs.mdx).

The P1 price and maximum internal segmentation count remain undocumented in these
sources. A Free-only paid-usage bound does not establish a bound on internal detector
calls, an exact quota forecast or detector coverage. If the approved trial requires
an exact internal-call ceiling, those missing facts still prevent that contract.
Keep external dispatch, input bytes, output tokens and elapsed-time bounds explicit;
do not present them as a bound on Cloudflare's nested evaluations.

### Native observations: discover through two canaries before an importer

Cloudflare explicitly documents a Dashboard `eventID` link from a request to its
Guardrails evaluation log(s), including passing evaluations. That is a feasible
manual observation route for a bounded capability canary; it does not promise an
aggregate completed-negative field or a list of every expected segment.
[Pinned Guardrails log contract](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/ai-gateway/features/guardrails/set-up-guardrail.mdx).

The legacy Logs API is documented specifically for accounts whose first Gateway
predates 2026-09-24. Later accounts use Workers Logs. An empty current Gateway list
does not establish the account's first-Gateway date. Determine the cohort before
choosing a polling API. The generated `LogGetResponse` has upstream `success`,
`response_head` and `response_head_complete`, but no typed P1 verdict, `eventID` join
or aggregate detector completion. A body-completeness flag proves only payload
completeness, not that all detector evaluations succeeded.
[Pinned Legacy Logs API scope](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/ai-gateway/observability/logging/legacy-logs.mdx),
[Pinned generated log schema](https://github.com/cloudflare/cloudflare-python/blob/6992be906720834c83357ba99f4704c9f0ad7bd1/src/cloudflare/types/ai_gateway/log_get_response.py).

The smallest practical native-contract discovery is one approved attack canary and
one approved benign canary, then inspection of their exact linked evaluation logs
through the available Dashboard surface. Record native identifiers, actual evaluated
content/category/model, result and success/error evidence as exposed. Only a native
explicit successful negative evaluation may contribute a negative result. Missing,
ambiguous, failed, expired or truncated evidence remains unavailable; HTTP 200 and
absence of a flag are insufficient because FLAG can proceed without evaluation.
Do not continue the remaining pilot cases or build an automatic importer unless the
canaries establish a usable observation contract. Do not require the attack to be
predicted positive or the benign case to be predicted negative to admit the remaining
cases: correlated completed evaluations establish observability regardless of class;
any FP/FN remains in the quality report. This is capability discovery, not an
acceptance test of detector accuracy or proof of complete long-input coverage.
[FLAG failure and segmentation behavior](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/ai-gateway/features/guardrails/usage-considerations.mdx).

Requiring actual canary verdicts before the canary run would be circular. Requiring
machine-readable aggregate completion and every internal segment identifier before
any canary also exceeds the currently documented service contract. Preserve those
requirements where needed for later metrics/coverage claims; classify unsupported
claims as unavailable rather than treating missing service features as a temporary
permission problem. If the native logs cannot support completed negative results,
the capability investigation can conclude unsupported without claiming detection
completion or silently substituting another detector.

For the proposed dedicated Gateway, configure automatic retries OFF through its
documented Dashboard toggle and inspect readback. The API schema permits retry
attempt values 1–5; neither an invented zero nor an omitted update field is proof
that retries are disabled. No Gateway configuration was made by this research.
[Retry controls](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/ai-gateway/configuration/manage-gateway.mdx),
[Generated update schema](https://github.com/cloudflare/cloudflare-python/blob/6992be906720834c83357ba99f4704c9f0ad7bd1/src/cloudflare/types/ai_gateway/ai_gateway_update_params.py).

### REST authentication choice for the proposed trial

The current [REST API authentication contract](https://developers.cloudflare.com/ai-gateway/usage/rest-api/#authentication)
requires Account > Workers AI > Read on `/accounts/{account_id}/ai/*`, with the
existing Bearer token in `Authorization`. It distinguishes those inference paths
from `/ai-gateway/*` configuration/log/route management. The same page documents
`cf-aig-gateway-id` on `/ai/run` and the older model-in-path Workers AI endpoint.
Use the explicitly created trial ID, never `default` or an omitted ID. This is a
documented route to investigate with the existing permission set; do not preemptively
add AI Gateway Run, create another token, or treat a later access failure as permission
to broaden policy. Provider-native `gateway.ai.cloudflare.com` authentication is a
different surface and is not the proposed transport. Context7 fetched this contract
on October 17; no authenticated request tested it in this phase.
