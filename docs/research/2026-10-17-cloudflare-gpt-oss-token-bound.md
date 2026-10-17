# Cloudflare GPT-OSS 20B output-token bound — primary-source findings

Date: 2026-10-17. Scope: `@cf/openai/gpt-oss-20b` on
`/client/v4/accounts/{account_id}/ai/v1/chat/completions`. Documentation/source research only;
no inference, account access, runtime change or profile activation.

## Finding

**Not established:** the inspected primary sources do not explicitly guarantee that either
`max_tokens` or `max_completion_tokens` is enforced by this exact endpoint/model as a hard ceiling
on **all billed output, including reasoning tokens**. This is an evidence gap, not proof that
Cloudflare ignores either parameter or excludes reasoning from its limit.

Parameter declarations and generic token-limit wording provide useful evidence of the intended
interface. They do not establish the requested connection between server enforcement, reasoning
generation, returned usage and billable neurons. No live verification was performed.

## Evidence

| Primary source                                                                                                                                                                                                                                                                                                                                   | Observed fact                                                                                                                                                             | Limit of that evidence                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Model schema, Messages branch](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/workers-ai-models/gpt-oss-20b.json#L382-L386)                                                                                                                                                            | Declares integer `max_tokens`, default 256, described as the maximum tokens generated in the response. The inspected model JSON does not declare `max_completion_tokens`. | It does not define reasoning-token inclusion, billable-output accounting, precedence between the two parameters or server enforcement on the compatibility endpoint. Absence from this JSON does not prove the other parameter is rejected. |
| [Workerd shared chat options](https://github.com/cloudflare/workerd/blob/1568dcf0a34da009f0a5c86b31d3a7f832ede97e/types/defines/ai.d.ts#L535-L545), [model-specific input](https://github.com/cloudflare/workerd/blob/1568dcf0a34da009f0a5c86b31d3a7f832ede97e/types/defines/ai.d.ts#L4766-L4792)                                                | GPT-OSS 20B's chat input inherits both optional numeric `max_tokens` and `max_completion_tokens`. Its reasoning is always enabled; supported effort is low/medium/high.   | Workers binding types describe a separate interface; they are not an implementation or enforcement contract for the HTTP endpoint. Low reasoning effort is not a numeric reasoning-token cap.                                               |
| [Workerd usage types](https://github.com/cloudflare/workerd/blob/1568dcf0a34da009f0a5c86b31d3a7f832ede97e/types/defines/ai.d.ts#L579-L590)                                                                                                                                                                                                       | Defines `completion_tokens` and optional `completion_tokens_details.reasoning_tokens`.                                                                                    | Types alone do not guarantee this model returns the detail, establish how those counts overlap, or equate them with billable units.                                                                                                         |
| [Workers AI glossary](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/glossary/workers-ai.yaml#L7-L10)                                                                                                                                                                                   | Context window includes input, reasoning and completion/response tokens; the glossary describes `max_tokens` as a stopping limit which cannot exceed context size.        | It does not explicitly connect the stopping limit to all reasoning and billable output on GPT-OSS 20B. Context capacity is not a demonstrated per-request billing ceiling.                                                                  |
| [Pricing explanation](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/workers-ai/platform/pricing.mdx#L11-L13), [model price row](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/workers-ai/platform/pricing.mdx#L75) | Lists USD 0.200/M input and USD 0.300/M output tokens, equivalent to 18,182/M input and 27,273/M output neurons; backend billing remains in neurons.                      | The inspected page does not specify this model's reasoning-token billing treatment or promise billable output cannot exceed either request parameter. These public rates are not account/quota or USD0 proof.                               |

The official [compatibility documentation source](https://github.com/cloudflare/cloudflare-docs/blob/c7e5b29eb2a2b986c13e744421aa750ebbaba6b8/src/content/docs/workers-ai/configuration/open-ai-compatibility.mdx)
documents the `/ai/v1/chat/completions` route and OpenAI-client usage. OpenAI-compatible request
syntax does not by itself establish identical billing/enforcement semantics.

The inspected [Cloudflare OpenAPI snapshot](https://github.com/cloudflare/api-schemas/blob/15656f084dd7a0ada54f8f659c749a7248254b9f/openapi.json)
contains the generic `/accounts/{account_id}/ai/run/{model_name}` schema, but no
`/accounts/{account_id}/ai/v1/chat/completions` path. It does not close the endpoint-specific gap.

## Local code observation and remaining unknowns

At Workbench HEAD `2cd9a77ac300adbf7643a5d5525ef8e96f533350`,
`evals/scorers/deepeval_cloudflare.py:118` constructs the judge request with model, temperature,
messages and optional response format, without either token-limit field. It reserves an HTTP
attempt and sets a 30-second client timeout; it rejects a returned non-stop finish reason.
Those controls do not constitute a documented provider-side ceiling on billable tokens. No code
was changed in this research.

Still unknown for the exact endpoint/model:

- Which limit is accepted/enforced, and precedence or validation when both are supplied.
- Whether the enforced limit includes every reasoning and final-output token, including any
  serving overhead counted toward output usage/billing.
- The precise relationship among reasoning usage, completion usage and charged output neurons,
  including truncation, timeout, disconnect and error outcomes.

An authoritative model/endpoint-specific provider contract covering these points is absent from
the inspected evidence. This note supplies no live-call authorization or inherited quota, and
does not change the blocked profile or its acceptance state.

## Retrieval record

- Context7 library `/websites/developers_cloudflare_workers-ai` was queried for this exact model
  and total reasoning/output limit. It returned generic other-model limit wording plus GPT-OSS
  metadata, insufficient for the claim above.
- The parent investigation reported HTTP403 for the developers.cloudflare.com model Markdown URL.
  This investigation did not retry or work around that restriction on the same site. It located
  `src/content/workers-ai-models/gpt-oss-20b.json` through the official GitHub repository tree and
  read independent public GitHub/raw sources without credentials or inference requests.
- Sources are pinned to Cloudflare docs commit `c7e5b29e` (2026-10-17 00:40:39 UTC), Workerd
  `1568dcf0` (2026-10-17 02:38:12 UTC), and API schemas `15656f08` (2026-10-16 23:17:24 UTC).
