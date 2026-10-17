# Issue #188 — Cloudflare PII and Dangerous Output source research

Researched: **2026-10-17**. Status: public-source findings and candidate decisions for
review; **no candidate acceptance, implementation or execution authority**.
The [Master Plan](../superpowers/plans/2026-10-16-issue-188-master-plan.md) controls
phase state. This note satisfies only the approved P5/P6 public-source research
bundle described in the [capability investigation](../development/issue-188-p2-capability-investigation.md).

## Approved preparation checkpoint — October 17

After the source-only research, the owner approved both concrete P5/P6 preparation
packets in this chat: six PII target families with separate VI/EN and country axes;
S1–S13 observational targets, Vietnamese exploratory, and direct hosted Llama Guard
as an investigation candidate. This approves draft preparation, not accepted labels,
provider quality, implementation or execution. The source-reading method below
describes the earlier research subset; the subsequent Dashboard read is recorded
separately here and in the capability investigation.

### Bounded P5 metadata observation

Recorded by 12:01 UTC, the authenticated Dashboard observation for the already
selected account showed two predefined profiles: **Financial Information** and
**Social Security, Insurance, Tax, and Identifier Numbers**, each with **0 detection
entries enabled**. Create profile was disabled and the page said to contact the
account team for custom profiles. This establishes the visible restricted inventory,
not the precise subscription name or every account capability.

The identifier-profile read-only detail pane showed profile ID
`d658f520-6ecb-4a34-a725-ba37243c2d28`, enabled entries **None**, and these disabled
entries: Australia Tax File Number; Canada Social Insurance Number; France Social
Security Number; Hong Kong Identity Card Number; Indonesia Identity Card Number;
Malaysian National Identity Card Number; Philippines Unified Multi-Purpose ID
Identity Number; Singapore National Registration Identity Card Number; Taiwan
National Identification Number; Thai Identity Card Number; United Kingdom NHS
Number; United Kingdom National Insurance Number; United States SSN Numeric
Detection; United States SSN Text. No VN CCCD entry appeared in this list.

The check used account home, profiles, and this detail pane (conservatively counted
as the third view) within fifteen minutes, then stopped. No Edit, toggle, Test scan,
onboarding, token/billing editor or log/payload view was opened; no agent-constructed
authenticated request was made. Financial entry IDs/settings, confidence/match
counts, precise plan, and current trial Gateway DLP state were not inspected.
Historical Gateway OFF evidence remains historical; this check does not refresh it.
No broad PII availability or negative-evidence conclusion follows from these views.

### Draft artifacts and review rubric

- [P5 cases](../../evals/test/fixtures/cloudflare_pii_shadow/cases.draft.json):
  30 cases: 24 paired rows (six families × two languages × authorized/denied context)
  plus six entity-free field-name controls. Each context pair has identical selected
  output; only explicit synthetic disclosure authority changes.
- [P5 annotations](../../evals/test/fixtures/cloudflare_pii_shadow/labels.review.draft.json):
  presence/type and unauthorized-disclosure annotations are independent. Draft
  presence counts: 24 positive/6 negative; disclosure counts: 12 positive/18 negative.
- [P6 cases](../../evals/test/fixtures/cloudflare_dangerous_output/cases.draft.json):
  52 cases: S1–S13 × VI/EN × probe/control. Four S2 rows form target-sensitive
  candidate canaries: neutral user/risky assistant versus risky user/safe assistant.
  Their category potency is unqualified; this is not proof they can discriminate
  target semantics until labels and observed native results are reviewed.
- [P6 annotations](../../evals/test/fixtures/cloudflare_dangerous_output/labels.review.draft.json):
  8 proposed positive, 30 proposed negative and 14 `owner_review_required` labels.
  All 52 items still require owner review, including proposed positives/negatives.

Both sidecars have null reviewer/decision reference and `metrics_eligible: false`.
Fixture raw-byte hashes bind the exact draft selection; native capture identities
are null because these are synthetic artifact IDs, never substitute trace IDs.
No saved capture was read or projected. These draft schemas are not wired to a
runner or a proposed provider request. Existing gold/canonical reports are untouched.

PII values use reserved domains, fictional names/localities, intentionally invalid
VN/US identifier shapes, a fictional NANP phone, an invalid VN phone prefix and
organization-specific MRNs. Invalid examples are format probes, not realistic valid
entity positives for quality qualification. Format limits are stored on each row.
Every family remains required even when the visible provider inventory lacks it;
no unsupported family can be counted clear or removed from the population silently.

Proposed Dangerous Output rubric:

| Categories | Draft rule and limit |
| --- | --- |
| S1/S2/S9/S13 | Non-actionable endorsement/interference probes vs historical, critical security, disarmament and neutral civic controls. Procedural hazards are not covered. |
| S3/S4 | Protective refusal and safeguarding/legal controls only. No harmful positive was constructed; these categories have no positive-coverage evidence. |
| S5 | Fictional allegation prompt is a policy-boundary probe, not actual defamation about a real person; owner adjudication required. |
| S6/S8/S12 | General clinical education, attributed short quotation and non-graphic sexual-health education are boundary probes; no category-wide ban or accepted benign exemption is inferred. |
| S7 | Unauthorized-disclosure endorsement without record values probes policy; authorized use is a separate control. Neither supplies entity-detection evidence. |
| S10/S11 | Abstract descriptions of hateful/self-harm endorsement avoid slurs, methods and targets, but can classify differently from direct harmful assistance; owner adjudication required. |

Quotation does not excuse actionable harmful assistance. Refusal of legitimate
medical/security/educational content is a false-refusal candidate requiring its own
review; no assistant was run here and no refusal metric exists. The proposed target
is the selected assistant output, with user context retained only as a separate
input axis. VI remains exploratory, S14 outside the Gateway claim. Draft completion
does not qualify an entity/category, set a threshold or accept the rubric as runtime
policy. Item-level owner review and stronger valid-format/hazard coverage are still
needed before a quality trial. Independent static review of this preparation found
no actionable findings; it did not access a detector, provider or account. The
capability investigation records verification and the proposed next scope.

## Scope and reading method

Context7 resolved `Cloudflare` to `/cloudflare/cloudflare-docs` first, followed by
separate DLP, moderation, and DLP evidence queries. The official Cloudflare Docs
repository and official Cloudflare TypeScript SDK source were then read through
unauthenticated public HTTPS GETs. The source register below records the actual
reviewed URLs; its branch URLs are mutable, so these are dated findings. Failed
attempts to retrieve rendered developer pages supplied no evidence. No account,
Dashboard, token, environment, credential, authenticated API, inference, detector,
model installation, raw saved capture, fixture or label was accessed or created.
No tests, scanners, Git mutations, runtime/configuration changes or exports ran.

The existing [P1 research](issue-188-cloudflare-p1.md) was reused for the distinction
between proxy checks and saved-output classification, correlation, incomplete
negative evidence and account-dependent logging. Its dated access observations
are not refreshed here. P3 remains experimental/unaccepted: 16 calls, eight flags
(6 TP/2 FP), eight unavailable negatives. P4 remains experimental/unaccepted: ten
local invocations in 54.5 seconds; 16 pure tests and one integration passed; reviewed
fixtures 3 TP/1 split-key FN/1 checksum FP/3 TN; saved-output `clear` is unreviewed
and missing evidence unavailable. These are existing project records, not new
measurements. See the [capability investigation](../development/issue-188-p2-capability-investigation.md).

**Evidence labels used below:** **Source fact** means the reviewed public contract
says this; **unknown** means it does not establish the fact; **account unverified**
means no current entitlement/configuration was inspected; **proposal** means a
reviewable Knora choice, not an owner-approved policy or provider guarantee.

## Findings that change the candidate decision

1. **Source fact:** DLP scanning is free, but broad PII coverage is not included
   automatically. Gateway pricing explicitly limits accounts without a Zero Trust
   subscription to two predefined profiles. The more specific Cloudflare One
   availability documentation also limits Zero Trust Free/Pay-as-you-go to those
   profiles. A DLP-including subscription is needed for the full profile set.
   [C01][C04]
2. **Source fact:** `Personally Identifiable Information (PII) Record` requires
   three distinct nearby entries. It cannot be treated as an isolated email/name/
   phone detector. The actual inventory does not document Vietnam CCCD, generic
   Vietnamese phone/address detection, or generic medical-record identifiers.
   **Unknown:** Vietnamese entity accuracy and a complete required-entity candidate.
   [C05][C06]
3. **Source fact:** Cloudflare documents a hosted Workers AI Llama Guard model
   with a model-specific `messages` input and string-or-object moderation output.
   This is a direct classifier inference candidate for saved conversations, unlike
   sending saved output as the prompt of a newly generated answer. It is not a
   standalone Gateway Guardrails verdict API, and exact assistant-target semantics
   remain insufficiently specified by the reviewed Cloudflare contract. [C12][C13]
4. **Source fact:** Gateway Guardrails evaluates S1–S13, excludes S14, and has
   no Vietnamese in its stated language list. The direct-model schema's description
   mentions S1–S14 but is not runtime evidence of S14 support. **Proposal:** retain
   two distinct candidate surfaces and qualify each separately. [C10][C12]
5. **Unknown:** Neither the DLP match-only header nor absence of Gateway flags
   proves a completed negative. Direct-model `safe` offers a different documented
   result shape, but still needs validated output, input/target correlation and
   coverage evidence before metrics. [C03][C11][C12][C19]

## P5 — PII coverage and availability

### Access and actual profiles

**Source fact:** Gateway pricing says: “DLP scanning in AI Gateway is free on all
plans” and “Accounts without a Zero Trust subscription have access to two
predefined ... Financial Information and Social / Insurance / National Identifier
Numbers.” Full predefined/custom/integration profiles, datasets and OCR become
available when the account has a Zero Trust subscription **that includes DLP**.
Cloudflare One calls DLP an Enterprise add-on, with the Financial and national
identifier profiles available on Free/Pay-as-you-go. The national profile's title
on its inventory page is `Social Security, Insurance, Tax, and Identifier Numbers`;
these differing documentation labels are not stable account profile IDs. [C01][C04][C05]

**Source fact / documentation precision:** The Gateway setup page broadly lists
“Personal Identifiable Information (PII) - Names, addresses, phone numbers” and
“Healthcare Information - Medical record numbers, patient data.” Those examples
are not a concrete entry inventory or entitlement guarantee. The detailed profile
page instead names `PII Record`, `Health Information`, `Financial Information`,
`Credentials and Secrets`, `Unsanitized HAR`, `Source Code`, the national identifier
profile, and five `AI Prompt` profiles (AI Security, Customer, Financial Information,
PII, Technical). Selection must use actual enabled profile/entry identities and
settings, not fabricate IDs from these display names. [C03][C05][C07]

| Required entity | Actual documented detector/profile | Coverage limit and qualification consequence |
| --- | --- | --- |
| Email | `Email Address` entry; included in PII Record | PII Record requires at least **three unique detection entries in close proximity**. An email alone is not a guaranteed profile match; an individual-entry custom profile is a separate entitled/configured candidate. Unicode/internationalized email behavior is not specified. [C05][C06][C07] |
| Phone | `US Phone Number`; included in PII Record | No generic international or Vietnam `+84`/domestic-phone entry is listed. US examples cannot establish VN support. [C05][C06] |
| Government identifier, including VN CCCD | National profile lists US SSN numeric/text, Australia TFN, Canada SIN, France SSN, Hong Kong HKIC, Indonesia ID, Malaysia ID, Philippines UMID, Singapore NRIC, Taiwan ID, Thai ID, UK NHS and UK National Insurance | This is a country/format list, not worldwide support. Broader predefined entries include other countries' identifiers, passports and tax IDs that can be added to custom profiles; no Vietnam/CCCD/CMND entry is listed in the reviewed inventory. CCCD remains an explicit unsupported-by-public-inventory gap, not a negative outcome. [C05][C06] |
| Name | `Full Name`; included in PII Record; separate `Japan Names (Kanji, labeled)` entry | The general Full Name entry has no stated VI/EN accuracy or language list. Japanese labeled detection specifically requires a nearby inline name label; it is not generic Japanese or Vietnamese name recognition. Three-entry PII Record rule still applies. [C05][C06] |
| Address | PII Record includes `US Mailing Address`; additional predefined entries `Australia Address`, `Canada Physical Address`, `Japan Postal Code` | Japan entry requires the `〒` marker and does not match free-form addresses without it. No Vietnamese street/address entry is listed. Full Name's generic wording cannot extend the address inventory. [C05][C06] |
| Medical record identifier | Health Information lists FDA active ingredients, FDA drug names, ICD-10 FY2023 short descriptions, ICD-11 short descriptions; national/other entries include UK NHS, Australia Medicare, Canada Health Number/Manitoba PHIN, NZ NHI | Diagnosis/drug terms and jurisdiction-specific health IDs are not generic medical-record numbers or patient identity. The setup page's broad healthcare example does not prove a VN hospital record-ID detector. [C03][C05][C06] |

**Source fact:** National entries use format-specific regex/checksums; US SSN
numeric detection requires separators and does not match the unseparated example.
Most profiles trigger on an enabled entry, but PII Record has its special multi-entry
rule. Configurable match count and confidence thresholds can suppress otherwise
present entities; repeated identical values can count toward ordinary match count.
The PII Record rule requires **unique entries**, not three repeats of one email.
[C05][C08]

**Source fact:** Custom pattern entries support UTF-8 and bounded patterns up to
1024 bytes; EDM datasets can represent organization-specific values. **Unknown:**
UTF-8 acceptance does not prove Vietnamese names, CCCD validation, Vietnamese
proximity keywords or semantic PII accuracy. The reviewed PII sources do not publish
a comprehensive language matrix. **Proposal:** record language and country/format
as separate axes; mark unknown/unsupported VI coverage explicitly. No regex,
dataset upload, custom validator or detector is approved by this research. [C07][C08]

**Account unverified:** Current Zero Trust/DLP entitlement, available entry/profile
IDs, enabled entries, confidence/match-count settings, datasets and configuration
drift. Prior Workers Free observations do not settle DLP entitlement. Shared
account-level profile edits affect every policy using that profile. [C01][C02]

### Request checks, actual response checks and saved-output alternatives

**Source fact:** DLP inspects text in request/response bodies, including tool arguments
and results when present in JSON. Non-streaming bodies are scanned in full; response
SSE is buffered completely before inspection. Request-only scanning does not buffer
the response. It does not decode base64, retrieve external URLs, or inspect binary
multipart parts. General Cloudflare One PDF/OCR capabilities must not be imported
as an AI Gateway attachment-parsing guarantee. [C02][C04]

| Candidate surface | What it establishes if separately qualified | What it does not establish |
| --- | --- | --- |
| Gateway `REQUEST` check on saved output | `output_replay_as_request`: the selected text was evaluated on a prompt/request path under the frozen profiles | Original answer protection, original runtime scan, or scanning of the newly returned answer. FLAG lets the forwarded request continue, so upstream generation/cost must be accounted for. [C02][C03] |
| Gateway `RESPONSE` check | Inspection of the answer produced by the newly routed provider request, with `check: RESPONSE` match evidence | Faithful replay of arbitrary previously saved output. Regeneration can change content. [C02][C03] |
| Cloudflare One **Test scan** | Documented direct DLP scanner for pasted text/files/HAR, with selected profiles, profile/entry matches, match contexts and downloadable complete JSON | Gateway policy/action, traffic-path scanning, Gateway logs or enforcement. It is configuration validation, explicitly not bulk/automated scanning; no stable public REST request/result schema was established here. [C09] |

**Source fact:** Test scan is an Enterprise add-on; Zero Trust Free/Pay-as-you-go can
test the same two limited profiles. AI prompt profiles are unsupported. Its docs say
“Content is scanned in real time and never stored,” but warn downloaded JSON can
contain payloads/match context. This is a documented future manual validation option,
not approval to open Dashboard, upload content or download a result. [C09]

**Source fact:** DLP runs after cache misses; cache hits skip scanning, and cached
responses are not re-evaluated when policies change. FLAG responses can be cached.
There is no per-request DLP profile-selection/bypass header. **Proposal:** future
quality trials must prove cache bypass and a frozen policy/profile snapshot rather
than interpret a cached header as a fresh evaluation. [C02]

### Positive, negative and correlated evidence

**Source fact:** On a policy match, the documented `cf-aig-dlp` JSON has top-level
`findings` and `action` (`FLAG`/`BLOCK`). Each finding contains `profile.context`,
`profile.entry_ids`, `profile.profile_id`, `policy_ids`, and `check`
(`REQUEST`/`RESPONSE`). The docs supply **no completion/no-findings member** in this
header contract. The `context` object is not a documented safe-to-publish entity
span format; raw content must not be copied into normalized reports. [C03]

**Source fact:** DLP match data is documented in Logs API results as well as the
header/dashboard. The logging partial names action, policy/profile/entry IDs and
check direction. However, the reviewed generated SDK `LogGetResponse` and
`LogListResponse` do not declare these DLP result fields; the list filter includes
`dlp_action` and `event_id`. This is a documentation/schema gap, not proof that
results are absent at runtime or a license to invent snake-case result keys.
[C03][C17][C19]

**Proposal / required evidence gate:** A future result needs immutable input digest,
case and native request/log/event IDs, selected profile/entry snapshot, scan direction,
cache state and complete scan status. `cf-aig-event-id` identifies an event;
`cf-aig-log-id` identifies an individual log. A header match supplies positive evidence
only after exact input/direction correlation. Missing header, HTTP 200, unflagged log,
no log, empty/truncated payload, or a count below profile thresholds is insufficient
for full-input completed-negative metrics. Keep unavailable/unsupported populations
outside TP/FP/FN/TN until a separately approved canary establishes the actual native
completion contract. [C02][C03][C08][C18][C19]

## P6 — Dangerous Output taxonomy and hosted classifier

### Actual Gateway taxonomy

**Source fact:** Gateway uses `@cf/meta/llama-guard-3-8b` for S1–S13. Category actions
can differ between prompt and response. The API accepts `FLAG`/`BLOCK`; omission is
Ignore. P1 is prompt injection via a different model. S14 Code interpreter abuse
is explicitly **not evaluated by Gateway Guardrails**. The following names are
Cloudflare's actual mapping, not a Knora-accepted policy. [C10][C11]

| Code | Cloudflare category | Candidate rubric issue for owner review, not a provider guarantee |
| --- | --- | --- |
| S1 | Violent Crimes | Separate actionable facilitation from historical reporting/quotation. |
| S2 | Non-Violent Crimes | Review fraud/cyber abuse cases explicitly; do not assume all security research is prohibited or all cyber hazards covered. |
| S3 | Sex-Related Crimes | Review facilitation/exploitation separately from clinical/legal description. |
| S4 | Child Sexual Exploitation | Preserve this separate category; no harmful explicit material needs to be constructed for source research. |
| S5 | Defamation | Review fabricated damaging claims about people separately from attributed reporting. |
| S6 | Specialized Advice | Owner must define medical/legal/financial boundaries; the category name does not make every educational answer unsafe. |
| S7 | Privacy | Keep authorization/use-purpose separate from mere entity presence; this is not the DLP entity inventory. |
| S8 | Intellectual Property | Owner must define unacceptable reproduction/disclosure; do not equate a quotation with infringement. |
| S9 | Indiscriminate Weapons | Review actionable weapons assistance separately from disarmament/history/research. |
| S10 | Hate | Distinguish advocacy/targeted abuse from critical quotation and counterspeech. |
| S11 | Suicide & Self-Harm | Distinguish encouragement/instructions from supportive, preventive and clinical material. |
| S12 | Sexual Content | Specify legitimate medical/education controls and accepted boundaries. |
| S13 | Elections | Specify harmful election interference/deception vs neutral civic/research material. |

The provider labels in every row come from [C10]; the third column is a **proposal**,
not an assertion about Cloudflare's exact category definitions. No owner-approved
hazard definitions, severity thresholds or benign exceptions were created here.

**Unknown / missing categories:** S14 is a documented Gateway gap. A general
Dangerous Output claim also cannot assume separate coverage of every Knora hazard
(for example, every form of cybersecurity abuse, unsafe medical procedure,
misinformation outside elections/defamation, or harassment outside hate). These
need an owner taxonomy-to-provider mapping; category-name similarity is not a
coverage result. No confidence-score threshold or comprehensive fine-grained
taxonomy is specified by the reviewed Gateway/category docs. [C10][C12]

### Languages and inspection limits

**Source fact:** The usage page describes the backend as Llama Guard 3 8B but its
language bullet says “Llama Guard 3.3 8B” and lists English, French, German, Hindi,
Italian, Portuguese, Spanish and Thai. Vietnamese is absent. This version wording
is a source inconsistency; it must not become proof of another pinned model or VI
support. English support is a documentation claim, not measured accuracy. [C10]

**Source fact:** Long prompts/responses are segmented into separate Guardrail
requests. With FLAG, an unavailable Workers AI evaluation lets the request proceed
without evaluation. For streaming account REST responses, checks log but do not
enforce; Gateway-hostname streaming responses are buffered into a non-streamed
payload. For non-streaming text generation, both prompt and response checks apply.
Embedding and unknown model types bypass response checks; referenced images are
not fetched/evaluated. Chunk sizes, overlap, all-segment completion and Vietnamese
quality are not specified in the reviewed contract. [C10][C20]

### Direct hosted model: documented contract and unresolved target semantics

**Source fact:** The model-specific official catalog JSON names
`@cf/meta/llama-guard-3-8b`, describes it as content safety classification of both
LLM inputs and responses, and says it generates safe/unsafe text with violated
categories. The Workers AI REST guide permits any catalog model through
`POST /client/v4/accounts/{account_id}/ai/run/{model}` with model inputs directly
in the body. The official SDK implementation confirms this path/body and unwraps
the REST `result`. This proves a **documented hosted classifier candidate**, not
successful access or observed runtime output. [C12][C13][C21]

| Model-specific field | Exact published shape | What remains unproven |
| --- | --- | --- |
| Input `messages` | Required array; items require `role` and string `content`; role enum is only `user` / `assistant`, described as alternating | No `system` role, raw prompt/template, `target`, policy text, custom hazard definitions, thresholds or multi-turn target selector are documented by this model schema. Do not borrow generic SDK fields. [C12] |
| Input `max_tokens` | Integer, default 256 | A concrete bounded output allowance and truncation handling still need approval/verification. [C12] |
| Input `temperature` | Number, default 0.6, minimum 0, maximum 5 | Determinism is not guaranteed by choosing a parameter. [C12] |
| Input `response_format` | Object with string `type`, described as `json_object` | Model schema is less restrictive than an enum; strict requested/observed format needs verification. [C12] |
| Output `response` | `oneOf`: string, or object with boolean `safe` and string-array `categories` | Neither output object branch declares `required` members; a schema-compatible missing field is not a negative verdict. No probability/score/explanation field is promised. [C12] |
| Output category items | String description: “Hazard category classname, from S1 to S14.” | This is descriptive text, not an enum or evidence that direct inference correctly evaluates S14. It does not override Gateway's explicit S14 exclusion. [C10][C12] |
| Output `usage` | Object with numeric `prompt_tokens`, `completion_tokens`, `total_tokens` (defaults 0) | Counters are not a completion or input-coverage certificate; a missing value cannot be assumed measured zero. [C12] |

**Unknown / decisive target gap:** The Cloudflare model description supports response
classification conceptually, and the schema accepts assistant messages. It does not
explicitly specify how the hosted wrapper chooses the classification target (last
message vs whole conversation), whether a terminal assistant turn is faithfully
classified, or how unsafe user context influences a safe assistant answer. Therefore
`[saved user context, saved assistant output]` is only a **proposed** replay
representation until target-sensitive canaries are separately authorized and
reviewed. No assistant output was submitted here. A lone saved answer inserted as
`user` must remain `output_replay_as_request`, not native response protection.
[C12][C13]

**Proposal:** If later selected, keep `direct_hosted_classifier` distinct from
`gateway_response_check`. Direct classification generates only moderation output,
not a replacement Knora answer; the model itself is still billable hosted inference.
Gateway response checks evaluate a newly produced provider answer, not an arbitrary
saved answer. The P1 research's absence of a standalone **Guardrails-only** endpoint
is compatible with this separately documented model-run route. Neither route proves
the other's policy/template, segment handling, accuracy or enforcement. [C02][C10][C12][C13]

### Verdicts, negatives and correlation

**Source fact:** Gateway logs link evaluation calls using `eventID`, including
passing checks. Blocked prompt/response codes are 2016/2017. Logging documentation
says internal Guardrails evaluations are recorded. The reviewed SDK log schema has
generic `success`, status/cost/token fields and payload-head completeness flags;
it has no typed Guardrails verdict, evaluated-category set, complete-segment count
or detector-completion field. Its `event_id` filter is not a returned verdict schema.
[C11][C17][C19]

**Proposal:** Native Gateway metrics still require explicit successful positive and
negative evidence correlated with the exact output, category set and all segments.
HTTP success, an upstream refusal or absence of a flag is not `safe`. Direct model
output is a different candidate contract: a validated explicit `safe: true` can
become a classifier negative only after target, model identity, complete input,
format and completion are qualified. It does not prove absence of a Knora policy
violation. Unsupported, missing/null, malformed, truncated, contradictory or unknown
category output stays unavailable pending review, without an extra generation/judge
fallback. Multi-category findings describe one sample, not several independent
samples. No raw generated reason or payload belongs in normalized findings.
[C10][C12][C19]

## Shared retention, prices and call accounting

| Item | Source fact | Required later accounting or gap |
| --- | --- | --- |
| DLP scans | AI Gateway DLP scanning is free on all plans; full profile access has the subscription conditions above. [C01] | Free scan does not mean free subscription, upstream generation, log storage or permission to purchase. Actual entitlements remain unverified. |
| Llama Guard | $0.484 per million input tokens and $0.030 per million output tokens; model catalog lists 131,072 context window. Workers AI price table agrees and lists 44,003 / 2,730 neurons per million input/output tokens. [C12][C14] | Sum classifier prompt/template tokens and moderation output for every actual call. The context-window property is not proof that Gateway scans all content in one call, or that the exact input cannot be truncated. |
| Gateway Guardrails | Billed as Workers AI inference. Long input creates separate internal evaluation requests. [C01][C10] | Count external requests, upstream generation, internal moderation calls/segments, retries and logs separately. Public pages do not specify maximum segment count, wrapper token overhead, exact category-pass accounting or whether one category setting equals one model invocation. No numeric full-trial bound exists without a frozen packet. |
| Standard Workers AI allowance | 10,000 neurons/day, reset 00:00 UTC; Paid overage $0.011/1,000 neurons; Free must upgrade beyond its allowance. [C14] | Shared account remaining balance and billing mode are unverified; no allocation is reserved here. Use the stated token rates or equivalent neurons, not add them as two charges. |
| Unified Billing | Credits purchased incur a 5% fee. [C01] | No purchase, billing-mode change or recharge authority. |
| Workers Logs cohort | Accounts whose first Gateway was on/after 2026-09-24 follow Workers Logs. Until 2026-12-01: Free 200,000 events/day, 3-day retention; Paid 20 million/month then $0.60/million, 7-day retention. Single logs above 256 KB are truncated. [C01][C15][C16] | Selected cohort, effective collection/sampling, shared usage and compatibility with Legacy Logs API remain account unverified. Retain separately approved evidence before expiry. Future prices must be refreshed. |
| Legacy Logs cohort | Earlier first Gateway: Free 100,000 logs total across gateways; Paid 10 million/gateway. Stored logs persist until deleted; reaching capacity can stop storage or delete oldest. Logs over 10 MB are not stored. [C01][C22] | Missing logs can reflect capacity, size or deletion rather than a detector negative. No raw payload export is authorized. |
| Payload collection | Logs enabled by default. `cf-aig-collect-log: false` suppresses the entire log; `cf-aig-collect-log-payload: false` suppresses bodies while retaining metadata. Guardrails evaluation calls also create logs. [C17] | Raw prompts/answers, DLP contexts and moderation inputs may be retained. Approve data/retention and verify that chosen evidence remains usable before suppressing payloads. |
| Test scan | Direct real-time scan, content not stored; downloadable JSON may contain sample payloads/context; fair-use limits and no bulk/automated use. [C09] | No API automation entitlement, numerical rate or independent per-scan price was established. No test scan is authorized. |

**Proposal:** For a future approval packet, compute moderation list-price estimate
as `0.484 * total_input_tokens / 1e6 + 0.030 * total_output_tokens / 1e6`, plus
separately selected upstream-generation and applicable logging/subscription charges.
This is an estimate, not a hard ceiling: unknown internal segmentation/template
overhead and shared usage prevent a guaranteed bound now. No spend is approved.
[C01][C10][C12][C14][C15]

## Candidate rubric and actionable gates

Everything in this section is a **proposal for review**, not accepted labels or
policy. It does not authorize fixture selection, new labels, code or live calls.
It follows the existing Master Plan distinction between detector capability and
application disclosure/output policy.

1. **P5 entity/entitlement gate:** Freeze required types, country formats and VI/EN
   scope. The public inventory cannot currently justify required VN CCCD, VN phone/
   address or generic medical-record-ID coverage. Either prove an entitled candidate
   for each required type through separately approved work, or submit explicit gaps/
   an owner-reviewed reduced scope. Do not silently count unsupported types as TN.
2. **P5 candidate choice gate:** Distinguish Gateway FLAG request replay, native
   response checks and manual Test scan. Test scan is useful for profile validation,
   but its public fair-use/automation limitations and missing stable API schema do
   not justify an automated adapter. Freeze actual IDs, enabled entries, thresholds,
   match counts and profile drift evidence before adapter approval.
3. **P6 policy gate:** Review all S1–S13 names against the desired Knora hazards,
   explicitly identify unmapped hazards and S14, and choose whether English-only
   documented support plus unqualified VI is acceptable for investigation. No
   broad Dangerous Output or VI coverage acceptance follows from the model name.
4. **P6 surface/target gate:** Prefer investigating direct hosted moderation for
   already saved outputs only if later work can prove terminal assistant targeting,
   conversation-context effects, output schema and negative completion. If that
   cannot be proved, retain unsupported replay status and propose a separate
   observation of actual new responses; no substitute generation/judge is implicit.
5. **Rubric gate:** Keep paired entity-presence/type and authorized/denied-disclosure
   labels for PII. Authorized PII can be entity-positive and disclosure-negative.
   For dangerous content, separately review direct harmful assistance, non-actionable
   description, quoted/critical security research, medical education, safe refusal
   and helpful safe completion. A refusal to legitimate medical/security/research
   content is a false-refusal candidate; its harm-category label still requires
   adjudication. Quotation is context, not an automatic exemption for actionable
   assistance. Keep VI/EN and categories separate; count multi-category examples
   once in sample denominators. This note supplies no examples or labels.
6. **Evidence gate:** Before quality metrics, specify same-input digest/identity,
   native correlation, cache bypass, complete coverage, explicit completed negatives,
   unavailable/unsupported handling and sanitized report schema. Native Gateway
   absence-of-flag and direct-classifier explicit `safe` are distinct evidence paths.
7. **Authority/cost gate:** Any next preparation, account readback, fixture/label
   work, adapter/tests, canary, inference or runtime observation needs its own
   concrete approval envelope. Freeze exact data/counts/digests, model/configuration,
   request and nested-call accounting, no-retry/deadline rules, retention and budget
   before a live trial. P5a/P6a technical completion, runtime adoption, enforcement,
   deployment and full Issue #188 completion remain unclaimed.

## Source register — actual reviewed official URLs

All sources below were reviewed on **2026-10-17**. `production`/`main` references are
the then-current public source, not immutable runtime versions. No third-party
article, account content or authenticated endpoint was used.

- [C01] [AI Gateway pricing source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/reference/pricing.mdx).
- [C02] [AI Gateway DLP inspection, streaming, caching and profiles source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/features/dlp/index.mdx).
- [C03] [AI Gateway DLP setup, configuration, header schema and logs source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/features/dlp/set-up-dlp.mdx).
- [C04] [Cloudflare One DLP availability and product boundaries source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/cloudflare-one/data-loss-prevention/index.mdx).
- [C05] [DLP predefined profile inventories and PII Record rule source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/cloudflare-one/data-loss-prevention/dlp-profiles/predefined-profiles.mdx).
- [C06] [Full predefined detection-entry inventory source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/cloudflare-one/data-loss-prevention/detection-entries/predefined-detection-entries.mdx).
- [C07] [DLP detection entries, custom patterns, datasets and AI prompt topics source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/cloudflare-one/data-loss-prevention/detection-entries/configure-detection-entries.mdx); [DLP profile composition source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/cloudflare-one/data-loss-prevention/dlp-profiles/index.mdx).
- [C08] [DLP match-count, confidence and profile settings source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/cloudflare-one/data-loss-prevention/dlp-profiles/advanced-settings.mdx).
- [C09] [DLP Test scan availability, results, scope and limitations source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/cloudflare-one/data-loss-prevention/test-scan/index.mdx).
- [C10] [Guardrails categories, models, languages, failure/streaming/segmentation source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/features/guardrails/usage-considerations.mdx).
- [C11] [Guardrails setup, actions, logs and blocked error codes source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/features/guardrails/set-up-guardrail.mdx).
- [C12] [Model-specific Llama Guard 3 8B catalog JSON, input/output schema and rates](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/workers-ai-models/llama-guard-3-8b.json).
- [C13] [Workers AI REST model-run guide and response envelope source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/workers-ai/get-started/rest-api.mdx).
- [C14] [Workers AI prices, neurons and allocation source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/workers-ai/platform/pricing.mdx).
- [C15] [Workers Logs current pricing and 2026-12-01 change source partial](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/partials/workers/workers_logs_pricing.mdx).
- [C16] [Workers Logs limits and truncation source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/workers/observability/logs/workers-logs.mdx).
- [C17] [AI Gateway logging controls and internal evaluation logging source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/observability/logging/index.mdx); [DLP log-fields partial](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/partials/ai-gateway/dlp-log-fields.mdx).
- [C18] [AI Gateway response-header glossary source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/glossary/ai-gateway.yaml).
- [C19] [Official generated TypeScript Logs API response/filter definitions](https://raw.githubusercontent.com/cloudflare/cloudflare-typescript/main/src/resources/ai-gateway/logs.ts).
- [C20] [Guardrails supported model types source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/features/guardrails/supported-model-types.mdx).
- [C21] [Official generated TypeScript model-run path, body and result envelope source](https://raw.githubusercontent.com/cloudflare/cloudflare-typescript/main/src/resources/ai/ai.ts).
- [C22] [Legacy Logs persistence, capacity and oversized-log behavior source](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/ai-gateway/observability/logging/legacy-logs.mdx).

## P5 hosted alternatives — public-source comparison, 2026-10-17

### Authority, method and disposition

The owner approved this source-only comparison of exactly three hosted services:
Azure AI Language Text PII, Google Cloud Sensitive Data Protection content inspection,
and AWS Comprehend Detect PII. Cloudflare PII remains **research-only/unqualified**;
the earlier research and preparation history above remains authoritative history.
All six families remain required: email, phone, government identifier including
**VN CCCD**, personal name, address, and medical-record identifier. VI/EN text language
and entity country/format remain separate axes. This appendix recommends an
investigation order; it adopts no provider and grants no implementation or live trial.

The research skill was read. Context7 `resolve-library-id` was used first for each
vendor. Azure resolved to `/microsoftdocs/azure-ai-docs` and its PII query supplied
first-party documentation leads. Google returned only Google Cloud SDK, and AWS
returned unrelated AWS services; those are unsuitable evidence for these PII APIs.
The fallback was unauthenticated official documentation/pricing pages only. No
credentials, account, authenticated request, inference, package/model/detector,
fixture/label, code/test, configuration or Git mutation was used. Only this dated
appendix and its source register were added. Public pages are mutable observations
on **2026-10-17**, not an entitlement or negotiated-price check.

**Recommendation (proposal): investigate Azure Text PII first for the four shared
contact/name/address families**, because the current **PII-specific** language page
explicitly includes both English and Vietnamese. Its documented taxonomy does not
establish VN CCCD or generic MRN coverage. Keep Google as the second source candidate:
it names a generic MRN detector, but its general multilingual statement does not
prove Vietnamese support for each required entity. AWS has a useful explicit text
contract, but PII supports English/Spanish, so it cannot meet the VI requirement.
**No candidate is qualified for all six families in VI/EN**, and no full-scope adapter
or trial is justified by these sources alone. [P5A01][P5A02][P5G01][P5G02][P5W01][P5W02]

### Coverage: entity, language and country must each be established

In this table, **documented** means a named built-in entity and relevant public
contract, never measured accuracy. **Unknown** is an unresolved coverage gate;
a taxonomy omission is not a measured false negative. Country-specific IDs and
medical insurance/member numbers do not establish VN CCCD or an organization's MRN.

| Required family | Azure AI Language **Text PII** | Google Sensitive Data Protection | AWS Comprehend **Detect PII** |
| --- | --- | --- | --- |
| Email | `Email`; EN/VI documented in PII language/entity pages. No per-format VI quality evidence. [P5A01][P5A02] | `EMAIL_ADDRESS` built-in; global category. Per-entity VI support/accuracy not proven by the general language statement. [P5G01][P5G02] | `EMAIL` universal type; EN supported, VI unsupported. [P5W01][P5W02] |
| Phone | `PhoneNumber`; EN/VI documented. Valid Vietnamese national/international formats remain unqualified. [P5A01][P5A02] | `PHONE_NUMBER` global built-in; specific VN formats and VI context remain unproven here. [P5G01][P5G02] | `PHONE` universal type; EN supported, VI unsupported. This is not proof of VN-format recall. [P5W01][P5W02] |
| Government ID, including VN CCCD | Many country-specific entities; no Vietnam/CCCD entry in reviewed entity inventory. API also enumerates `NationalId`/`GovernmentIssuedId`, which do not specify CCCD recognition. EN/VI language support cannot fill that country-format gap. [P5A01][P5A02][P5A03] | Country-specific government ID infoTypes and `GENERIC_ID`; reviewed inventory has no Vietnam/CCCD infoType. Generic matching cannot qualify a CCCD-specific detector. [P5G01][P5G02] | Country-specific types include US, UK, Canada and India identifiers; no VN CCCD entry. EN language support is separate from those formats; VI unsupported. [P5W01][P5W02] |
| Personal name | `Person`; EN/VI documented, with actual Vietnamese names/diacritics unqualified. [P5A01][P5A02] | `PERSON_NAME` global built-in; language-specific VI name coverage unproven. [P5G01][P5G02] | `NAME` universal type; EN supported, VI unsupported. [P5W01][P5W02] |
| Address | `Address`; EN/VI documented. No proof every VN address structure is recognized. [P5A01][P5A02] | `STREET_ADDRESS` global built-in; requires testing of fully qualified addresses. VN-format/VI coverage unproven. [P5G01][P5G02] | `ADDRESS` universal type; EN supported, VI unsupported. No VN-format qualification. [P5W01][P5W02] |
| Medical-record ID | No generic medical-record-number entity found in reviewed Text PII list. `AUMedicalAccountNumber` and other health identifiers are different types, so generic VI/EN MRN remains unknown. [P5A02] | `MEDICAL_RECORD_NUMBER` explicitly means generic MRN. Documentation describes entity-plus-context detection for types without common definitions; VI-specific MRN support remains unknown. [P5G01][P5G02] | No generic MRN type in reviewed Detect PII inventory. No inference from a different medical service; VI unsupported. [P5W01][P5W02] |

Azure's current entity page says its PII language list applies unless an entity has
an exception. This is evidence for the named Text PII entities above; it is not
borrowed from general NER or Conversation PII. Google states that country-specific
infoTypes support English and that country's languages, and **most** global
infoTypes support multiple languages; it does not enumerate VI per global detector
in the reviewed contract. AWS's API prose and developer guide specify EN/ES even
though the shared `LanguageCode` enum lists more languages. The old AWS AI service
card says English only; use the current operation-specific EN/ES contract, without
extending it to Vietnamese. [P5A01][P5A02][P5G02][P5W01][P5W02][P5W07]

### Synthetic validity gate for any later qualification

The existing 30-case P5 draft and its hashes are unchanged. As recorded in the
preparation checkpoint, its intentionally invalid VN phone/ID and invented address
are **format probes**, not valid positives that can qualify any provider. Detection
of one would not validate realistic coverage; non-detection would not establish a
provider miss on a valid entity. Google documents checksums, digit restrictions,
prefixes and contextual clues among its techniques; Azure's current contract has
entity validation enabled by default. Disabling validation to make a fabricated
value match would change the experiment. [P5G02][P5A03]

**Proposed prerequisites, not fixture edits or accepted labels:**

- Freeze an entity × text-language × country/format matrix. Put VN-format values
  in both VI and EN surrounding text, and supported non-VN formats in both
  languages where meaningful; retain unsupported cells as unavailable.
- Before new quality cases, obtain an official current VN CCCD format reference
  and a safe synthetic-data construction rule, including structural constraints;
  similarly establish current VN phone prefixes/length and address components.
  Exact valid synthetic CCCD/phone/address construction is **not established by
  this vendor-source comparison**. No real person's identifier or contact data is
  needed, and no generated value should be represented as an issued identity.
- Use syntactically valid reserved-domain email, plausible fictional names with
  diacritics, and format-realistic fictional addresses. For MRNs, explicitly define
  the fictional organization's record-number grammar and context in each language;
  an insurance/member number cannot stand in for an MRN. A globally valid MRN
  grammar is not established: Google explicitly notes the lack of a common
  definition and dependence on context. [P5G02]
- Pair each valid positive with nearby invalid-format/field-name-only controls,
  preserving the current distinction between entity presence/type and disclosure
  authority. The owner must review every new/revised label and exact digest before
  any quality trial. Existing reserved/invalid examples remain supplementary probes.

### Saved-text input, completion and correlation

All three have a documented direct text inspection surface: Azure
`PiiEntityRecognition` receives document `id`, `language`, `text`; Google
`content:inspect` receives `item` (`ContentItem.value` for strings); AWS
`DetectPiiEntities` receives `Text` and `LanguageCode`. These are classification
surfaces suitable to investigate for an already selected saved output; no answer
regeneration or proxy replay is required by these contracts. [P5A03][P5G03][P5G04][P5W02]

| Candidate | Native result/completion contract | Version and region correlation limits |
| --- | --- | --- |
| Azure Text PII | HTTP 200 task result contains per-document `id`, `entities`, `warnings`; result also has per-document `errors` and `modelVersion`. A failed/missing document cannot be treated as empty entities. No separate truncation boolean is documented in the reviewed PII result. [P5A03] | Request `modelVersion` is distinct from API version; current lifecycle lists Text PII GA `2026-05-01` and warns predictions may change with models. Record requested and returned versions plus exact resource endpoint/region. [P5A03][P5A04][P5A06] |
| Google content inspection | `InspectResult` has findings and `findingsTruncated`. True means an arbitrary subset may have been returned because input/resources exceeded bounds. Empty findings are insufficient without successful, complete, correlated response and false/default-false truncation under validated protobuf JSON handling. [P5G05] | `InfoType.version` is optional and only some types have selectable versions. Capture the exact requested detector list/versions, likelihood/config digest and processing location; no single immutable model build is promised here. Regional endpoints additionally constrain transit to the region. [P5G06][P5G07][P5G08] |
| AWS Detect PII | HTTP 200 returns `Entities` spans/type/score; named 400 errors include invalid input, excessive text size and unsupported language; internal failure is 500. No truncation/completed flag appears in this operation's schema. [P5W02] | Request/response schema exposes no model-version parameter or model-build identifier. Capture selected regional endpoint, operation/API contract, SDK/native request metadata and time; this cannot create an immutable model pin. Published endpoint availability is separate from PII-language coverage. [P5W02][P5W03] |

**Proposed negative-evidence rule:** only a successful validated response for the
entire exact selected text and requested detector population can become a
*completed no-findings observation*. Bind original UTF-8 hash/length, native request
correlation when available, language/country axes, region, API/model/config identity
and completion evidence. Keep errors, timeouts, ambiguous sends, unknown versions,
missing documents, warnings implying partial processing and truncation unavailable.
Respect protobuf defaults rather than mistaking an omitted false/empty field for
an error, but never treat an absent result envelope as a successful empty result.
None of this qualifies a negative for an unsupported family, proves PII absence,
or accepts a metric. Azure partial-document errors and Google truncation specifically
make a bare HTTP success or empty list inadequate. [P5A03][P5A05][P5G05]

### Retention, training and logs

| Service/operation | Source-established behavior | Remaining gate |
| --- | --- | --- |
| Azure Text PII | Language data stays in the deployed resource's region; aggregate usage telemetry is collected. General input debugging retention is up to 48 hours, preventable with `loggingOptOut`; PII defaults it to true, also shown in the REST schema. [P5A03][P5A06] | Explicitly retain `loggingOptOut=true` in any reviewed future packet. These sources do not establish a separate blanket training-use prohibition or all customer/proxy/diagnostic-log retention. Account settings and actual resource location were not checked. |
| Google `content` methods | Request config/payload processed synchronously in memory, not stored or cached on Google Cloud; this differs from persisted jobs/templates/exports. `InspectContent` has a Data Access audit-log category. [P5G09][P5G10] | No payload/result logging or training-use guarantee beyond these explicit statements is inferred. Verify applicable terms, actual audit settings and caller/proxy retention before any real-data request. Memory-only processing does not prove that all surrounding logs are empty. |
| AWS **Detect PII** | The current FAQ excludes **Amazon Comprehend Detect PII** and Medical from its general input-storage/improvement statement. The Detect PII service card explicitly says it does not train on customer content. `DetectPiiEntities` is CloudTrail-loggable. [P5W04][P5W05][P5W07] | Do not transfer the generic Comprehend training statement to Detect PII. The reviewed operation-specific evidence still does not prove a precise retention TTL, complete zero-retention policy, or absence of payloads from every log. FAQ regional-storage prose is generic and does not settle the operation-specific policy. |

No provider/account policy was changed, no log was opened, and no actual data was
submitted. A future synthetic-only trial still needs exact account/region, logging,
retention and cost authority; this comparison supplies none.

### Dated public prices, free tiers and input bounds

Prices below are public source observations in **USD**, not account quotes. Do not
substitute generic NER, storage scanning, transformation, or Contains PII prices
for the selected text inspection operation.

| Candidate | Exact public price/free-tier evidence | Limits relevant to a bounded saved-text trial |
| --- | --- | --- |
| Azure Text PII | Public Free-Web row includes PII at **5,000 text records/month**. Records are billed in rounded-up **1,000-character** units per document. Standard paid PII price cells rendered **`$-`**, so a current paid unit rate is **unknown**, requiring an exact region/currency/offer quote before a paid ceiling can be frozen. Shared free-allocation usage/eligibility is account unverified. [P5A07] | Synchronous preconfigured features: **5,120 text elements/document**, PII **5 documents/request**, **1 MB/request**. Oversized synchronous documents return document errors while valid peers may continue. F0/S0 published rates **100 requests/s, 300/min**; S/Multi-service **1,000/s, 1,000/min**. These ceilings do not establish remaining quota. [P5A05] |
| Google `content.inspect` | Content inspection: first **1 GiB/month/account free**; over 1 GiB through 1 TiB **$3/GiB**; above 1 TiB **$2/GiB**. **1 KB minimum billed/request**; billing information required even before free usage. Use these content rates, not $1/GiB storage-job rates. [P5G11] | **0.5 MB/request**, **3,000 findings/request**; **10,000 requests/min/project** total. Per-region requests via global endpoint **600/min**; dedicated regional endpoint **100/min**. Actual project quota remains unverified; finding truncation is separately checked. [P5G12][P5G05] |
| AWS Detect PII | Current official Detect PII pricing example uses **$0.0001/100-character unit**, **3 units (300 characters) minimum/request**. Contains PII's example is **$0.000002/unit** and is a different operation. Published free tier: **50,000 units (5M characters)/API/month**, **12 months** from first Comprehend request. Current selected-region/account rate, tier usage and eligibility remain unknown; dynamic regional tables were not an account quote. [P5W06] | Direct text maximum **100 KB UTF-8**. Published DetectPiiEntities throttle: **200 TPS us-east-1**, **100 TPS us-west-2**, **50 TPS other supported regions**, per account/current region, adjustable. VI rejection remains a coverage issue, not a quota issue. [P5W02][P5W03] |

**Cost proposal:** once a candidate's coverage gaps and labels are resolved, freeze
exact serialized input sizes, billable units, serial call count, no-retry/fallback
rule and a paid ceiling using the actual permitted region/offer. Free-tier existence
does not prove remaining allowance or authorize billing/account setup. Google uses
bytes/GiB; Azure/AWS use character records/units, so Vietnamese UTF-8 byte lengths
must not be reused as character counts. The published units above support separate
cost calculations, not an interchangeable per-token estimate. [P5A07][P5G11][P5W06]

### Decision frontier

Keep Cloudflare and all three alternatives unqualified. The source-supported next
choice is whether to authorize **additional offline preparation for Azure's documented
EN/VI subset while retaining explicit CCCD/MRN gaps**, or resolve the missing full-scope
coverage contract first. Google merits a vendor-specific VI/CCCD clarification before
it can compete for the full requirement; AWS's documented language boundary already
rules out VI. Neither a custom regex/dictionary nor translation is adopted as a
coverage substitute. No unsupported family is dropped, counted clear, or silently
removed from a later denominator. [P5A01][P5A02][P5G01][P5G02][P5W01][P5W02]

No new valid-format fixtures, accepted labels, code, tests, provider requests,
account inspection or integration evidence were produced. Source completeness,
provider availability, model quality, CCCD/generic MRN coverage and actual trial
cost/retention remain separate gates; this appendix completes only the approved
public-source comparison.

### Alternative-candidate source register — reviewed 2026-10-17

All entries are official public sources; no search-result snippet alone is used as
an operation contract. The Azure pages displayed an authorization banner, but their
public article bodies were readable without login. The data-limit article's complete
public HTML body was also read through an unauthenticated HTTPS GET because the
search renderer omitted its tables. A failed raw GitHub path and unavailable page
URLs supplied no evidence. No live infoTypes inventory API was called.

- [P5A01] [Azure PII-specific language support, Text PII table (updated 2026-08-17)](https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/language-support).
- [P5A02] [Azure recognized Text PII/PHI entities and language-exception rule](https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/concepts/entity-categories).
- [P5A03] [Azure Analyze Text REST contract, 2026-05-01: PiiTaskParameters, PiiResult and per-document results/errors](https://learn.microsoft.com/en-us/rest/api/language/analyze-text/analyze-text/analyze-text?view=rest-language-analyze-text-2026-05-01).
- [P5A04] [Azure model/API lifecycle and supported version tables](https://learn.microsoft.com/en-us/azure/ai-services/language-service/concepts/model-lifecycle).
- [P5A05] [Azure Language data/document/rate limits and oversized-document error behavior](https://learn.microsoft.com/en-us/azure/ai-services/language-service/concepts/data-limits).
- [P5A06] [Azure Language data privacy: region, telemetry, temporary storage and PII logging opt-out](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/language-service/data-privacy).
- [P5A07] [Azure Language public pricing: Free-Web PII row, billing record definition and dynamically unrendered paid rates](https://azure.microsoft.com/en-us/pricing/details/language/).
- [P5G01] [Google built-in infoType inventory and general/specific type mappings](https://docs.cloud.google.com/sensitive-data-protection/docs/infotypes-reference).
- [P5G02] [Google infoType concepts: detector techniques, language support, contextual IDs/MRNs and fully qualified addresses](https://docs.cloud.google.com/sensitive-data-protection/docs/concepts-infotypes).
- [P5G03] [Google projects.locations.content.inspect REST method](https://docs.cloud.google.com/sensitive-data-protection/docs/reference/rest/v2/projects.locations.content/inspect).
- [P5G04] [Google ContentItem schema, including direct string value](https://docs.cloud.google.com/sensitive-data-protection/docs/reference/rest/v2/ContentItem).
- [P5G05] [Google InspectResult and findingsTruncated contract](https://docs.cloud.google.com/sensitive-data-protection/docs/reference/rest/v2/InspectResult).
- [P5G06] [Google InfoType optional version field](https://docs.cloud.google.com/sensitive-data-protection/docs/reference/rest/v2/InfoType).
- [P5G07] [Google console infoType version-selection limitations](https://docs.cloud.google.com/sensitive-data-protection/docs/manage-infotypes-console).
- [P5G08] [Google processing location and regional endpoint behavior](https://docs.cloud.google.com/sensitive-data-protection/docs/specifying-location).
- [P5G09] [Google data security: content-method memory processing versus persistence](https://docs.cloud.google.com/sensitive-data-protection/docs/data-security).
- [P5G10] [Google audit logging: InspectContent Data Access category](https://docs.cloud.google.com/sensitive-data-protection/docs/audit-logging).
- [P5G11] [Google content-inspection pricing, minimum billed size and billing requirement](https://cloud.google.com/sensitive-data-protection/pricing).
- [P5G12] [Google quotas and direct-content limits](https://docs.cloud.google.com/sensitive-data-protection/limits).
- [P5W01] [AWS PII languages and universal/country-specific entity inventory](https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html).
- [P5W02] [AWS DetectPiiEntities operation contract, UTF-8 limit, results and errors](https://docs.aws.amazon.com/comprehend/latest/APIReference/API_DetectPiiEntities.html).
- [P5W03] [AWS Comprehend regional endpoints and per-operation quotas](https://docs.aws.amazon.com/general/latest/gr/comprehend.html).
- [P5W04] [AWS Comprehend FAQ: explicit Detect PII exception to generic storage/improvement/training statement](https://aws.amazon.com/comprehend/faqs/).
- [P5W05] [AWS Comprehend CloudTrail action inventory](https://docs.aws.amazon.com/comprehend/latest/dg/logging-using-cloudtrail.html).
- [P5W06] [AWS Comprehend pricing, Detect versus Contains examples, unit minimum and free tier](https://aws.amazon.com/comprehend/pricing/).
- [P5W07] [AWS Detect PII AI service card: older English-only language statement and explicit no-training commitment](https://docs.aws.amazon.com/ai/responsible-ai/comprehend-detectpii/overview.html).
