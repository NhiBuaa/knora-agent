# Issue #188 P2 — capability investigation and trial packet

Status: **P2 investigation has public-source and approved Dashboard metadata
evidence; P3 is not ready.** This is a verification artifact, not a competing plan.
It records evidence available on 2026-10-16. Current-chat approval covers proactive
safe local metadata and Cloudflare Dashboard reads. It prohibits token-secret
access, new agent-constructed authenticated API/CLI requests or configuration changes.
The separately approved Q3 exception added exactly two token Read permissions;
Q4/Q4b subsequently authorized a bounded credential-in-memory API recheck as recorded
below. Neither grants further permission changes or unrestricted API access. Normal Dashboard navigation used its existing browser
session and browser-managed read traffic. No inference, spend, export, runtime
activation, enforcement, merge or deployment is authorized.

## Authority and boundary

The controlling sequence is the [Issue #188 Master Implementation Plan](../superpowers/plans/2026-10-16-issue-188-master-plan.md).
P1 remains the exact offline fixture and `generation_evidence` envelope approved in
the [#192 ACK](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6200725822):
selected immutable inputs, native identities/digests, a separate consumer projection
of `[alias, content]`, and a supplementary report. Gold/canonical reports are not
changed, no latest trace is selected, and no answer is regenerated.

The historical preflight made only two read-only requests. Both returned HTTP 403
with error code `10000`. Its record says this checkout's configured account/token,
but does not identify a token display name, token kind or environment-variable
binding. Current policy evidence below narrows the explanation; historical token
identity and policy continuity are still **unproven**.

## Approved metadata observations before Q3

Observed through the existing Edge Dashboard session on 2026-10-16, approximately
03:20–03:27 UTC. These are sanitized observations, not a full configuration export.
The durable envelope is [the Dashboard observation record](issue-188-p2-dashboard-observation.md),
SHA-256 `a7f46229574b0dbcb0350a18f7f312549ddaef60e7623b9d96c40165ebe1b609`.
Raw account IDs, emails, IPs, payment details and token values are not retained here.

| Selected surface | Observation | Limit |
| --- | --- | --- |
| Local account setting | Allowlisted lookup of `KNORA_CLOUDFLARE_ACCOUNT_ID` in the primary checkout matched the selected Dashboard account. The selected worktree has no `.env`; the shell process has no account setting. | No token setting was read. This proves current account equality only, not the historical request path/account. |
| Account API tokens | Dashboard displayed the first-token onboarding state, with no account-owned token rows. | Does not identify the historical credential or rule out another user's token. |
| User token named `Workers AI` | Active, one account, last used Oct 15, 2026, expiry shown as `-`. Read-only summary and unchanged policy form showed exactly `Workers AI:Edit` and `Workers AI:Read`, including the selected account. | **No AI Gateway or Billing grants in this selected policy.** No token secret, prefix, suffix or fingerprint was accessed. |
| Selected token restrictions | Policy form showed no selected IP-filter operator/value and TTL `Select time range`; list showed no expiry. Form was exited via Back with no field changes or submission. | No current IP/TTL restriction was displayed; exact validity timestamps and historical restrictions remain unknown. |
| Workers plan and subscriptions | Workers plans marked Free as Current plan; Subscriptions marked Workers Free Active. | Does not establish every Cloudflare product entitlement or a future Gateway billing mode. |
| Workers AI usage | `Neurons used today: 0/10k`; UI says daily reset at 00:00 UTC. | Point-in-time, shared-account display; no reservation, future allowance or P1 cost guarantee. |
| AI Gateway landing | Onboarding view said the default Gateway will be automatically created by the first authenticated request and offered Create a custom gateway. No Gateway list/configuration or native Guardrails evaluations were available in that view. | Treat target Gateway/configuration, historical first-Gateway date, log cohort and native verdict as unavailable; do not infer that no Gateway ever existed. No example was executed and no Gateway was created. |

**403 assessment before Q3:** the selected token lacked both permissions required by
the failed endpoint types. If the historical calls used this token with this same
policy, missing AI Gateway Read and Billing Read is a sufficient permission-based
explanation. Current evidence does not prove that antecedent or exclude other
historical failures. Dashboard access uses browser identity and does not validate
this API credential. At that pre-Q3 checkpoint, neither endpoint had been retried.
Current successful endpoint checks are recorded under Q4/Q4b below.

### Q3 — approved token policy change and readback

On 2026-10-16, the owner approved adding exactly `AI Gateway:Read` and `Billing:Read`
to the existing user token `Workers AI`, then explicitly confirmed the final
`Update token` action. At approximately 14:21 UTC (21:21 Asia/Saigon), Dashboard
reported `Token has been updated`. A subsequent **View summary** readback showed:

- `AI Gateway:Read` and `Billing:Read` added.
- Existing `Workers AI:Edit` and `Workers AI:Read` retained; same selected account.
- No edits to account scope, IP filtering or TTL in the submitted form; token remained
  Active in the post-save list. No roll, new token, secret access or Gateway change.

This supersedes the earlier missing-grants observation for the current policy only.
The original observation envelope remains unchanged. Q3 does **not** authorize API
retry, inference, spend or data egress. At the Q3 checkpoint, neither endpoint had
been retried. The separately approved Q4/Q4b outcomes below supersede that access
status; historical credential linkage remains unverified.

### Q4 — approved bounded API recheck, stopped after first request

The owner separately approved exactly this envelope in this chat:

- An isolated local process may load only `KNORA_CLOUDFLARE_ACCOUNT_ID` and
  `KNORA_CLOUDFLARE_API_TOKEN` from the primary checkout's existing `.env`, for
  request authentication in memory. No secret value, header, prefix, suffix,
  fingerprint or raw environment/file content may reach tool output or an artifact.
  This requires an explicit exception to the current prohibition on credential reads.
- At most two HTTPS GETs to `api.cloudflare.com/client/v4`: one
  `/accounts/{selected_account}/ai-gateway/gateways`, then one
  `/accounts/{selected_account}/subscriptions`. Use the existing Bearer credential;
  no token verification call, pagination, redirects, retries or alternate credentials.
- Timeout at most 20 seconds per request; response body cap 256 KiB. Stop the sequence
  on access failure, timeout, redirect, oversized/malformed response or unexpected
  account binding. Do not dump raw exceptions or responses.
- Retain only UTC, endpoint template, HTTP status, boolean `success`, numeric error
  codes and result count. Do not retain raw Billing/Gateway payloads or account IDs.
- No request body, inference, Gateway/config/token change, new dependency, budget
  authorization or additional egress. Credential is sent only as the authentication
  header to the named Cloudflare API host over TLS.

This tests the currently configured credential. Its equivalence to the Dashboard
token or the historical credential is not inferred from its location, and no secret
comparison is permitted. Success would prove current access to the tested endpoints,
not historical root cause, native P1 capability or readiness to run P3.

**Observed execution:** the one-off local checker passed an offline assertion check
of selected-key parsing and safe output before credential/network access. Q4 then
made exactly one external request. Its retained result is:

| UTC | Endpoint template | HTTP | `success` | Error codes | Result count |
| --- | --- | --- | --- | --- | --- |
| 2026-10-16T15:38:58.413726+00:00 | `/accounts/{selected_account}/ai-gateway/gateways` | 200 | true | `[]` | 0 |

The request account matched the selected account's locked digest. The secret and
raw response were not printed or persisted. The local check nevertheless exited 1:
in addition to the reported successful fields it required `payload.get("errors") == []`,
which was not satisfied. The normalized empty numeric-code list does not retain
whether `errors` was absent, null or another shape; do not invent that fact. No
response body is retained to reparse.

Per Q4's stop condition, **subscriptions was not requested**, and neither endpoint
was retried. Current Gateway-list access is proven by HTTP 200 / `success:true`;
the selected response page contained zero Gateways. Subscriptions access, historical
credential continuity and native P1 capability remain unverified. The halted sequence
is not a live process or a reusable permission allowance. Any continuation must
explicitly authorize the one remaining subscriptions GET after an offline repair
of the overly strict optional-field handling; do not repeat the successful Gateway GET.

The checker was subsequently repaired offline to accept absent/null/empty `errors`
only with HTTP 200, boolean success true and a result list; contradictory nonempty
errors, malformed errors, success false and missing result lists remain rejected.
The assertion check passed without credential or network access. A single-subscriptions
dispatch mode was prepared with the same process deadline and sanitization. Its
subsequent approved execution is recorded below; the repair does not retroactively
determine the original Gateway response's unretained field shape.

### Q4b — remaining subscriptions GET approved and completed

The owner explicitly approved the one remaining subscriptions GET after Q4 stopped,
with all Q4 credential, timeout, output and no-retry restrictions retained. Before
execution, the single-endpoint dispatch/deadline and offline assertions were checked.
Exactly one external GET was then sent; the process exited 0. Retained result:

| UTC | Endpoint template | HTTP | `success` | Error codes | Result count |
| --- | --- | --- | --- | --- | --- |
| 2026-10-16T15:45:46.105728+00:00 | `/accounts/{selected_account}/subscriptions` | 200 | true | `[]` | 1 |

The successful Gateway GET was not repeated. Across Q4/Q4b, exactly two external
GETs were made, with no retries, redirects, pagination, inference or mutation.
Both endpoints now have successful access evidence for the selected account and
configured credential. This resolves the *current endpoint-access* uncertainty;
historical credential identity/policy continuity and the cause of the old 403s
remain unproven. No token value/header/fingerprint or raw payload was printed or
saved. The subscriptions response's product/plan details were not retained or
interpreted: the approved output contains only its count, not billing/entitlement
proof. These one-time allowances are consumed; further API/credential use requires
a new concrete scope. P3 remains separately gated.

## Existing native capture handoff

The explicitly named [Workbench capture handoff](https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6201161284)
records the following identities. They were checked against that comment, not against
capture bytes or the runtime. This does not authorize a newer trace lookup:

| Native identity or digest | Recorded value |
| --- | --- |
| Workspace | `19de636b-44a7-42ff-b6da-b8032811c855` |
| Dataset/version | `ae04464e-4b8c-456b-b8af-696c17d003af` / `v1` |
| Gold/reference digest | `sha256:ebcbd6480769ace53eb32782e6bfeda0b64ec2e300da0e4f877cb46198bba22f` |
| Saved run | `92c5457f8a8e494db14191b99d6fc6b6` |
| Named saved traces | `4753b5bf-5d14-42e8-a4af-9cd1b8051f48` (`answer-1`); `d8492c6e-0f7e-4a11-9f7a-8185e8728780` (`refusal-1`) |

The handoff states that `answer-1` has retrieval status `BELOW_THRESHOLD` and empty
`generation_evidence`; a detector requiring generation evidence must therefore record it
as **unavailable**, not as a benign or completed-negative verdict. This capture is
useful for identity and unavailable-path binding, but it does not supply the full
16-case native positive/negative trial population or a completed native P1 verdict.
The consumer must still project the ordered Workbench `[alias, content]` pairs in a
separate module and bind the supplementary `knora-security-observation-v2` report;
neither the gold/canonical reports nor this capture is modified here.

The handoff does not supply attempt IDs or a capture-artifact digest. Its gold/reference
digest is not a capture digest. Those bindings must be supplied and checked before
consuming this capture. The synthetic pilot below does not require native capture IDs.

### Existing projection pieces and remaining integration gap

The legacy producer `project_generation_evidence()` in
`evals/runners/milestone_3.py` returns ordered `(alias, content)` pairs, requires
the exact `E1..En` alias mapping, includes selected uncited evidence and excludes
excluded distractors. However, `evals/runners/run_security_shadow.py` requires
object entries with `content`, and `evals/runners/cloudflare_p1_shadow.py` reads
`alias`/`evidence_id` from those objects after capture validation. It does not accept
Workbench pair arrays directly or call the legacy producer. The focused producer
tests passed **2/2** (`test_milestone_3_runner.py -k generation_evidence`); neither
these nor the 128-test suite proves Workbench-pair consumer compatibility.

A separate #188 consumer projection preserving the selected ordered pairs and native
bindings remains necessary before that capture can be used. No implementation or
shared Workbench edit is part of this P2 investigation. This gap does not require
rebuilding the existing synthetic P1 fixture pipeline.

## Capability matrix

| Capability | Current public evidence | P2 conclusion |
| --- | --- | --- |
| List AI Gateways | `GET /accounts/{account_id}/ai-gateway/gateways` accepts API Token or legacy API Email + API Key and requires `AI Gateway Read` or `AI Gateway Write`. [Cloudflare API reference](https://developers.cloudflare.com/api/resources/ai_gateway/methods/list/) | AI Gateway Read added under Q3. Q4 verified current HTTP 200 / success true / zero results on the selected page; historical credential linkage remains unknown. |
| Read account subscriptions | `GET /accounts/{account_id}/subscriptions` accepts API Token or legacy API Email + API Key and requires `Billing Read` or `Billing Write`. [Cloudflare API reference](https://developers.cloudflare.com/api/resources/accounts/subresources/subscriptions/methods/get/) | Billing Read added under Q3. Q4b verified current HTTP 200 / success true / one result; no product/plan details retained. This is separate from Workers AI and AI Gateway permissions. |
| Verify token | `/user/tokens/verify` reports token status. Cloudflare's troubleshooting guide says to confirm `status: active`. [Troubleshooting](https://developers.cloudflare.com/fundamentals/api/troubleshooting/) | A future read may verify status, but active status alone does not prove target-account access. |
| Token resource scope | User tokens inherit a subset of user permissions; account-owned token grants are bounded by the creator's permissions. Token permissions are resource-scoped. [Account tokens](https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/), [Create token](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/) | Credential kind, relevant permission names, creator/user ceiling, and requested-account equality must be checked without reading the secret. |
| Runtime token restrictions | Client IP filtering and TTL can restrict target calls; the Verify Token endpoint is exempt from IP filtering. [Restrict tokens](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/) | A successful verify would not rule out a historical IP, `not_before`, or expiry failure. |
| Account-token compatibility | Current account-token compatibility lists AI Gateway, Billing, and Workers AI. [Account tokens](https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/) | No evidence supports categorically rejecting account-owned tokens or switching to a Global API key. |
| Gateway availability and logs | AI Gateway is available on all plans; log behavior depends on first-Gateway cohort and plan. Guardrails are billed as Workers AI token inference. [Pricing](https://developers.cloudflare.com/ai-gateway/reference/pricing/) | Workers Free and the current 0/10k usage display are observed; target Gateway, first-Gateway date, billing mode, retention and P1 billing basis remain unverified. |

Code `10000` is not diagnostic by itself: Cloudflare's own successful token-verification example includes a `messages[].code=10000` informational message. The future packet must preserve HTTP status, `success`, and the distinction between `errors` and `messages`, including any `documentation_url`.

## Historical-403 hypotheses

These are testable hypotheses, not findings about the current account:

1. Missing `AI Gateway Read` or `Billing Read` (or a user/creator permission ceiling).
2. Requested account differs from the token's resource scope.
3. Bearer token versus legacy API-key syntax mismatch.
4. Token inactive, not yet valid, expired, or restricted by historical client IP.
5. Enterprise account/member API access disabled, if the account is Enterprise.

No hypothesis independently authorizes a permission expansion, a new credential,
a Global API key or an authenticated retry. Only the explicit Q3 change above was approved.

## Missing historical provenance and fallback collection

The agent collected the safe current policy/account/plan/usage metadata above.
Do not ask the owner to collect those facts again. Only historical fields absent
from the selected issue record remain uncollected:

1. For each historical request: UTC timestamp, path template, HTTP status, `success`,
   sanitized `errors[].{code,message,documentation_url}`, and request/Ray ID if retained.
2. Whether both historical calls used the user token named `Workers AI`, whether
   its policy was the same then, and the authentication scheme label. No secret
   comparison or fingerprint is needed or permitted.
3. Whether the historical requested account matched the currently selected account;
   historical validity/IP/API-access restrictions only if retained and applicable.

The agent checked [the named historical comment](https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6193633990)
and its two explicitly named Markdown artifacts at `5c580a313d17e1b75b130337bc036943319a00e7`.
They do not retain this provenance or the full sanitized error envelope. Do not
search shell history, credential stores, arbitrary logs or latest traces to recover it.
If the owner has the original selected preflight record, provide only the fields
above after removing headers/credentials. Otherwise an owner attestation of token
display name/policy continuity, or `unknown`, is enough to classify the historical
diagnosis. No manual Dashboard screenshots are needed for already observed facts.

Keep absent fields as `unknown`. Do not include Authorization headers, token strings,
token prefixes/suffixes/fingerprints, email addresses, unrelated accounts, or raw
Cloudflare payloads.

## Proposed P3 trial packet (not approved)

This is the smallest reviewable packet to present after the sanitized capability
read. It is not an allowance or a configuration instruction.

- **Input:** the existing 16 synthetic VI/EN cases, fixture SHA
  `sha256:2cac53d286a9ca1496614c9a5f24af548efd35380b92bb6063299f106d10a186`;
  public/synthetic text only. Existing fixture case IDs and digests are synthetic;
  they are not native run/attempt/trace/workspace identities. A later real capture
  must pin actual native identities/digests and build its own ordered `[alias, content]`
  consumer projection. Missing identities stay unavailable. No gold/reference answer
  or private data is sent.
- **Gateway intent:** a dedicated trial Gateway whose semantic diff is prompt P1
  `FLAG`, no other hazard `BLOCK`, response checks ignored, caching/retries/fallbacks
  disabled, and existing billing mode preserved. The exact JSON field/readback must
  be confirmed against the account's current configuration before any write. No
  Gateway is created or changed by P2.
- **Requests:** at most 16 external generation requests, serial, `stream:false`,
  no retries or continuations, output cap 256 tokens, 60 seconds/request, 20 minutes
  total, and at most three read-only log polls per case. These are proposed bounds,
  not approved inference authority.
- **Cost:** do not use the historical USD 1 suggestion as a budget. The October 17
  refresh identifies a conditional USD 0 paid-usage route: verify current Workers
  Free, standard Workers AI billing, no Unified Billing credit use/fallback, and
  applicable free logging. Shared quota may be depleted; no upgrade, purchase or
  billing change is allowed. Without those facts, a conservative combined paid-cost
  ceiling is still required. P1 unit price and internal call count remain unknown.
- **Native evidence gate:** before dispatch, establish a feasible native observation
  and correlation route. The first two authorized attack/control canaries then
  discover actual native completion/verdict evidence and exposed coverage before
  any remaining dispatch. Continuation depends on usable correlated observations,
  not on obtaining the expected TP/TN; retain FP/FN. These verdicts are trial outputs,
  not results that must already exist before P3. HTTP 200, a model answer, an unflagged
  log, a missing/truncated log, or a hypothetical import is not a negative result.
- **Stop and rollback:** stop before further dispatch on 403/429, routing or
  FLAG-only drift, missing correlation/verdict, inaccessible or truncated logs,
  unknown cost, timeout with ambiguous send state, or any data-scope mismatch. Any
  future configuration trial must restore the exact pre-trial snapshot and verify
  readback; this document grants no write or rollback action.
- **Reporting:** retain selected/attempted/observed/completed/unavailable/error/
  timeout populations; publish only the existing digest-bound
  `knora-security-observation-v2` supplementary schema, with no raw messages,
  secrets, response bodies, or provider reasons. The supplementary report and the
  ordered `[alias, content]` consumer projection remain separate artifacts.

### Configuration and observation contract gaps

The [dated public-source refresh](../research/issue-188-cloudflare-p1.md#2026-10-16--p2-public-source-refresh)
contains the checked HTTP contracts. A future complete create/update body needs
`cache_invalidate_on_update`, `cache_ttl`, `collect_logs`, `rate_limiting_interval`
and `rate_limiting_limit`; create also needs `id`. The Guardrails semantic fragment
is `{"prompt":{"P1":"FLAG"},"response":{}}` under `guardrails`. Other categories
are omitted (Ignore); omitting all `guardrails` disables it. This fragment alone
is not a runnable PUT. No current target snapshot exists for an exact diff.

| Proposed control | Admission evidence required before a future write/run |
| --- | --- |
| Explicit dedicated authenticated Gateway | Named approved account/Gateway, exact full body, effective permissions and account-wide Run exposure accepted; no implicit default auto-creation. |
| Only prompt P1 FLAG | Full Guardrails readback, response checks ignored, DLP/other hazards separately checked. A generation may succeed when P1 is unavailable. |
| Cache OFF | Stored config plus request headers; bypass cache, no custom cache-key override, no cache HIT counted as a fresh evaluation. |
| Retry/fallback OFF | Use the documented Dashboard Retry Requests toggle OFF and inspect readback. API omission is not proof of OFF; published `retry_max_attempts` minimum is 1, so do not write 0. No client retry, universal endpoint array, dynamic route or provider fallback. |
| Billing preserved | Actual `workers_ai_billing_mode` and billing fallback behavior. No Unified Billing switch, credit purchase, top-up or auto-recharge. |
| Native verdicts | Dashboard request-to-Guardrails `eventID` links, including passing evaluations, provide a documented discovery route. Inspect the exact canary evaluations before implementing an importer. Public log-detail schema has no typed P1 completion/verdict/event join; request-head completeness is not evaluation completeness. Explicit successful negative evidence is required for a negative result. |
| Roles/segmentation | Record evaluated text/roles and segment coverage actually exposed by canaries. Complete internal segment enumeration is not a precondition to bounded discovery; unsupported coverage claims remain unavailable. P1 segment size/overlap/truncation/VI quality remain undocumented. |
| Logs | Actual cohort, payload-suppression effect, retention, capacity and truncation behavior. No raw log import or extra payload retention authority follows from metadata-read approval. |

Generation-only published cost is
`(0.200 * input_tokens + 0.300 * output_tokens) / 1_000_000` USD for GPT-OSS 20B.
It excludes P1 internal evaluations and logging. The reviewed tables do not supply
a hosted P1-specific rate or a maximum internal segmentation count. The observed
free allowance alone and Gateway spend limits do not establish a combined hard ceiling.
The October 17 refresh below describes a conditional Free-only alternative; its
current account predicates remain unverified. No paid trial or final executable
account configuration is presented as ready.

## Offline verification

Fresh checks used existing installed tooling; no dependency or service was started:

- Focused P1, Secrets, saved-capture projection, ownership and evaluation-runner
  boundary suite: **128 passed** across `test_cloudflare_p1_shadow.py`,
  `test_security_shadow.py`, `test_milestone_3_runner.py`,
  `test_source_clause_projection.py`, `test_evaluation_ownership.py` and
  `test_evaluation_runner.py` (`-p no:deepeval`, `PYTHONPATH=backend/src`). The
  P1/Secrets subset alone is 56 passed.
- A full-suite attempt in the existing environment cannot collect
  `test_deepeval_capture.py` and `test_ragas_review.py` because `deepeval` and `ragas`
  are not installed; no dependency was installed for this phase. With those two
  modules excluded, the first fail-fast run reached 23 passed before the existing
  Windows launcher test `backend/test/adapters/cli/test_dev_launcher.py::test_daily_cloudflare_preflight_needs_no_ollama_and_pins_profile`
  returned `PROFILE_RESOLUTION_FAILED`. This is outside the documentation-only P2
  diff and was not altered or treated as a P2 success signal.
- Ruff repository check passed; `docker compose config --quiet` passed with the
  selected worktree's unset MinIO credential warnings. No runtime was started.
- Pinned fixture has 16 unique cases, four positive and four control cases per VI/EN.
  Labels remain draft/unaccepted. One-off preparation ran with socket/subprocess
  audit guards and produced no network or subprocess attempt.
- Prepared report SHA-256 values were rechecked:
  `8b324a176d630d6cebf555214cface261b9056b0d65d121b2530af602bf87de1` and
  `cd835585f70c8d80071bf3526dc5941c02394533a484f481849a93f082e5dc57`.
  Their 16 message contents total 112,786 UTF-8 bytes; largest is 38,101 bytes.
  Byte counts are not tokenizer or internal-evaluation bounds.

Offline admission review of this packet:

| Condition | Required disposition | Current packet |
| --- | --- | --- |
| Missing/expired authority, mismatched account, input or config digest | No dispatch/write | Historical credential linkage unknown; future authority not issued. |
| Exact target config or retry-OFF readback absent | No write or inference | Blocked; semantic intent only. |
| Neither verified Free-only paid-usage bound nor combined paid-cost ceiling | No inference | Current Free/billing/log predicates need readback; generation price alone is insufficient. |
| Native log/verdict inaccessible, truncated or uncorrelated | Unavailable, never completed negative | Mapping feasibility unproven. |
| Read-only metadata envelope | No token/config modification or API retry | Observed policy form exited without save; no direct authenticated request made. |

This is a document/admission review, not a newly implemented live validator or proof
of Cloudflare behavior. Existing hypothetical mocks remain hypothetical.

### Offline packet self-check

A fresh no-network Python self-check validated the proposed packet as data only. It
asserted the published create-required fields, `guardrails.prompt == {"P1":"FLAG"}`,
an empty response guardrail map, non-negative cache/rate fields, 16 serial requests,
60-second per-request and 1,200-second total bounds, `stream:false`, zero client
retries/continuations, three log polls per case, and stop conditions for `403`,
`429`, ambiguous timeout, missing verdict and unknown cost. It also asserted that
`retry_max_attempts` is omitted rather than incorrectly serializing the published
minimum field as zero. The command exited 0 and printed the expected field/control
summary. This checks packet consistency only; it does not validate a live Cloudflare
readback or authorize a request.

## P2 outcome and P3 entry gate

Public research and approved current-metadata investigation are recorded. The
pre-Q3 permission mismatch was established for the selected token, and the two Read
grants were subsequently added and read back under Q3. Q4 proved current Gateway-list
access (HTTP 200, success true, zero results), then stopped on local validation.
After explicit Q4b approval and offline repair, subscriptions returned HTTP 200,
success true and one result. Current access to both endpoints is verified; historical
root cause and credential continuity remain unproven. The two one-time API allowances
are consumed; no further API/credential use is authorized. The final
exact trial packet remains **capability-blocked**, not live-ready, on target config,
retry behavior, native verdict feasibility and combined cost evidence. P3 additionally
requires explicit approvals for exact fixture labels/digest, Gateway create/change,
native log retention and data egress, inference and per-run call/token/time/cost
limits, and stop/rollback policy. Enforcement, export, runtime activation, and merge
remain independently OFF/unapproved.

The existing [label review draft](../../evals/test/fixtures/cloudflare_p1_shadow/labels.review.draft.json)
is still `draft_for_owner_review`, with `reviewed_by` and `decision_ref` null.
Its SHA-256 is `f022804002150805827c16bac9231afc0a34c0b2ea12e77a26ba2704b9731bfc`,
bound to [cases](../../evals/test/fixtures/cloudflare_p1_shadow/cases.json) SHA-256
`2cac53d286a9ca1496614c9a5f24af548efd35380b92bb6063299f106d10a186`.
It proposes eight injection-presence positives and eight controls (four of each per
VI/EN). Label acceptance would authorize those annotations only, not detector quality
acceptance or a live call. Historical-403 attribution is not an additional P3 gate
once current endpoint access is proven; configuration, observable verdict feasibility,
cost and the explicit run permissions above remain the actual frontier.

### October 17 refinement and next executable step

The [pinned public-source refresh](../research/issue-188-cloudflare-p1.md#2026-10-17-focused-refresh--bounded-capability-discovery)
refines the earlier blocker assessment. Exact P1 unit price/internal segment count,
machine-readable aggregate verdicts and all segment identifiers are not prerequisites
to a bounded capability-discovery canary. A verified Free-only billing/log route
can bound paid usage at USD 0, with shared quota depletion and unknown internal
count retained as limitations. Dashboard links to native Guardrails evaluations,
including passing evaluations, provide the documented discovery route. Neither
condition has been established on a newly configured target account/Gateway.

The smallest proposed execution is the existing `p1-vi-attack-1` and
`p1-vi-control-1`, in that order, within the same pinned fixture and 16-request total.
Use the existing model and envelope above, serial/no retry, at most 256 output tokens
and 60 seconds per request. Inspect at most three times per request through the
actual Dashboard log surface. These two calls discover the native observation
contract; they need not classify the expected labels correctly. Continue the
remaining 14 only if covered by the same explicit run authorization and usable
completion/correlation is demonstrated. Unsupported long-input coverage stays
unavailable. Do not write a speculative importer or silently reuse the Legacy API
for a Workers Logs cohort.

The concrete approval frontier is one bounded P3 packet covering the pinned labels,
dedicated authenticated Gateway, prompt P1 FLAG only, retry toggle OFF/readback,
cache bypass, billing preserved, synthetic message egress and native log retention,
credential use in memory, external call/time/output limits, shared quota risk and
stop policy. Any additional Gateway Run token permission must be named explicitly;
Q3's two Read grants do not authorize it. Do not create a key or broaden account
scope. No credential/header/raw response enters a local artifact. Retain only
sanitized native evaluation metadata in the separate supplementary report, under
the approved native-log policy. This paragraph proposes authority; it grants none.

At 2026-10-17 02:13 UTC, browser inventory exposed no previous Edge connection.
A direct navigation to `https://dash.cloudflare.com/` in the available in-app
browser reached **Sign in to Cloudflare** at `/login`. No credentials were read or
entered. Current plan, billing mode and log-cohort readback therefore cannot be
collected through that session. The owner can reconnect the previously authenticated
Edge browser or sign in directly in the opened Dashboard tab; no manual metadata
copy or token secret is required. Once access returns, collect only the approved
read-only facts before presenting any exact cloud mutation for approval.

Goal remains the full Issue #188 objective and is not complete. P2 investigation is
complete; P3 has no live authorization. P1 labels/quality, later phase decisions,
enforcement/export, merge and deployment retain their existing status.

### October 17 authenticated Dashboard follow-up

After the owner signed in and explicitly resumed this chat, read-only navigation
at approximately 06:08–06:10 UTC (13:08–13:10 Asia/Saigon) established these current
facts on the previously selected account. No form field was changed or saved.
The October 16 observation envelope remains immutable.

| Surface | Current observation | Limit |
| --- | --- | --- |
| Workers plans | Free marked Current plan; Workers AI 10,000 neurons/day and Workers Logs 200,000 events/day displayed in that plan table. | Shared limits, no reservation; no upgrade performed. |
| Workers AI usage | 78.11/10k neurons today; reset 00:00 UTC. | Point-in-time account usage, not attributable to #188; this follow-up sent no inference. |
| Gateway landing | Onboarding still offers automatic default creation and Create a custom gateway. | No existing target config inspected; historical first-Gateway/log cohort still unknown. |
| Credits | USD 0.00; no usage data and no invoices available. | No credits bought; does not independently establish fallback or auto-recharge behavior. |
| Unsaved create form | Collect Logs ON, capacity 100,000 with Delete oldest logs; cache OFF, rate limit OFF, spend limits OFF, Retry Requests OFF, authentication ON, Workers AI billing Standard billing. | Proposed defaults only; no Gateway exists from this action, no saved config digest or effective guardrail readback yet. The form exposes no TTL in the inspected logging section. |

The log-limit editor was opened only to inspect available controls, then cancelled
without editing or saving. No token page, secret, API client, payment action or
inference was used. The login blocker is resolved. Saved Gateway and guardrail
readback, actual billing/fallback behavior and native evaluation evidence must still
be established under the separate configuration/trial authority below.

### Consolidated P3 approval packet — proposed, not granted

This packet is the next decision under the existing Master, not a second plan.
It bundles setup and a finite synthetic trial to avoid approving each routine read
or offline repair separately. Its grant, if approved, expires after the first run
session or 24 hours after approval, whichever comes first; no automatic renewal.

1. **Labels and data:** accept the existing draft annotations for the pinned cases
   SHA-256 `2cac53d286a9ca1496614c9a5f24af548efd35380b92bb6063299f106d10a186`
   and label packet SHA-256
   `f022804002150805827c16bac9231afc0a34c0b2ea12e77a26ba2704b9731bfc`.
   Eight attack cases cover override, exfiltration, role spoof and indirect boundary;
   eight controls cover quoted attack, legitimate imperative, role words and long
   boundary (four of each class per VI/EN). Acceptance concerns annotations only.
   Permit only those synthetic envelopes to the selected Cloudflare account; no
   native capture, gold/reference answers, private data or arbitrary latest trace.
2. **Configuration:** create only `knora-issue188-p1-trial` through Dashboard if that
   ID is unused. Authentication ON, prompt P1 FLAG only, all other prompt categories
   and response checks ignored; DLP OFF; caching/retries/rate limiting OFF; no routes,
   provider fallback or stored third-party credentials. Standard Workers AI billing;
   no Unified Billing, billing fallback, credits, recharge, subscription or paid
   upgrade. Inspect saved readback before dispatch; stop if these controls cannot
   be established. No token grant, token creation or token roll is in this packet.
3. **Native logs:** permit Cloudflare to retain the synthetic prompts, disposable
   generation responses and evaluation payloads in this dedicated Gateway only.
   The observed create form offers a 100,000-record limit with oldest-record eviction,
   and no inspected TTL; approval must accept that native retention can persist until
   deletion. Preserve the service's actual free log retention if it is shorter.
   No Langfuse/OTEL/Logpush/export or local raw payload copy. Inspect only the trial's
   exact linked logs, at most three inspections per case. Retain local sanitized IDs,
   digests, statuses and verdict metadata in the separate supplementary report.
4. **Credential and transport:** permit the bounded local program to load only the
   primary checkout's existing account/token settings in memory and send the token
   only over TLS to `api.cloudflare.com`, using the documented Workers AI REST path
   plus the exact trial Gateway ID. No secret/header/fingerprint output, redirect,
   retry, pagination, token verification or additional authenticated metadata GET.
   Q4/Q4b are not reused. If existing permissions fail, stop; do not add Gateway Run.
5. **Execution and cost:** at most 16 external generation POSTs in one serial run,
   `@cf/openai/gpt-oss-20b`, stream false, maximum 256 output tokens, 60 seconds per
   request and 20 minutes total. No tools, continuations or retries. First two are
   `p1-vi-attack-1` then `p1-vi-control-1`; continue the remaining 14 only after usable
   native completion/correlation and FLAG-only routing are proven. Preserve FP/FN.
   USD 0 paid usage only, contingent on fresh Free/Standard/no-fallback readback;
   accept potential depletion of shared free quota and unknown internal P1 call
   count. No paid exploratory call to discover a missing feature or price.
6. **Implementation and stops:** allow the minimal P3 transport/native mapping and
   offline tests within existing P1 adapter/test/report paths, using installed
   dependencies only. Keep the CLI offline by default and preserve immutable reports.
   Stop on configuration/billing drift, 403/429, cache hit, missing/truncated or
   uncorrelated evidence, ambiguous send state, timeout, unsupported native verdict,
   or data mismatch. A possibly sent request consumes its allowance. No automatic
   replay or alternate provider. On stop, cease dispatch; disable trial guardrails
   through the same Dashboard configuration authority if configured, retain evidence
   and report the readback. No cloud deletion is preauthorized by this packet.

This packet authorizes nothing until the owner approves it. Read-only preparation
does not establish detector quality. Runtime activation, enforcement/export,
later threat-group decisions, merge/deploy and final #188 acceptance remain separate.

### P3 approval and staged execution — October 17

The owner replied **"tôi duyệt"** to the complete consolidated packet in this chat
on October 17 (approval recorded at approximately 08:06 UTC). This grants exactly
that packet; earlier proposed/not-granted wording above is its preserved proposal.
Labels are accepted for the two pinned digests, not detector quality. No additional
token grants, API GETs, enforcement/export, runtime or merge authority follows.
The first run session ends after 20 minutes from its first dispatch, or on a named
stop. A conservative final expiry is 2026-10-18 08:00 UTC; no restart/replay.

Dashboard creation succeeded with exact ID `knora-issue188-p1-trial`. Saved readback:
authentication ON; logs ON/100,000/delete-oldest; cache/rate limits/retries OFF;
Standard Workers AI billing; log classification OFF; no OTEL destination; dynamic
route onboarding shows no configured route. Guardrails was enabled, then saved with
only prompt P1 Flag and every other prompt/response category Ignore. The collapsed
saved summary reads `Prompt hazard categories Flag Prompt Injection / Jailbreaks`;
DLP remains OFF. Enabling Guardrails initially supplied all-category Flag defaults;
these were replaced before any inference. No Block action or provider key was set.
The saved semantic Dashboard observation and its digest are in
`evals/reports/cloudflare_p1_shadow/p3-trial-001/configuration.json` and
`configuration.sha256`; this is an agent observation, not an API export.

Immediately before dispatch, Workers AI showed 78.11/10k neurons and Workers plans
still marked Free as Current plan. Standard billing was read back from the saved
Gateway; the billing dropdown offered Unified and Standard only, with Standard
selected. No Unified Billing/fallback or route was configured. No credit, upgrade,
policy change, token secret output or authenticated metadata GET was performed.

The P3 transport is staged to only the first attack canary until its actual native
evaluation is inspected. It reuses the exact offline envelope, locks fixture digest,
target/model/expiry, reserves an immutable attempt before send, bypasses cache,
does not follow redirects/retry, caps response bytes and applies a 59-second async
deadline. Only sanitized transport metadata is written; responses/headers/credentials
are discarded. Its default command performs no credential read or network. The
existing offline P1 CLI is unchanged; native result mapping remains unsupported
until observed evidence can justify it. Six new tests went RED on the absent module,
then GREEN; the P1/Secrets/transport subset is 62 passed, Ruff check/format passed.

**Stopped attempt:** At 08:12:20 UTC on October 17, the first canary was durably
reserved, then the program returned `transport_or_response_error`, with HTTP status,
success and native log ID all null. The reservation conservatively consumes one
attempt; it does not prove that a POST reached Cloudflare. Original diagnostics
collapsed credential/parser and HTTP errors, so root cause and actual send state
are unknown. Do not call this another 403, a detector error or a completed negative.
No retry, second canary, additional credential load or authenticated API GET followed.

Guardrails was turned OFF under the approved stop policy and saved readback verified
OFF, with DLP still OFF. Gateway/log collection was retained; nothing was deleted.
The dedicated trial Logs page resolved to the Workers Logs query surface, showing
the Free 200K events/day/sampling notice and No events found on the first inspection.
This establishes the current observation surface, not historical account cohort or
proof of zero provider receipt. Missing events can be delayed or sampled.
One subsequent explicit Refresh, after the UI's stated two-minute delay window,
also showed no events. Exactly two native-log inspections were used; no event was
opened, no additional endpoint/request was tested and no inference was replayed.

Immutable results are in `evals/reports/cloudflare_p1_shadow/p3-trial-001/`:
`p1-vi-attack-1.reserved.json`, `p1-vi-attack-1.transport.json`, `closed.json` and
`supplementary-stopped-001.json`. The v2 supplement records 16 reviewed selections,
one unknown, 15 unavailable/not attempted, zero evaluable/native completed results,
one reserved attempt and zero HTTP responses. Actual external request count and
observed cost remain unknown; external request upper bound is one. TP/FP/TN/FN are
all zero with undefined precision/recall/FPR; no quality claim follows.

Offline investigation compared the prior working Q4 checker and the new transport.
The account hash matches the selected Dashboard identity. The prior checker uses
explicit UTF-8-sig dotenv parsing and stdlib TLS; the new code uses default text
decoding and HTTPX. Those differences are hypotheses, not a verified cause; the
original error was not retained precisely enough to distinguish them without new
credential/network authority. No speculative provider/permission/billing change
was made. Safe diagnostics were repaired with two further RED→GREEN tests: future
failures report only an allowlisted stage/class, never exception text, credentials
or headers. The current focused suite is **64 passed**; Ruff check/format passed.
This verifies diagnostic behavior, not a fix of the original live failure.

The live session is closed on its named stop; the remaining 15 are not a reusable
budget. Further diagnosis needing credentials or a renewed run needs a new concrete
scope. Settled label acceptance and Q2 reads do not need repeating. P3 quality and
full Issue #188 remain incomplete, with runtime/enforcement/export/merge OFF.

### Renewed P3 session — trial-002, October 17

The owner explicitly approved the renewed packet in the current chat. It permits
credential binding diagnosis in memory, verified local repairs and one new finite
16-POST session under the same fixture, Gateway, model, logging and zero-paid-usage
limits. It accepts possible duplication of trial-001's indeterminate first canary.
No extra authenticated GET, token grant, billing change, export, enforcement,
runtime activation, merge or deployment was authorized. The new approval is recorded
in `p3-trial-002/approval.json`; its conservative outer expiry is October 18 11:10 UTC.

**Verified local fault and repair:** A credential-only check reproduced
`UnicodeDecodeError` at `credential_loading`, with zero network requests. This
Python 3.13 host defaults to cp1252; the loader omitted an encoding. A synthetic
UTF-8/BOM regression failed on the same decode path before the one-line UTF-8-sig
repair, then passed. The repaired in-memory check returned only binding-valid=true;
no secret, header, token fingerprint or exception message was output. This proves
the current loader defect; trial-001 remains indeterminate because its original
diagnostics did not identify the failed stage. Do not rewrite that historical record.

**Fresh readback:** Workers Free remained Current plan, usage 78.11/10k neurons,
credits USD 0, Standard Workers AI billing. Gateway authentication/logging remained
ON, logs 100,000/delete-oldest, caching/retries/rate limits OFF, no OTEL destination.
Re-enabling Guardrails reset categories to all-Flag defaults; before dispatch these
were replaced and saved as prompt P1 Flag only, every other prompt/response category
Ignore, DLP OFF. `configuration.json` is a sanitized agent Dashboard observation,
not an API export; its SHA-256 is
`40f6ce5f5ea1522492afb138b3b13c13bf54e54a9fa55ec943a5b49b7bd9ce18`.

**Execution:** First dispatch was October 17 11:17:07 UTC. The first attack and
quoted-control canaries each returned HTTP 200/success=true with a native log ID.
After the UI's two-minute delay window, exact request IDs, case IDs and input
digests matched the selected native logs; both explicitly showed Guardrails flagged
and `guardrails.prompt.P1 = FLAG`. The benign canary was not required to predict TN.
These correlated positive findings admitted the remaining 14 cases without tuning
or requiring an expected class. All 16 serial POSTs returned HTTP 200/success=true
and native log IDs; last dispatch began 11:28:58 UTC. There were no retries,
continuations, redirects, additional authenticated GETs or provider changes.

Dispatch authority is exhausted at 16/16. Guardrails was turned OFF and saved
readback verified OFF, DLP OFF; the Gateway and native logs were retained. The
20-minute review window ended at 11:37:07 UTC. All 16 native logs were inspected
and correlated before that deadline. The first canary used two inspection rounds,
the control and remaining cases one each; opening the same selected event's Details
and Raw JSON is part of that inspection, not an additional poll. Only safe scalar
IDs, digests, outcomes, flags, token counts and estimates were retained locally.
No native prompt/response payload was exported or copied into a local report.

**Findings:** Eight explicit P1 flags comprise six attack cases and two controls
(`p1-vi-control-1`, `p1-en-control-1`, both quoted-attack controls). Eight other logs
show Success without an explicit negative evaluation. Those eight remain
unavailable, including VI attack-2/attack-4; they are not FN/TN. The observed schema
does not expose successful negative evaluations or completion of every internal
segment. An explicit positive finding supports detected presence; it does not prove
full-input clearance or segmentation coverage. No automatic native-negative importer
was added, and no model answer was substituted for a detector result.

The immutable `p3-trial-002/supplementary-001.json` reuses existing metric/population
helpers and records 16 selected/reviewed/attempted/observed, 8 evaluable explicit
positive findings, 8 unavailable, 0 clear, 6 TP and 2 FP. Precision among explicit
flags is 0.75. Existing helper recall/FPR values are conditional on the eight
evaluable rows only; **full-population recall and FPR are null** and cannot be
reported as 100%. Group/subgroup counts retain missing outcomes. Quality acceptance,
Detection Completed and Protection Enabled remain false. Supplement file SHA-256:
`1ec83820a6f33a0bbb876c00d32a5918f6553f49e84fe2f9ae0725e39d569130`.

Parent-log cost estimates sum to approximately USD 0.00627019. They are not an
invoice, observed paid charge or combined internal-P1 price. The approved paid bound
remained USD 0 under the freshly verified Free/Standard route; actual combined cost
and added detector latency are unknown. No billing or quota API was called afterward.

Offline tests cover the Unicode repair, second-canary ordering, closed/expired
session rejection, native-canary binding, no replay, bounded response handling and
sanitized failures. The original P1 offline CLI and shared helpers remain unchanged.
Native-negative feasibility and owner disposition of the false positives are the
next substantive P3 decisions; a new live session is not implied. P4 exact follow-up
inputs/environment and P5/P6 entity/taxonomy decisions remain separately gated by
the Master. Full Issue #188 is not complete.

### Offline review closure — trial-002

Independent review found that a future HTTP 200/success response without a valid
`cf-aig-log-id` could permit the next dispatch. Missing and invalid-header regression
cases both failed before the repair; continuation now requires a valid native ID.
Both cases also verify rejection before the second canary. This defect was not
triggered in trial-002: all 16 saved response IDs correlate with native evidence.
The reviewer rechecked the repair and ran the focused suite: 14 passed, finding
resolved. No further live request or credential read was made for this repair.

Fresh local verification on the dirty worktree: 70 P1/Secrets/transport tests passed;
Ruff format/check/lint passed (393 files), default trial CLI reports OFFLINE, and
`git diff --check` passed with the existing LF/CRLF warning on the P1 note. Full
pytest collected 2,014 items but stopped on two missing optional dependencies,
`deepeval` and `ragas`; no packages were installed and no full-suite success is
claimed. Compose/runtime checks were not repeated for this change. Exact-head
CI run `38787009474` remains SUCCESS for `4f1a672`, not the uncommitted P2/P3 work.
PR #199 remains Draft/Open at `bd5f288`; PR #205 remains Draft/Open at `4f1a672`,
stacked on #199. Nothing was committed, pushed, merged or deployed.

`p3-trial-002/review-completed-001.json` binds the finished review to the immutable
supplement. `closed.json` retains its historical dispatch-close snapshot, including
the then-pending native review; it is not overwritten to describe later work.

### Next frontier — proposed P4 offline envelope, not approved

**P3 recommendation for owner disposition:** retain Cloudflare Gateway P1 as an
experimental, unaccepted candidate. Preserve the two quoted-control false positives
and eight unavailable outcomes. Require a usable completed-negative/full-input
observation contract before P1 quality qualification or runtime adoption. Do not
change labels, thresholds or category actions to improve this pilot's numbers.
No renewed live run is proposed. P4 is independent of P1 quality acceptance, but
the Master's P4 contract requires approval of exact input and environment.

The smallest P4 follow-up reuses PR #199 unchanged, with no new cases or installs:

| Item | Exact proposed bound |
| --- | --- |
| Code | Current branch's existing `evals/runners/run_security_shadow.py` and `evals/scorers/security_shadow.py`; PR #199 base `bd5f288da7822d81e99f17f97567ec5c3129d7bb`; record current code hashes before any run. No scanner/threshold/checksum/split-key behavior change. |
| Environment | `C:/Developer/Projects/knora-agent-worktree/issue-188-security-shadow/.venv/Scripts/python.exe`; read-only metadata verified Python 3.12.15, guardrails-ai 0.11.0, guardrails-ai-secrets-present 0.1.0, detect-secrets 1.5.0. No package/model install, dependency or environment mutation. |
| Reviewed controls | Original `C:/Developer/Projects/knora-agent-worktree/issue-188-security-shadow/evals/test/fixtures/security_shadow/cases.json`, SHA-256 `09d64242c694abee6017723b73c1dabd468f6125a0816c003337e05c40954d4a`, all eight cases and existing exact-digest owner review. No new labels. |
| Selected saved output | `C:/Developer/Projects/knora-agent-worktree/issue-153-pdf-baseline/evals/reports/pdf_retrieval_v3_v1/baseline-b-layout-v2/captures/case-pdf-v3-001-attempt-1.json`, verified byte SHA-256 `6daa50d8876efa79663ae433c7a0b2b8028a6f0091a8602d4fdd080dc7224729`; only saved output is scanned, unreviewed for security metrics. Missing generation evidence remains unavailable. Retain native IDs and original CITATION_STRUCTURAL_ERROR; no trace lookup or re-answer. |
| Execution | At most ten local detector invocations: eight existing fixtures, one saved output, one existing real integration test. At most 30 seconds each, five minutes total, no retries. Run the existing 16 pure tests and one isolated integration test. Stop on digest/package drift, unexpected egress/subprocess behavior, dependency failure, timeout or unsafe result. Python audit guard is not an OS firewall. |
| New artifacts | Only additive safe reports under `evals/reports/security_shadow/p4-qualification-001/` and progress in this evidence note/Master. Preserve `pilot-003.json` and `pdf-smoke-002.json` bytes. No raw text, matches, credential access, cloud request, config/runtime activation, enforcement/export, merge or deployment. |
| Interpretation | Compare presence and known split-key FN/checksum FP without suppression/concatenation. Saved-output result is not leak authorization or application-security acceptance. Present residual gaps for owner review; no automatic P4 PASS. |

**Byte-identity check:** The current P1 worktree's fixture has SHA-256
`a44753332dd670be947df84804b656e8e88ac8af93bd679d10cc79b3e37dcf64`,
which does not match the old review. Its Git blob SHA-256 is
`c21ec0dfa036a3378ec0a411b93031ab4630cc7aee05c46c8934f8983e6a4e28`;
neither is substituted for the approved original bytes. The original Secrets
worktree still contains the exact reviewed `09d64242...` fixture. Use that selected
file directly after approval; do not normalize/rewrite fixtures or historical
reports to manufacture a match. This preparation read only metadata/digests and
the already-selected artifacts; it did not execute the detector.

### Owner disposition and P4 approval — October 17

The owner answered Q1: **retain Cloudflare P1 experimental/unaccepted**. The two
quoted-control false positives and eight unavailable outcomes remain intact;
completed-negative/coverage evidence is required before qualification or runtime
adoption. This settles the P3 disposition question without accepting P1 quality
or authorizing another live run.

The owner answered Q2: **approve exactly the P4 offline packet above**. This grants
the selected original eight-case fixture and saved output, existing pinned isolated
environment, sixteen pure tests, at most ten local detector invocations including
one real integration, thirty seconds each and five minutes total without retries.
It permits new safe reports and these progress documents only. No algorithm or
label change, installation, credential/cloud access, runtime/enforcement/export,
commit/merge/deploy permission follows. The proposed/not-approved heading above is
the preserved proposal; this paragraph records its subsequent approval.

### P4 offline qualification evidence — October 17

The exact approved finite run completed at 11:45:21 UTC with **10 local detector
invocations in 54.5 seconds**, no retries, no timeout/error/unknown result, no
credential read or cloud request. Every worker recorded zero blocked network
attempts. The existing sixteen pure tests passed before dispatch; the single real
integration test passed, including temporary-directory cleanup. No scanner code,
labels, package pins, environment or algorithm was changed. All ten allowances
are consumed; this run cannot be restarted or expanded automatically.

Artifacts are additive under `evals/reports/security_shadow/p4-qualification-001/`:
approval/preflight with actual input/review/code/environment hashes; ten immutable
reservation/result pairs; `fixtures-001.json`; `saved-output-001.json`; integration
JUnit; and `completed.json`. The original Secrets fixture was used directly with
its matching review. Actual code bytes matched PR #199 after Git line-ending
comparison; both current raw code hashes are recorded for reproducibility.

| Population | Result | Interpretation |
| --- | --- | --- |
| Eight reviewed synthetic fixtures | 3 TP, 1 FN, 1 FP, 3 TN; recall 0.75, FPR 0.25, precision 0.75 | The same split-key miss and public-checksum false positive remain. This is development presence evidence, not held-out quality or unauthorized-disclosure acceptance. |
| Exact selected saved output | Completed local `clear`, unreviewed security label | The detector emitted no finding for this text. It is not a reviewed TN, proof of no secret, repaired application result or accepted leak policy. |
| Same capture's generation evidence | Unavailable, no detector invocation | The capture lacks exact evidence. Do not reconstruct evidence, find another trace or re-answer. |

The saved report retains native run/attempt/trace/workspace/case/source identities,
the original `CITATION_STRUCTURAL_ERROR` and other failure provenance. Its two
scope units are unreviewed with zero evaluable metrics; only the output text was
scanned. Four historical report files (pilot/smoke in both worktrees) were hashed
before and after and remain byte-identical. The selected fixture and capture also
retain their approved hashes. New reports contain no raw input, answer, match or
credential text. Python-level audit blocking is not an OS firewall guarantee.

File SHA-256 bindings:

- `fixtures-001.json`: `76adc307b22b9493e59dbe10aae3e4e0dc045e7abf8762f1d705e86b61ad5ff9`.
- `saved-output-001.json`: `52a7d0f482ceb1290f3cac7313c4ba1ef20fc6aade29a938a0529c3085cc0f90`.
- `completed.json`: `7aaf8bc239243556cb913987b08a6422029d2c381f8c6110bd5c7a4bb9e02b72`.

Independent read-only review found no actionable findings. Standard-library checks
verified hashes, report digests, serial count/time bounds, metrics/populations,
native identities, JUnit and absence of copied raw content; the reviewer did not
rerun the detector or tests. A coordinator artifact self-check also passed. The
broader pytest dependency limitation recorded above remains; no fresh broad-suite
success is claimed. No live configuration changed during P4, so the P3 OFF readback
remains the last observed cloud state, not a new readback.

**Quality disposition pending:** Recommend retaining the Secrets candidate as
experimental/unaccepted with the split-key/checksum limits. A remediation proposal
requires a separately reviewed selection and specific algorithm decision; do not
silently concatenate whitespace or suppress checksum-shaped strings. Execution
success does not settle that decision. Detection Completed and Protection Enabled
remain false; P7 runtime adoption is not authorized.

### Proposed next offline research envelope — P5/P6 sources only, not approved

To advance the remaining threat groups without another live trial, propose one
finite research bundle in the existing Master. Section 6 explicitly permits early
P5/P6 source research when authorized; implementation and live progression keep
their existing dependencies.

- **Inputs and sources:** Public primary Cloudflare documentation through Context7
  and official documentation pages only. Use current local contracts/research for
  comparison; do not open another saved capture or account/token surface.
- **PII questions:** Establish DLP's entity/profile/country/language coverage, access
  and plan requirements, prompt versus actual response coverage, saved-output replay
  meaning, correlation/completed-negative evidence, retention and price/accounting.
  Map candidate email, phone, government identifier including VN CCCD, personal name,
  address and medical-record identifier coverage. These are research targets, not
  an accepted product entity policy; unsupported targets stay explicit gaps.
- **Dangerous Output questions:** Map the documented S1–S13 categories and missing
  categories to actual hosted API/Gateway semantics, VI/EN limits, saved-output versus
  new-response scanning, completed-negative evidence, costs and logs. Draft the
  distinction between actionable harmful instruction and legitimate quoted security,
  medical/research material; the owner still decides the final taxonomy/exceptions.
- **Deliverables/files:** One cited feasibility matrix and a concrete decision packet
  in `docs/research/issue-188-cloudflare-pii-dangerous-output.md`; progress links in
  this evidence note and the existing Master. Identify facts that public sources
  cannot establish. State feasible/unsupported/unknown, never invent API contracts.
- **Boundaries:** Research/documentation only. No new fixture population or labels,
  adapter/runtime behavior, dependency install, model import, credential/account read,
  authenticated API, inference, Gateway/DLP/billing/log mutation, export/enforcement,
  commit/push/merge/deploy. No quality acceptance or P5a/P6a technical-completion
  claim merely from finishing this research subset. Subsequent implementation/data/
  live scopes require their concrete reviewed packet.

### Owner P4 disposition and P5/P6 research approval — October 17

The owner retained Secrets **experimental/unaccepted**, preserving the split-key FN
and checksum FP, unchanged algorithm/reports and no runtime adoption. P4's bounded
execution/evidence work is complete; this decision is not security-quality acceptance.
The owner also approved exactly the P5/P6 source-only research envelope above.
Public primary-source investigation and its one cited research note may proceed;
entity/taxonomy policy, fixtures, adapter code, live/config/data/budget and runtime
decisions remain outside this grant. No local detector invocation or cloud request
is authorized by that research approval.

### P5/P6 source-only research completed — October 17

The approved research subset is complete in
[Cloudflare PII and Dangerous Output source research](../research/issue-188-cloudflare-pii-dangerous-output.md).
Context7-first queries were followed to the official documentation/model catalog/
SDK sources, with 22 source groups recorded. No account/credential access, fixture,
label, code, model/detector execution, configuration or paid activity occurred.

Key results for the next decisions:

- DLP scan pricing does not establish full PII entitlement. Accounts without a
  DLP-including subscription are limited to Financial Information and the national
  identifier profile. The current account's Zero Trust/DLP entitlement is unverified;
  Workers Free is a different fact. PII Record requires three distinct nearby
  entries. The public inventory does not establish VN CCCD, generic VN phone/address
  or generic medical-record-ID coverage. Unsupported formats cannot become TN.
- Gateway request replay, actual new-response scanning and manual DLP Test scan
  are distinct. Test scan is configuration validation, not an established automated
  API for this evaluation. Missing DLP headers/flags remain insufficient negative
  evidence. Actual selected profiles, entries and settings must be known first.
- Gateway documents S1–S13, explicitly excludes S14 and does not list Vietnamese.
  The direct hosted Llama Guard model has a separate documented input/output schema;
  its descriptive S1–S14 field is not runtime proof. Terminal-assistant targeting,
  contextual effects, truncation and completed-negative evidence still need future
  canaries under separate authority. No saved answer was submitted or regenerated.
- The candidate rubric separates presence from unauthorized disclosure, and harmful
  assistance from legitimate quoted/medical/security/research use. These remain
  proposals; no Knora entity/taxonomy/benign-exception policy was accepted here.

Independent review found no confirmed material contract/scope issue. Three public
source spot-checks confirmed the PII Record rule, Gateway categories/languages and
direct-model roles/result schema. A cached-source price discrepancy was resolved
by fresh unauthenticated no-cache reads of the official model catalog and Workers
AI price table: both show USD 0.484/M input, the table shows USD 0.030/M output.
No inference occurred. Mutable source URLs and unknown internal calls prevent an
executable cost guarantee. This finishes the research bundle, **not** P5a/P6a
implementation, quality qualification, or the full Issue #188 Goal.

### Next decision packet — P5/P6 offline preparation, not approved

These two branches are independently reviewable. They do not reopen the settled
P1/Secrets experimental dispositions or grant provider calls.

**P5 proposed target and preparation:** Retain six desired entity families — email,
phone, government identifier including VN CCCD, personal name, address, and medical
record identifier — with VI/EN and country/format explicitly separate. This is a
required-target proposal, not a claim Cloudflare covers them. Do not silently reduce
the target list to the account's free profiles. Entity presence/type and authorized/
denied disclosure remain separate proposed annotations.

If approved, perform one read-only entitlement check in the already selected
Cloudflare account: at most three Dashboard page visits within fifteen minutes,
limited to Zero Trust/DLP plan and available profile/entry metadata plus the existing
trial Gateway's displayed DLP state. No token/billing editor, payload/log review,
Test scan, enable toggle, onboarding, profile edit, API/CLI request or secret access.
Stop on login/access/onboarding requirements or unavailable metadata; record the
specific unknown instead of enabling a feature. This scope permits normal Dashboard
reads only, not new agent-constructed authenticated requests.

Then draft at most **30 synthetic supplementary cases** (up to 24 paired entity/
disclosure-context rows plus six benign controls), without reading another saved
capture. Reuse the existing review/digest/identity conventions; labels remain
draft/unaccepted. Record unsupported types rather than treating them as clear.
Allowed new paths are `evals/test/fixtures/cloudflare_pii_shadow/cases.draft.json`
and `labels.review.draft.json`, plus preparation/coverage updates in the research
note, this evidence note and existing Master. No adapter/runtime code is included.

**P6 proposed taxonomy and preparation:** Use S1–S13 as separately reported
observational category targets, with VI exploratory/unqualified and S14 outside
the Gateway claim. Select direct hosted Llama Guard as a **candidate to investigate
for saved-output classification**, keeping it distinct from Gateway response checks.
Do not adopt it until target-sensitive canaries prove usable semantics.

Draft explicit Knora hazard/benign-context rules and at most **52 synthetic
supplementary cases** across VI/EN, including paired benign medical/educational,
critical quoted security/research, supportive/preventive and neutral civic controls,
and target-sensitive canary representations. Quotation is not a blanket exemption
for actionable harmful assistance; authorized PII is not automatically a policy
violation; S7 is not an entity detector. No harmful explicit material is needed.
Category names alone do not settle medical/legal/financial advice, IP, privacy,
sexual-education or election policy; unresolved examples stay marked for owner
review. No labels become accepted by generating a draft.

Allowed new paths are `evals/test/fixtures/cloudflare_dangerous_output/cases.draft.json`
and `labels.review.draft.json`, plus the same research/evidence/Master updates. This
is data/rubric/canary preparation only, not adapter code or a moderation request.

**Shared next-scope bounds:** No package/model installation/import, local detector,
credential read, new raw capture/latest trace, gold/canonical report mutation,
re-answer, provider/API request, DLP Test scan, cloud config/billing/log mutation,
export/enforcement/runtime, commit/push/merge/deploy. Draft artifact identities are
synthetic and remain distinct from native run/attempt/trace/workspace identities.
Local JSON/digest/schema self-checks do not dispatch detectors. Present exact bytes,
counts, proposed annotations, remaining provider/coverage gaps and a concrete future
code/canary packet after preparation; neither live permission nor quality acceptance
is implicit. Owner may retain or explicitly narrow the proposed entity/taxonomy
scope before any such preparation.

### P5/P6 preparation approved and completed — October 17

Owner answered both frontier questions in this chat: **six PII families and exact
P5 packet approved; S1–S13/direct-hosted candidate direction and exact P6 packet
approved**. The preceding proposed packet is retained as the approved scope record.
This changes preparation authority only; all labels still require item-level review.

The Dashboard check is closed after three conservatively counted views within the
15-minute limit: selected account home, DLP profiles, and the identifier-profile
detail pane. The authenticated UI displayed two predefined profiles (Financial
Information; Social Security, Insurance, Tax, and Identifier Numbers), each with
**0 detection entries enabled**; Create profile disabled. Identifier profile ID
`d658f520-6ecb-4a34-a725-ba37243c2d28` showed Enabled None and a disabled-entry list
without VN CCCD. The [research checkpoint](../research/issue-188-cloudflare-pii-dangerous-output.md#approved-preparation-checkpoint--october-17)
records the actual entry names and observation limits. Precise plan, entry UUIDs,
Financial settings, thresholds and current trial Gateway DLP state remain unknown.
No config, onboarding, Test scan, API/CLI, secret, billing editor or payload/log was
accessed. This read does not renew prior OFF proof or prove all account capabilities.
The finite metadata check is consumed; do not start another view automatically.

| Draft artifact | Exact raw-byte SHA-256 |
| --- | --- |
| [P5 cases](../../evals/test/fixtures/cloudflare_pii_shadow/cases.draft.json) | `83f7a2d7e6d9ecf916340f54f5cf9e2e66b88d72487e6c0d0cf0e0dc38e7eac5` |
| [P5 review](../../evals/test/fixtures/cloudflare_pii_shadow/labels.review.draft.json) | `ab9bb7e649aa7bfa839a96d9e0db8df289ebf6e4ae4f66cb939335e2f1b13e92` |
| [P6 cases](../../evals/test/fixtures/cloudflare_dangerous_output/cases.draft.json) | `69ca4a1b08a82f2b7ded1910eb46eb4f3413553175baaf9c399bd86a89684b18` |
| [P6 review](../../evals/test/fixtures/cloudflare_dangerous_output/labels.review.draft.json) | `74492e6d50cd9de5e4eb63465c8de8a823c36cb36b7062c619a3498dfdab00fc` |

P5: 30 cases (15 VI/15 EN), 24 same-output authorization-pair rows plus six controls.
Proposed presence 24 positive/6 negative; unauthorized disclosure 12 positive/18
negative. Invalid VN/US ID shapes, invalid VN phone and invented addresses are marked
format-only probes, not realistic valid-entity qualification. Generic MRNs and all
six required families stay explicit even if the provider cannot cover them.

P6: 52 cases (26 VI/26 EN), four per S1–S13. Proposed labels: 8 positive, 30 negative,
14 unresolved policy probes; **every** label awaits owner review. S3/S4 have only
protective controls, no harmful positive. S5/S6/S7/S8/S10/S11/S12 risk probes require
adjudication; meta-description, fictional subjects and education are not automatically
hazardous. Four S2 rows provide proposed neutral-user/risky-assistant and risky-user/
safe-assistant canaries. They are weak high-level probes, not proven discriminators.
No method, explicit exploitative content or real personal record was constructed.

Both review sidecars have null reviewer/decision reference, false metrics eligibility,
and the exact fixture digest. Synthetic identities are separate from native captures;
no additional saved output, gold/reference material, trace or generation evidence was
selected. No code/model import, detector, provider request, package/Git mutation or
runtime/export/enforcement change occurred during this preparation.

Local PowerShell JSON/digest self-checks passed: 30/52 counts, unique case IDs, exact
review populations and raw digests, VI/EN, null native IDs and unselected evidence;
all 12 P5 pairs preserve output and change only authority; all 52 P6 representations
end with the exact selected output as assistant, four rows/category and four canary
rows. These check artifact consistency only. They are not detector tests or quality
evidence. `git diff --check` passed with the existing LF/CRLF advisory in P1 notes.

### Next code/canary decision packet — proposed, not approved

**P5 candidate gate:** Current Cloudflare evidence does not establish coverage of
the required six families. Do not enable entries, buy DLP, invent a Test scan API, write a speculative
PII adapter or silently narrow scope. Recommended next investigation is a separately
approved **public-source-only alternative-candidate comparison** of at most three
hosted services for all six families, VI/EN, valid synthetic formats, direct
saved-text classification, completed-negative
evidence, retention and bounded costs. This may research other cloud services but
does not grant an account, upload, package/model or request to any service. Keep
Cloudflare PII research-only/unqualified while this gap is unresolved. Draft P5 labels
must be reviewed or revised with exact new digests before any quality trial.

**P6 proposed offline code envelope:** After owner disposition of the draft rubric,
the owner may explicitly defer all item-label acceptance and authorize only syntax/
mapping preparation. Implement only a pure payload/verdict adapter at
`evals/scorers/cloudflare_dangerous_output.py` and focused
`evals/test/test_cloudflare_dangerous_output.py`, reusing the existing supplementary
observation conventions. No HTTP client/dispatch, credential/account read, model
import or runner is included. It must preserve selected assistant bytes; admit only
the documented user/assistant roles; validate complete, correlated native results;
keep missing/contradictory/malformed/truncated/unknown-category outputs unavailable;
and keep Gateway, direct classifier and output-replay-as-request surfaces distinct.
For the first mapping version, validate the documented object-result branch only;
string responses remain unavailable until an exact grammar is proven and reviewed.
Parsed safe/unsafe values are unqualified observations, including positives; neither
becomes completed detection or a metric until separate target/coverage/completion
evidence is accepted. Mocks can verify mapping, never provider targeting or quality.
Do not generalize a new transport/base class, modify runtime/canonical reports or
accept draft labels.
This is a reviewable future scope, not authorization to write those files now.

**P6 proposed future canary shape:** Use the four exact S2 draft rows, beginning with
the two EN rows; VI only after EN demonstrates useful target sensitivity. At most
four serial classifier POSTs, no answer generation, retries, fallback, GET/pagination
or other cases. Freeze reviewed labels/fixture digests and exact messages, requested
model/version/format/output cap, input-token bound, credential/account authority,
remaining quota/paid ceiling, native completion/correlation and retention before
asking to execute. The current packet deliberately has **no executable live grant**:
these account/cost/target prerequisites and review remain unresolved. Stop after an
error, ambiguous send, missing correlation/completion, truncation or failed target
discrimination; no implied renewal. Gateway config/Guardrails remain untouched.

Independent static review found no actionable findings in the completed preparation:
counts, digests, draft state, identities, authorization pairs, target representations
and canaries matched the records. The reviewer recommended making unqualified
positive and negative parsing explicit in the future packet; that clarification was
added. No detector, model, network, account or credential check was used for review.
Thirty-eight local Markdown links resolved; three recorded P4 artifact digests were
also checked unchanged. Provider feasibility/quality and full CI were not rechecked.

Next frontier is the P5 gap/alternative-research disposition and P6 rubric/code
preparation decision. Full P5a/P6a, live qualification, P7 runtime and final #188
acceptance remain incomplete. P1 and Secrets remain experimental/unaccepted.

### Alternative PII research and P6 pure mapper approved — October 17

Owner approved both new branches in this chat: retain Cloudflare PII research-only/
unqualified and compare at most three hosted alternatives using official public
sources/Context7; implement only the two-file P6 pure mapper/test envelope while
deferring all item-label acceptance. The prior proposed packet is now its approval
record for those two offline branches. Its four-POST future canary is still proposed,
not authorized. No account/credential/cloud/execution allowance was renewed.

The P6 mapper is at
[`evals/scorers/cloudflare_dangerous_output.py`](../../evals/scorers/cloudflare_dangerous_output.py),
with pure tests at
[`evals/test/test_cloudflare_dangerous_output.py`](../../evals/test/test_cloudflare_dangerous_output.py).
There are no production callers, HTTP transport, CLI/runner, file/credential reads,
model/scanner imports or report writes. The builder returns only documented
user/assistant messages, `max_tokens: 256` and `response_format: json_object`; it
requires the exact selected terminal assistant output, preserves Unicode/order/
whitespace/long text, copies messages and rejects extra metadata or invalid roles.
Context7 was resolved/queryed for the model-specific contract and C12's exact public
catalog JSON was read again before implementation; generic SDK system-role examples
were not imported into this model's payload.

`map_result` consumes an **unwrapped** model-result object and separate consumer
capture metadata. That metadata is an internal prerequisite supplied by a future
authorized caller, not new Cloudflare response fields or evidence observed here.
Expected-input digest syntax/equality, direct-classifier surface/model, nonempty
native request ID, exact HTTP/API success and explicit full-input/full-response
flags are required before even retaining a candidate verdict. The caller still
owns sealing the expected input and native capture; those flags alone never prove
provider target semantics, complete coverage or a native completion contract.

The mapper admits only an explicit boolean `safe` plus a noncontradictory unique
S1–S13 category list. String, missing/malformed/unknown categories (including S14),
absent/mismatched metadata or incomplete response stays unavailable without a
candidate verdict. Raw payloads, usage, reasons and native IDs are not copied into
the normalized result. Both valid candidate positive and negative results still
have `status: unavailable`, false provider-quality/detection/protection fields and
null metrics. There is no qualification switch, fallback generation or threshold.

Verification at the dirty worktree (HEAD remains `4f1a672`):

- RED: all **57** pure cases failed because the approved mapper did not yet exist.
- GREEN: all **57** passed after minimal implementation, then passed again after
  required formatting. Tests cover payload/target integrity, malformed/contradictory
  object/string results, each missing capture-evidence field, strict boolean/status
  checks, digest/correlation/surface boundaries and sanitized no-network mapping.
- `python -m ruff format .`: two new files formatted, 393 unchanged;
  `ruff format --check .`: 395 formatted; `ruff check .`: all checks passed.
- `git diff --check`: passed, with the existing P1 note LF/CRLF advisory.

Commands used the existing main-checkout `.venv/Scripts/python.exe`, without reading
its environment credentials or installing packages. No full-suite/integration test
was run under this pure-test-only grant; prior missing `deepeval`/`ragas` collection
limitations and exact-subject CI requirements remain unresolved. Mock/capture
metadata tests do not establish provider access, quality or successful live parsing.
Independent code review found **no actionable findings** and independently ran the
permitted focused file: **57 passed**. Static caller search found only the tests.
The reviewer confirmed the unqualified/unavailable boundary and sanitized mapping;
provider behavior, transport, runtime, broader tests and CI were not verified.

Exact formatted code SHA-256:

- Mapper: `b5984cd03390506a8ea808f853b9ed38cbd7a86aa7ba8912488dc5fe7bcba122`.
- Tests: `9023c7bd68fbbfb14799d1bbbb50cf9857af47e2eb32d83b24ade111b56dacef`.

All four P5/P6 fixture/review hashes and three previously recorded P4 report hashes
were rechecked unchanged. The prior dirty changes are preserved; no commit/push or
new exact-head CI occurred. The isolated mapper does not complete all of P6a.

#### Prepared canary bytes — not a live grant

The approved pure builder was applied offline to the four exact S2 draft rows.
Canonical payload bytes use UTF-8 JSON, `ensure_ascii=False`, sorted keys and
separators `(',', ':')`, no final newline. These hashes identify that precise
serialization; any later transport must send or explicitly re-review the exact bytes.
No tokenizer/model or network was used. All labels remain draft and canary potency
is unknown; counts/bytes do not prove input-token/template cost or target semantics.

| Case ID | Payload SHA-256 | UTF-8 bytes |
| --- | --- | --- |
| `p6-en-s2-risk_probe` | `61a3ec46ff64caca002ddc5f271196a20e45fd79dc2b523a8999fe21f4d61225` | 257 |
| `p6-en-s2-benign_control` | `d9f5ab35e812c5ab1ef4aab8d90575ecf893b39e2f96dca2bac3e3ee723e1bc4` | 296 |
| `p6-vi-s2-risk_probe` | `bb7bb5c232679898f4567ca72d3491ddb26130afba4daf804087cf7990b8dc4d` | 303 |
| `p6-vi-s2-benign_control` | `0de684d3c63e1e1f86608cbcf1610879f0c1755d3760b0ac0fae3353cd36fb9b` | 366 |

This preparation does not authorize account/credential readback, sending these
bytes, new transport code, acceptance of their proposed labels or a claim about
native response protection. The existing future-canary prerequisites still apply.

### P5 alternative-source comparison completed — October 17

The approved comparison is complete in
[the dated three-provider appendix](../research/issue-188-cloudflare-pii-dangerous-output.md#p5-hosted-alternatives--public-source-comparison-2026-10-17):
Azure AI Language Text PII, Google Sensitive Data Protection content inspection and
AWS Comprehend Detect PII, with 26 official source entries and Context7-first method.
No account, credential, provider call, fixture/label/code change or installation
occurred in the research. Earlier source/preparation history was preserved.

- **Azure:** Current PII-specific Text PII language table explicitly includes VI/EN;
  the named Email/PhoneNumber/Person/Address entities make it the first recommended
  investigation candidate for those four families. VN CCCD and generic MRN coverage
  remain unproved. Request API version and returned modelVersion are separate even
  where the public lifecycle tables currently use the same `2026-05-01` date.
- **Google:** A generic MEDICAL_RECORD_NUMBER detector is documented, but broad
  multilingual support does not prove VI for every required entity, nor VN CCCD.
  Its direct content-inspection result has explicit findingsTruncated semantics.
- **AWS:** Detect PII's operation-specific EN/ES boundary excludes VI; its generic
  language enum cannot widen this. Detect PII has a specific no-training statement,
  so generic Comprehend input-use prose is not transferred to it.

**No candidate qualifies all six VI/EN families.** Cloudflare stays research-only/
unqualified; recommending Azure first is not adoption or a reduced final scope.
All six families remain required. No custom pattern, dictionary, translation or
second provider is silently adopted as a CCCD/MRN substitute.

The appendix separates per-document errors/completion/truncation, native correlation,
model/region limits, input bounds, logging/retention and costs. Azure's dynamic paid
price cells were not readable as a quote and remain unknown; shared free allocations
for every provider remain account unverified. Public prices are not executable paid
ceilings. Valid synthetic VN phone/CCCD/address construction also remains unresolved;
the original invalid probes cannot qualify provider accuracy. Root spot-checks of
the official Azure Text PII language/model lifecycle pages and Google InspectResult
confirmed the relevant VI, version and truncation statements without account access.

The approved alternative comparison and P6 two-file pure mapper are now technically
complete; full P5a/P6a, quality, any live execution and #188 remain incomplete.

Independent review found **no actionable findings** in the appended P5 comparison.
The reviewer spot-checked official Azure VI/entity/version, Google content-pricing/
truncation and AWS operation-specific language/no-training sources. The review did
not independently verify every source, account entitlement, regional quota, provider
execution or empirical accuracy. It changed no code, fixtures or Git state.

Final handoff checks resolved **44 local Markdown link targets** across the Master,
this evidence note and the research note. `git diff --check` passed with the existing
P1 note LF/CRLF advisory. Mapper/test and all four P5/P6 draft hashes still match the
recorded values. No optional test rerun, full CI, provider or account check was added.

### Next owner decisions — P5 contract gaps and P6 canary design

Both branches below are **proposals awaiting owner decision**, not current authority.
They preserve all six PII families, all historical artifacts and all 30/52 draft
annotations. No provider adoption, quality acceptance or scope reduction is implied.

**P5 recommendation — Azure contract and format-gap preparation:** Investigate the
documented Email/PhoneNumber/Person/Address VI/EN subset before writing an adapter,
while keeping VN CCCD and generic MRN explicitly unresolved and required. Use at most
eight additional official public pages/Context7 queries for this same candidate and
synthetic-format rules; no fourth provider. Append only to the existing PII/Dangerous
Output research note, this evidence note and the Master. Deliver exact request/result
and empty/error/partial-result examples from published schemas, a six-family gap
table, source-backed valid-format constraints, and a proposed minimal adapter/test
file envelope. Never invent government identities or claim a format-valid synthetic
identifier is guaranteed unassigned. Account-specific prices/availability remain
unknown. No new fixture, label, code, package, account, credential, API or model call.
Alternative decision: resolve the full six-family coverage contract before preparing
the four-family adapter; this leaves P5 implementation blocked rather than narrowing it.

**P6 recommendation — revise the target-canary proposal offline:** Do not accept the
four existing S2 draft labels as strong target-discrimination evidence. The risky
assistant outputs merely endorse account theft; the safe outputs describe rejecting
it. Neither proves how the selected hosted policy treats that endorsement. Authorize
at most four replacement synthetic user/assistant pairs with source-backed S2 rubric
and safe controls, without actionable account-compromise instructions. Preserve the
old 52-case files and payload hashes. Write only a new
`evals/test/fixtures/cloudflare_dangerous_output/target-canary.proposed-v2.json`, with
exact text, proposed labels, limitations and owner-review-required state; append the
review packet to the same research/evidence/Master documents. At most four official
policy/model source pages/Context7 queries; no mapper/test/algorithm changes. If a
useful safe probe cannot distinguish assistant targeting under the documented policy,
report that limitation instead of inventing a passing oracle. Final labels and any
replacement of the selected live manifest still require review of the concrete text.
Alternative decision: retain the current four weak probes, explicitly exploratory;
they cannot qualify target semantics regardless of their eventual model outputs.

Neither proposal permits HTTP transport/runner code, authenticated API, credential/
account inspection, model/detector execution, cloud/log/billing mutation, runtime,
enforcement/export or commit/push/merge/deploy. A future live packet must separately
freeze reviewed input/labels, native evidence, quota/cost/retention and account
authority. No live permission is being requested at this checkpoint.

### Q1 threat-model revision approved and recorded — October 17

Owner explicitly approved applying the risk-based threat-model revision and reviewed
P0–P10 diff to the existing Master. The
[Master](../superpowers/plans/2026-10-16-issue-188-master-plan.md) now records that
adopted direction and the
[review artifact](../research/issue-188-threat-model-proposed-master-diff.md) retains
the exact frozen proposal and approval receipt.

The preceding Azure/P5 contract and replacement-canary/P6 proposals were not selected
and are superseded as the current frontier. P5 now prioritizes permitted recipients,
actual data flows and prohibited disclosure while preserving legitimate PII-bearing
Workspace Q&A. P6 targets owner-reviewed harmful-assistance scenarios and legitimate
use. Six-family PII/S1–S13 research remains retained inventory; new detector adoption
requires demonstrated value. P7/P8 no longer force a new scanner or FLAG integration.

This approval covers the documentation update only. It does not accept any of the
30/52 draft labels or P1/Secrets quality, select a vendor, create a new fixture,
authorize the next scenario/control packet or renew any account/credential/API,
model/detector, runtime/config, enforcement/export or Git publication permission.
P1–P4 phase contracts and historical artifacts are preserved; #192 selected-input,
native identity/digest and separate consumer-projection/supplement boundaries remain.
Full Issue #188 is incomplete; Detection Completed: no; Protection Enabled: no.


## Approved risk-based E/G/L execution — October 18

Owner approved Master section 12 Q1+Q2+Q3 / E+G+L. The single authoritative
execution/claim matrix is now [Master section 13](../superpowers/plans/2026-10-16-issue-188-master-plan.md#13-approved-egl-execution--october-18).
Historical P1–P4 bytes/dispositions and P5/P6 drafts remain unchanged.

The new [offline supplement](../../evals/reports/security_outcomes/offline-001/report.json)
contains 32 selected cases: six local authorization/payload units completed,
26 model cases not_run/unavailable and zero semantic adjudications. PII presence
is distinct from permitted disclosure; authorized cited use remains legitimate.
No new detector, production hook, prompt or schema was introduced.

L preflight confirmed Workers Free but did not freshly establish every billing
condition; D6 closed the branch without reading credentials or sending requests.
The runner therefore has no live/credential path. Future use needs a fresh concrete
envelope; unused allowance does not transfer. Semantic quality stays unverified.

Pair projection uses selected #192 source8535130, not a schema guessed from old
reports. Native read_run does not expose attempt_id, so exact binding is unavailable;
no ID invention, latest trace, re-answer or shared contract edit. The selected flat
historical capture SHA6daa50d8 remains unchanged and unavailable for exact evidence.

Independent review passed after fixes; 43 new, 127 preserved and 250 combined
boundary/scorer tests passed. Ruff/OpenAPI/Compose passed. Missing local
DeepEval/Ragas/Vitest defer required coverage to exact-head CI under G; no installs.
See Master for frozen SHA, limits, claim matrix and final owner gates. Runtime,
enforcement and export remain OFF; no quality acceptance or merge is inferred.

## Final owner disposition — October 18

After readback of implementation `90da152d3bbbae04d4e315685b6527b13a7b23e6`
and all seven successful jobs in [CI run 39053369381](https://github.com/NhiBuaa/knora-agent/actions/runs/39053369381),
the owner explicitly selected **“Nghiệm thu engineering/research, chấp nhận hoãn
qualification và đóng #188”**. This authorizes Issue/Project/Goal closeout for the
engineering/research scope recorded in Master section 13. Six local units are
complete; 26 model cases remain not_run/unavailable and zero are semantically
adjudicated. P1/Secrets remain experimental; private processor permission and
native saved-attempt binding remain unverified. Historical evidence/draft labels
are unchanged. Detection Completed: no; Protection Enabled: no. PR #199/#205 stay
Draft/unmerged; no renewed live session, merge/deploy or runtime/enforcement/export
activation follows from this acceptance.

## Subsequent disposition — research-only / archived, October 18

The owner approved retaining #188 as completed research at the current checkpoint,
preserving its threat model, historical evidence and offline evaluators in
`codex/test`; no revert or deletion was selected. No further qualification or
detector/runtime implementation is planned automatically. "Archived" is the
initiative disposition, not a repository/worktree/PR operation. Main integration
as a runtime feature, provider calls, new issues/vendors, activation and deployment
are not authorized by this decision. PR review state is preserved independently.
Future controls must address a concrete threat and demonstrate security value
without preventing authorized PII-bearing Workspace Q&A. See the Master current
disposition; all historical gaps remain recorded. Detection Completed: no;
Protection Enabled: no; runtime/enforcement/export OFF.
