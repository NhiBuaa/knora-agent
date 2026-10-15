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
