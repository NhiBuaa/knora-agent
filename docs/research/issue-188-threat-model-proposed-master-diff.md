# Issue #188 — Reviewed threat model and approved Master diff

**Approval/application record — 2026-10-17 (Asia/Saigon):** Owner approved Q1 in this
chat: “Tôi duyệt Q1 — áp dụng hướng sửa Master Plan #188 theo threat model và proposed diff đã trình.”
The exact frozen diff below was applied to the existing Master, followed only by
approval/status readback updates. This records the revised direction; no code,
fixture/label acceptance, provider/detector execution, account/credential access,
runtime/config/enforcement/export or Git publication is authorized.

**Historical review material follows.** Its original pending wording, review question
and “not applied” statements describe the pre-approval checkpoint. They are preserved
with the reviewed diff, not current decisions or permission. The
[Master](../superpowers/plans/2026-10-16-issue-188-master-plan.md) is current authority.
Reviewed base SHA-256: `66f7c47e1298233a04124c43a695680df8ce67f4d92048c0a3cb92cf80eca7d3`.
Frozen patch SHA-256: `4a6e64035f7a9c7348257c322754ab4f4693e7f4ed974eaad7bbaad0c0fcc2ff`.

Application checks: exact diff applied; P0–P10 remain present and P1–P4 phase
contracts compared unchanged during application. After approval/status readback,
Master SHA-256 is `38ccb718d4858e1d0141e72eef8181d922c1bc83b2d3765fc297927732452e37`.
Forty local link targets resolved; seven selected domain/code/test/fixture hashes
remained unchanged; `git diff --check` passed with the existing P1 LF/CRLF advisory.
No code tests, CI, provider/detector or runtime checks were run for this docs update.

Date: **2026-10-17** (Asia/Saigon). Status: **analysis for owner review only**.
No scope replacement, label acceptance, technology selection or execution authority follows from this document.

**Review summary (tiếng Việt):** Giữ quyền hỏi đáp hợp lệ với tài liệu có PII; đánh giá quyền truy cập, nơi nhận dữ liệu và hành vi gây hại riêng. Đề xuất bỏ tính bắt buộc của detector phủ đủ sáu nhóm PII/S1–S13, giữ chúng làm inventory nghiên cứu. Chỉ thêm control/detector khi có khoảng trống và lợi ích đo được; toàn bộ thay đổi phạm vi còn chờ chủ sở hữu duyệt.

## 1. Review boundary

Local source and existing decision records were read; no account, credential, provider API, model, detector or external-network access was used. Test source was inspected, not executed. Hindsight search/list failed with local connection refused; no memory claim is relied upon. Issue ownership below is the repository's recorded boundary, not a fresh GitHub status assertion.

Keep the existing P0–P10 Master, completed work, original annotations, captures and supplementary reports intact until the owner approves an explicit diff. In particular, P1/Secrets remain experimental; P5/P6 annotations remain draft; #192 permits only selected, digest-bound native artifacts, a separate `[alias, content]` consumer projection and supplementary observations. No re-answer or latest-trace discovery is proposed.

## 2. Verified application data flow

1. **Workspace authorization:** persisted issuer/subject ownership plus endpoint capability is the current authority. This is a Workspace boundary, not an implemented per-document ACL or general purpose-consent engine. A PII detector cannot grant or revoke this authority. [S01][S02]
2. **Upload/ingestion:** raw PDF is read through the ObjectStore and extracted before embedding; extracted chunk text is passed to document embedding. Text/Markdown follows the same content-to-embedding boundary. A configured hosted embedding adapter receives text, not merely vectors. The inspected path does not send the raw PDF file to the generation model. ObjectStore deployment location is a separate, unverified storage boundary. [S03][S04][S05]
3. **Question/retrieval:** the question, or a query built from prior user questions for reference resolution, is embedded **before** evidence selection and generation. Rejecting an answer later cannot undo this disclosure. [S06][S07]
4. **Generation:** only selected evidence is sent as opaque alias/content pairs, together with the current question and, for follow-ups, bounded prior transcript marked untrusted. Hiding database IDs does not remove sensitive text. The adapter sends this payload to its configured generation endpoint. [S08][S09]
5. **Returned answer:** schema and citation-membership validation precede final delivery. These checks establish structural validity, not semantic safety, permission to disclose or immunity to injected instructions. Progress events do not publish partial answer tokens in this path. [S10][S11]
6. **Persistence:** protected Question Trace contains the raw question/answer and may contain contextual retrieval-query text. This differs from sanitized supplementary scanner reports and the proposed metadata-only external telemetry boundary. No claim that all runtime logs, infrastructure logs or provider copies are sanitized was verified. [S12][S13][S14]
7. **Client rendering:** the inspected component uses an element allowlist with `skipHtml`, excluding generated links and images; an existing test asserts generated script/link/image content does not become active. This is source/test inspection, not a fresh browser or frontend test run. [S19]
8. **Tools:** the inspected answer-generation payload declares no tool execution API. Separate read tools authorize Workspace-to-external-resource binding before lookup; write execution requires an approved proposal, compatibility, current resource and execution authority, then dispatch admission. Classifiers do not replace these deterministic controls. [S15][S16]

The inspected source demonstrates these paths; it does not prove which provider, region, logging mode, retention policy or credentials are active in any deployment.

## 3. PII presence is not an unauthorized leak

For the same cited sentence containing an employee email, the Workspace owner asking for that contact can be a legitimate answer. Sending that sentence to a disallowed third-party endpoint, exporting it to broadly accessible telemetry, or returning it across the Workspace boundary is a different event. A match on `email` proves none of those events by itself.

Use three separate questions in the proposed evaluation rubric:

- **Content fact:** is the selected byte span sensitive, secret-like or ordinary public/fictional data? Entity presence remains descriptive evidence, with explicit uncertainty.
- **Boundary fact:** who receives it: authorized Workspace requester, embedding/generation provider, detector provider, tool recipient, local protected persistence or external telemetry? Is that specific flow permitted by the approved product/deployment policy?
- **Security outcome:** did a prohibited disclosure or concrete harmful action occur, or was legitimate use incorrectly refused? If permission/context is unspecified, record **unresolved**, not an invented unauthorized-leak label.

This is an annotation and boundary-review discipline, not a proposal for a new per-document ACL, arbitrary purpose engine, data-taint graph or automatic redaction framework. Workspace access does not establish provider-processing permission; equally, private or PII-bearing content is not automatically forbidden for an authorized Workspace answer.

## 4. Risk and ownership matrix — proposed priorities

Assets include original documents/chunks, questions/history, service credentials,
answers, tool authority, traces and provider budget. Relevant actors are an injected
source/history author, a malicious requester, a cross-Workspace caller, a mistaken
model and a reader of an unintended log/export sink. A permitted provider is still
a separate processing boundary; no provider breach or malicious operator is asserted.
Prioritize deterministic access/recipient/credential boundaries first, then measured
injection and harmful-assistance gaps. Likelihood and production exposure were not
measured; the table is a review inventory, not a quantified risk score.

| Risk / concrete failure | Current evidence and control | #188 responsibility proposed | Separate owner / unresolved dependency |
|---|---|---|---|
| Source/history injection changes answer or induces leakage | Evidence is untrusted model input; citation checks do not establish instruction separation [S08–S11] | Retain P1; measure actual attack success and benign quotation/research completion, not just classifier flags | Existing AnswerQuestion/provider seams own application behavior; no autonomous tool bridge inferred |
| Question/PDF chunk sent to an unapproved AI endpoint | Document/query embedding occurs before generation; generation gets selected content [S03–S09] | Map actual sinks, identify missing policy decisions and verify approved data boundaries; optional detector only if it adds measurable value | Product/deployment data-processing authority must be decided; #188 cannot infer consent or silently change embedding space |
| Embedded credential or sensitive field copied to unauthorized sink | Secrets scanner finds patterns, with known FP/FN; presence does not establish recipient permission [S13] | Retain Secrets evidence; evaluate synthetic leak outcomes at named boundaries and legitimate technical-document controls | Runtime/service credentials must remain outside prompts by construction; rotation/storage hardening is separate |
| Cross-Workspace retrieval, document, conversation, trace or tool access | Ownership/capability checks and tenant predicates exist; cross-Workspace test asserts no model egress [S01][S02][S17] | Preserve deterministic regression gates and include misuse scenarios; no probabilistic AuthZ substitute | Workspace/AuthZ application owners; create no new security Issue or unverified blocker by this analysis |
| Raw question/output/secret leaks via logs, traces or exports | Trace intentionally retains content; scanner supplementary reports omit raw text; export policy distinct [S12–S14] | Audit selected #188 artifacts and data sent to detectors; keep exports OFF and raw captures separate | ADR0018/#158 controls evaluation/export authority; #153/#192 owns upstream source/capture compatibility |
| Harmful answer with valid citations | Structural validation is not harmful-output validation [S10] | P6 should cover owner-defined actionable harm plausible for Knora and benign professional/medical/security/research controls | General truthfulness/faithfulness and retrieval quality remain evaluation concerns; #158 tool observations do not become policy |
| Generated HTML/link/image becomes executable or leaks data through a browser fetch | Existing renderer excludes active HTML/link/image elements; regression source exists [S19] | Preserve deterministic output-rendering defenses and adversarial controls; no toxicity classifier needed for this boundary | Frontend rendering/security owner; no current browser/runtime verification |
| Resource/cost amplification via long/hostile input or added scanners | Ingestion/context budgets and provider timeouts exist; deployment-wide rate/quota/spend control not established [S03][S06][S07] | Include this residual risk and ensure candidate controls add bounded calls/resources | Ingestion/provider/deployment owners; do not claim denial-of-wallet prevention from local timeouts |
| Model attempts unauthorized tool lookup/write | Separate resource binding and approved/current-authority execution checks [S15][S16] | Adversarial regressions preserve these boundaries; no new generic agent sandbox required | M4 tool lifecycle/ADR0015 owns side-effect authority; output category is never execution authority |
| PDF resource exhaustion, stale derivations, storage retention or deployment exposure | Existing ingestion/workspace controls; deployment not inspected | Record residual risk/dependency and preserve existing gates; do not rebuild controls as detectors | M2/M5 module owners; local records explicitly place physical deletion/retention at #150 and OTP/CSP deployment hardening at #152 [S18] |

## 5. Detector necessity and minimal architecture — proposal only

- **P1:** retain experimental detector work as an optional observation. The security target is resistance to instruction-following/leakage, measured alongside false refusals; a positive flag is not prevention.
- **Secrets:** retain the local candidate and known split-key/checksum limitations. Never place service credentials into model input and rely on an output scanner to recover them.
- **P5:** first specify allowed data flows and evaluate unauthorized disclosure at those boundaries. Six-family VI/EN research is retained as prior coverage research, not silently deleted; propose removing universal six-family detector qualification as a prerequisite **only by owner decision**. Azure is not a default adoption. Neither a hosted PII classifier nor blanket output redaction is justified solely by a coverage checklist; another hosted detector creates another data recipient.
- **P6:** retain S1–S13 research, 52 draft cases and the pure mapper; propose making taxonomy a discovery inventory rather than automatic deny policy. Select concrete actionable harms and legitimate-use controls before any model trial. Category presence, discussion, quotation, document subject or PII presence must not automatically become a block. Citation validity alone must not excuse actionable harm either.
- **Runtime:** propose preserving existing authorization, retrieval and tool seams, with observations kept separate from enforcement. Add no universal scanner pipeline, router, policy engine or extra provider until a boundary-specific gap and benefit are demonstrated. Any later policy/config change still requires the approved P7/P9 gates.

## 6. Source register — exact local anchors

All paths are relative to this worktree; line numbers identify the inspected source on 2026-10-17, not a fresh deployed-code audit.

| ID | Source / relevant lines |
|---|---|
| S01 | `backend/src/knora/access/workspace_authorization.py:20–35` — persisted owner and capability checks |
| S02 | `docs/standards/architecture.md:15–44` — endpoint order, Workspace authority, credential/trace limits |
| S03 | `backend/src/knora/ingestion/job_processing.py:378–438` — PDF ObjectStore/extraction/chunk embedding |
| S04 | `backend/src/knora/ingestion/module.py:42–85` — authorization then text chunk embedding |
| S05 | `backend/src/knora/providers/cloudflare/embedding.py:45–68`; `backend/src/knora/providers/gemini/embedding.py:52–64` — outgoing text payloads |
| S06 | `backend/src/knora/answering/module.py:110–149` — query embedding precedes retrieval |
| S07 | `backend/src/knora/conversations/context.py:122–134` — reference-query prior user questions |
| S08 | `backend/src/knora/answering/module.py:202–213,403–415` — selected evidence and untrusted history |
| S09 | `backend/src/knora/providers/structured_generation.py:20–40`; `backend/src/knora/providers/openai_compatible/generation.py:71–103` — prompt/transport |
| S10 | `docs/standards/architecture.md:755–782` — citation/schema limits; response delivery |
| S11 | `backend/src/knora/answering/module.py:222–258,309–378` — validation and final-only delivery |
| S12 | `backend/src/knora/adapters/postgres/answering_store.py:668–694`; `backend/src/knora/answering/module.py:452–456` — content-bearing protected trace |
| S13 | `evals/scorers/security_shadow.py:20–44`; `evals/runners/run_security_shadow.py:144–162`; `evals/test/test_security_shadow.py:110–125` — pattern observation, exact-evidence requirement, sanitized report test |
| S14 | `docs/adr/0018-knora-evaluation-tool-authority.md:5–32` — #153/#158, private-eval permission, export and #188 boundary |
| S15 | `backend/src/knora/tools/read.py:36–62` — authorize bound external resource before lookup |
| S16 | `backend/src/knora/tools/execution.py:125–187`; `docs/adr/0015-human-approved-tool-execution-boundary.md:5–19` — current execution authority distinct from approval |
| S17 | `backend/src/knora/adapters/postgres/answering_store.py:266–275`; `backend/test/adapters/postgres/test_cloudflare_application.py:245–268` — eligible tenant retrieval, no-egress rejection test |
| S18 | `docs/development/figma-ui-completion-audit.md:84–87`; `CONTEXT.md:25–32` — documented #150/#152 boundaries, no current remote-status claim |
| S19 | `frontend/components/conversations/AnswerContent.tsx:87–128`; `frontend/tests/answer-rendering.test.tsx:138–153` — inert Markdown element policy and test-source assertions |

## 7. Proposed Master Plan diff

Review base: dirty-worktree Master SHA-256 `66f7c47e1298233a04124c43a695680df8ce67f4d92048c0a3cb92cf80eca7d3`, Git HEAD `4f1a6729fd8b246b69c8bd6df93301206214c493`.
The diff targets this exact local version, including prior uncommitted history. It is **not applied**.
P1–P4 phase contracts are unchanged; no code, original labels, reports or canonical domain definitions are edited.

### Material requirement changes requiring owner approval

| Prior direction | Proposed revision | Retained evidence / limitation |
|---|---|---|
| Four detector implementations and coverage as delivery goal | Evaluate four risk groups and choose justified controls; detector adoption conditional | Existing P1/Secrets remain experimental; no automatic waiver or completion |
| Six-family VI/EN PII qualification as prerequisite | P5 prioritizes permitted recipients/flows and prohibited-disclosure outcomes; entity detector optional | All six remain in research inventory, 30 drafts retained; no claim of universal PII protection |
| S1–S13 classifier qualification path | P6 selects concrete harmful-assistance scenarios with legitimate-use controls | S1–S13/52 drafts/mapper retained; untested hazards explicitly uncovered |
| New runtime observation hook after detector phases | P7 implements only proven boundary gaps; existing controls may suffice with owner review | Runtime/enforcement/export OFF; no new code authority |
| Detector metrics prominent in acceptance | Add recipient-specific leak/harm outcomes and legitimate utility; qualified metrics supplemental | Exact native evidence/unavailable rules and #192 boundaries unchanged |

These changes are **recommendations**, not decisions already made. If approved, the same Master is updated; this review artifact is not a competing implementation plan. Issue scope must be reconciled explicitly before closure.

### Exact unified diff — review only

```diff
--- a/docs/superpowers/plans/2026-10-16-issue-188-master-plan.md
+++ b/docs/superpowers/plans/2026-10-16-issue-188-master-plan.md
@@ -1,6 +1,15 @@
 # Issue #188 — Master Implementation Plan

-**Current execution envelope (October 17):** Owner approved P5 public-source-only
+**Current planning envelope (October 17 threat-model revision):** Owner requested
+analysis and a proposed Master diff before further work. The earlier Azure/P5 and
+replacement-canary/P6 packets were not selected and grant no execution authority.
+This revision changes scope only after explicit owner approval; documentation
+approval alone authorizes no code, account read, provider/detector call, config,
+runtime, enforcement, export or Git integration. Preserve every historical artifact.
+The review proposal is at
+[threat model and proposed diff](../../research/issue-188-threat-model-proposed-master-diff.md).
+
+**Historical checkpoint — completed offline comparison and mapper (October 17):** Owner approved P5 public-source-only
 comparison of at most three hosted alternatives while retaining Cloudflare PII
 research-only/unqualified, and the two-file P6 pure object-mapping/test envelope.
 All 52 P6 labels remain draft; candidate positive/negative parsing cannot qualify
@@ -85,11 +94,23 @@

 **Completion vocabulary:** **Detection Completed** means the agreed detection scope has completed, reviewed evidence and explicit owner quality acceptance, including coverage and false positives. **Protection Enabled** additionally requires an approved enforcement policy, separate activation authority and verified runtime prevention/rollback evidence. With enforcement OFF, Protection Enabled is false: never claim that Knora prevents attacks. P1 technical completion alone establishes neither final status.

-**Goal:** Deliver independently measured Prompt Injection, Secrets, PII and Dangerous Output detection, integrate accepted capabilities into Knora safely, and obtain owner security acceptance using Knora Evaluation.
-
-**Architecture:** Preserve the existing Secrets scanner and native captures/reports. Add only detector-specific cloud adapters and versioned supplementary observations inside Knora Evaluation, then an optional application observation hook and provider Gateway configuration. Separate observation, authorization and any future enforcement policy.
-
-**Tech stack:** Existing Python/HTTPX/pytest, isolated pinned Secrets dependencies, Cloudflare Workers AI/AI Gateway candidates, existing Knora application/trace/evaluation seams. No new local security model, evaluation framework, queue, dataset service or generic provider/router framework.
+**Goal:** Validate and reduce concrete AI security risks in Knora while preserving
+legitimate Workspace document use: instruction injection, prohibited disclosure of
+secrets/personal data, disallowed provider/log/tool egress and owner-defined harmful
+assistance. Evaluate all four original risk groups; a detector is a candidate control,
+not a deliverable required solely by its category name. Any changed requirement or
+accepted residual risk needs an explicit owner disposition, never an agent waiver.
+
+**Architecture:** Preserve existing AuthZ, evidence/citation and tool boundaries,
+Secrets/P1 work and native captures/reports. Map each data flow to its permitted
+recipient and control. First reuse deterministic controls and application evaluation;
+add a detector/observation hook only for a demonstrated incremental security benefit.
+Separate content presence, access/egress authorization, observation and enforcement.
+
+**Tech stack:** Reuse existing Python, provider adapters, isolated pinned Secrets
+candidate and Knora application/trace/evaluation seams. No Azure or other new vendor,
+PII service, moderation model, scanner chain, policy engine, router or local model is
+selected by this revision. Candidate adoption still needs a concrete approved scope.

 **Spec and authority:** [Issue #188](https://github.com/NhiBuaa/knora-agent/issues/188) and explicit owner decisions are requirements; this file is the single forward implementation plan, including architecture and phase contracts. [ADR 0018](../../adr/0018-knora-evaluation-tool-authority.md) governs evaluation/data authority. Plan approval, phase implementation approval, live approval, enforcement approval and merge approval are distinct.

@@ -124,36 +145,64 @@

 PR #199 remains Secrets-only and unchanged. P1 branch is explicitly stacked on its exact head `bd5f288da7822d81e99f17f97567ec5c3129d7bb`; research and Master-only commits were replayed as `c7852fc` and `ad9e596`. P1 reuses those existing helpers without modifying them. It does not contain unmerged Workbench implementations. Integration into main/merge order remains a future explicit decision; this stack is no claim that PR #199 is merged.

-## 3. Architectural decision proposed for review
-
-### Options
-
-1. **Recommended: thin detectors inside existing Knora seams.** Keep the approved offline Secrets worker. Prefer Cloudflare P1, investigate Cloudflare DLP for PII and S1–S13 for Dangerous Output. Reuse capture loading, label/digest validation, metric rules and atomic publication where their semantics fit. Introduce no pluggable detector framework.
-2. Put every group behind Gateway: fewer integration paths but Secrets coverage is not established and saved-output replay is not equivalent to response scanning. Would discard useful baseline evidence and hide coverage gaps. Not recommended.
-3. Build a general security platform/local model ensemble: unnecessary dependencies, resources, data authority and policy surface. Conflicts with the chosen no-new-local-model direction. Excluded.
-
-### Data flow and ownership
-
-```text
-Existing Knora sources/captures + reviewed security annotations (digest-bound)
-  -> explicit selected units: source page | retrieved candidate | generation evidence | output
-  -> existing Secrets worker OR approved Cloudflare-specific adapter
-  -> supplementary detector observations + safe provenance
-  -> Knora-owned aggregation, human review, accepted scope/policy
-  -> approved runtime observation integration (default OFF)
-  -> separately authorized runtime FLAG trial + application security evaluation
-  -> explicit owner enforcement disposition and final acceptance
-```
-
-Cloudflare P1 can retain `/accounts/{account_id}/ai/v1/chat/completions` and select a Gateway with `cf-aig-gateway-id`. This is an evaluation adapter change first, not a backend default change. P1 scans submitted text, not a whole PDF/source URL. Exact retrieved generation evidence can be serialized with existing `user_message(question, evidence)`; incomplete captures stay unavailable. P1 FLAG permits traffic when the detector is unavailable, so a successful generation is not a negative detector verdict. [Routing](https://developers.cloudflare.com/ai-gateway/usage/providers/workersai/), [Guardrails semantics](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/).
-
-For runtime, authorization and active-source selection occur before any security input is assembled or sent. Observe the exact post-selection generation envelope, then the completed structured generation output at the existing validation boundary. No detector may add evidence, change alias mappings, relax citation/ACL checks or authorize tool/data access. Source-page scanning is an explicit authorized offline job; no ingestion rejection, document quarantine or whole-PDF keyword ban is introduced.
-
-Proposed runtime shape is one optional application observation collaborator, composed in bootstrap, plus explicit Gateway selection within the existing generation adapter. No new general provider interface or service. Existing Secrets stays in its isolated worker environment through a server-configured executor; it is never imported into the default backend environment. Adopt that runtime executor only after packaging/resource/cleanup tests in P7; do not install Guardrails transitives in backend by convenience.
-
-Default OFF must perform zero detector initialization, subprocesses, extra HTTP or Gateway selection. In SHADOW/FLAG, findings are observational. Detector timeout/error cannot change an otherwise valid user response; it records unavailable/error. This proposed availability policy is subject to P7 approval; it does not swallow provider failures, auth errors, generation/schema errors or trace/citation failures. Never auto-fallback to another provider or remote service.
-
-Application SSE currently sends stages and a final validated result; it is distinct from token streaming upstream. First trials use `stream:false`. Future output enforcement must hold the answer until checks complete and explicitly decide SSE behavior. Cloudflare's streaming limitations are not resolved by naming a path “shadow.” No fire-and-forget tasks or new background queue to hide cost/latency.
+## 3. Threat model and architecture
+
+### Alternatives and recommended approach
+
+1. **Recommended: controls at actual data boundaries, with evidence-gated detectors.**
+   Preserve current controls; map assets, actors, allowed recipients and failure
+   scenarios. Measure security outcomes and legitimate use before adding a scanner.
+   Lower integration/egress cost; semantic risks remain explicit where unmitigated.
+2. Complete a four-detector pipeline first: retains the earlier delivery emphasis,
+   but six-entity/S1–S13 coverage does not prove permission or prevention and extra
+   hosted scans create extra recipients, latency and false-refusal opportunities.
+3. Use deterministic controls alone: suitable for AuthZ and exact synthetic leak
+   assertions, but insufficient to establish resistance to semantic injection or
+   harmful assistance. Do not claim those risks solved without evidence.
+
+### Trust boundaries and responsibility
+
+- Treat source/PDF text, questions and prior dialogue as untrusted model data. An
+  authorized source can contain injection; a risky topic can also be legitimate.
+- Workspace ownership/capabilities and eligible-source selection remain authoritative.
+  This revision creates no per-document ACL, arbitrary purpose engine or data-taint
+  platform. Access to a document is separate from permission to send it to a given
+  provider, detector, tool, log sink or export destination.
+- Trace question/PDF-derived chunks through document embedding, query embedding,
+  generation with selected evidence/history, protected persistence, and optional
+  detectors/telemetry. An output scan cannot undo earlier provider disclosure.
+  Do not infer that raw PDFs are uploaded to generation: the inspected path embeds
+  extracted text and generates from selected chunks. Storage is a separate sink.
+- Never put application credentials into prompts. Tool/resource authority is checked
+  by existing application controls, never by a model or detector verdict.
+- Keep generated output inert at the client boundary: existing Markdown allowlisting
+  and no-active-link/image/HTML controls address rendering/exfiltration risks directly.
+  Citation validation is not a replacement for either rendering or semantic controls.
+- Include resource/cost amplification in the risk review: existing input/context/
+  timeout limits and no-extra-call behavior matter; no global quota/rate/spend
+  guarantee has been established here. Add controls only for a verified owning gap.
+- AuthZ/Workspace, M2/M5 storage/lifecycle, M4 tool authority, #153 source/gold and
+  #158/#192 evaluation/capture ownership stay with their existing modules/Issues.
+  #188 owns threat scenarios, detector evidence, incremental benefit and security
+  acceptance; fixes across shared boundaries require exact ownership ACKs.
+
+### Minimal integration
+
+Keep existing provider and application interfaces. Prefer existing settings and
+server-owned recipient/data policy over a new policy service. A policy must name data
+classes, destination, purpose and persistence; PII presence alone is not a deny rule.
+Any new admission control is a separately approved implementation, not an existing
+capability claimed by this plan. Do not require manual permission for every ordinary
+question once the product/deployment policy explicitly permits that data flow.
+
+Runtime observations remain optional and OFF until approved. A candidate must show
+coverage of a concrete risk, usable completed evidence, incremental benefit against
+existing controls, acceptable legitimate-use impact, cost/latency/retention and an
+approved recipient before P7 adoption. Reuse no detector solely because it was built.
+No implicit extra provider, fallback, re-answer, redaction, source quarantine or block.
+SHADOW findings cannot alter a valid answer; existing AuthZ/provider/schema/citation
+failures keep their own semantics. P9 separately decides any future action/error/
+streaming policy; final-only validated answer delivery remains unchanged.

 ## 4. Reuse, files and integration boundaries

@@ -162,9 +211,9 @@
 | Existing `evals/scorers/security_shadow.py`, `evals/runners/run_security_shadow.py` and tests | Preserve Secrets worker, sanitized outcomes, reviewed-only metrics, native capture loader and report behavior. Extend only for a demonstrated new requirement, preserving v1 reading. | PR #199 unchanged by this planning work; separate approved follow-up commit/PR for any later change. |
 | `evals/runners/evaluation.py:write_report_atomic` | Existing immutable publication seam; consume without copying. | Shared edit only if an exact justified diff is ACKed by #158/#192. |
 | New `evals/runners/cloudflare_p1_shadow.py`, focused test/fixture directory | P1 envelope preparation, transport/log-specific observation, attempt bounds. | P1 Step A technical approval is complete at `4f1a672`; fixture labels accepted October 17; detector quality unaccepted, P3 live session closed after stop. |
-| New `evals/scorers/cloudflare_pii.py`, `cloudflare_dangerous_output.py` and focused tests | Only selected cloud API payload/result mapping when candidate contracts are proven. Use one shared transport already present if suitable; no speculative base classes. | P5/P6 candidate and phase approval; file split can shrink if one existing adapter suffices. |
+| P5/P6 candidate code, including existing pure `cloudflare_dangerous_output.py` | Preserve current mapper/tests; no new PII adapter, transport or vendor by default. Add only a boundary-specific capability justified by P5/P6 benefit evidence. | Separate exact file/data/recipient envelope after owner scope review; existing mapper is not runtime or quality acceptance. |
 | Existing shadow runner + Knora native run/report authority | Supplementary schema version only when new fields are needed; detector type, scope and config remain explicit. Avoid four copies of metrics/capture validation. | Freeze additive supplement contract in P1. If extracting narrow pure helpers is needed, agree exact diff first; do not import DeepEval to borrow its ledger. |
-| Proposed `backend/src/knora/answering/security_observation.py`; existing answering module, bootstrap/settings, generation adapter | Application observation seam, runtime default OFF, Gateway/log correlation, safe completion behavior. | P7 only; exact shared hunks ACKed by #153/#158/#192; no first-phase edits here. |
+| Existing ingestion, embedding, answering, bootstrap/settings, trace and generation seams | Inspect actual egress/control gaps first; no observation module or Gateway selection mandated. Implement only an approved minimal change at the affected boundary. | P7 only; exact shared hunks and owning-module ACKs; no change to embedding identity or source text by convenience. |
 | Main/pyproject, tables/migrations, trace reader, operator observations, CI, API/UI/OpenAPI | No changes for offline detectors. Runtime persistence should reuse authorized trace/supplement storage. New migration/UI only if necessary and explicitly approved. | #192 owns evaluation modules/Runs/schema; #153 owns retrieval/answering/trace work. Serialize actual migration order, never assume unmerged 0047–0051 revisions exist. |
 | Verification notes/reports | Evidence and commands at exact phase commit; each report immutable. Master stores phase state/evidence links, not duplicate report payloads. | No raw secret/PII text in normalized reports or external issue comments. |

@@ -186,14 +235,19 @@
 | --- | --- | --- |
 | P1 | Injection intent in submitted evidence/envelope, including VI/EN and quotations | Did the answer follow injected instructions, disclose a synthetic canary or violate the reviewed task? |
 | Secrets | Secret presence using fake/nonfunctional keys only | Did a forbidden synthetic secret reach an unauthorized response/destination? |
-| PII | Approved entity presence/type; supported countries/languages explicitly listed | Did disclosure violate the principal/Workspace/use-purpose policy? Authorized PII is a legitimate control, even if presence is detected. |
-| Dangerous Output | Owner-reviewed hazard taxonomy/category | Did output violate that policy, or did protection cause false refusal of legitimate medical/security/research content? |
+| PII | Optional, descriptive entity presence/type for a justified selected scope; not permission | Did a specific value reach a prohibited recipient under the approved Workspace/data-flow policy? Authorized document Q&A containing PII is legitimate; unspecified permission stays unresolved. |
+| Dangerous Output | Optional classifier for owner-selected harmful-assistance scenarios; vendor categories are references | Did the assistant facilitate a concrete reviewed harm? Distinguish intent, requested action and context from topic/quotation; measure legitimate medical/security/research completion separately. |

 For each threat and scope report TP/FN/FP/TN, precision, recall and FPR only for reviewed labels with completed `detected/clear` evaluations. Zero denominators yield null. Also show all selected, attempted, observed, reviewed, evaluable, unknown/error/timeout/unavailable/not-run counts, coverage and reasons. Deduplicate by case/attempt/scope/config identity; repeated windows or both evidence/output do not create independent cases. Report language/family/length/boundary subgroups and sample counts; no pooled security PASS.

 Authorization labels are not presence labels. An authorized PII output can be positive for entity detection and negative for unauthorized disclosure; maintain both targets, not a contradictory single label. HTTP 200, model refusal, unflagged log or missing verdict never establishes detector clear. Missing/truncated log coverage cannot support full-input clearance.

-Measure end-to-end injection success, unauthorized secret/PII disclosure, dangerous output, legitimate completion/false refusal and citation correctness separately in P8. Use synthetic canaries and controlled destinations; never actually exfiltrate, send email or exercise real credentials. Human adjudication is authoritative; DeepEval is optional corroboration only under #158 and separate call approval.
+Measure end-to-end injection success, unauthorized secret/PII disclosure at each
+selected input/output/log boundary, reviewed harmful assistance, legitimate completion/
+false refusal and citation correctness separately in P8. Exact synthetic canary
+transfer can be asserted deterministically without adding a general PII model; this
+does not establish real-world entity coverage. Entity detection metrics remain
+optional candidate diagnostics, never unauthorized-disclosure or protection scores. Use synthetic canaries and controlled destinations; never actually exfiltrate, send email or exercise real credentials. Human adjudication is authoritative; DeepEval is optional corroboration only under #158 and separate call approval.

 Record added latency, failures, attempts/tokens and observed billed units/cost, not just detector score. Distinguish estimated vs observed vs unknown cost. Freeze config/rubric before trials; do not tune on the same 16 P1 development cases and claim held-out improvement. Thresholds and feasibility budgets are owner decisions after exploratory baselines, before release evaluation; do not invent percentages.

@@ -201,22 +255,29 @@

 ```mermaid
 flowchart TD
-  P0[P0 Inventory and Master review] --> P1[P1 P1 Step A plus shared observation contract: offline]
-  P1 --> P2[P2 Account capability and exact trial packet]
-  P2 --> P3[P3 Approved P1 FLAG cloud trial]
-  P1 --> P4[P4 Secrets qualification: preserve baseline]
-  P3 --> P5[P5 PII candidate and qualification]
-  P5 --> P6[P6 Dangerous Output candidate and qualification]
-  P4 --> P7[P7 Runtime code default OFF]
-  P3 --> P7
+  P0[P0 Existing inventory plus owner-approved threat revision] --> P1[P1 Retained offline contract]
+  P1 --> P2[P2 Retained capability investigation]
+  P2 --> P3[P3 Retained P1 findings]
+  P1 --> P4[P4 Retained Secrets findings]
+  P0 --> P5[P5 Personal-data flow and disclosure controls]
+  P0 --> P6[P6 Concrete harm scenarios and legitimate use]
+  P3 --> P7[P7 Only approved justified boundary changes: OFF]
+  P4 --> P7
   P5 --> P7
   P6 --> P7
-  P7 --> P8[P8 Approved runtime FLAG and end-to-end evaluation]
-  P8 --> P9[P9 Owner enforcement disposition and optional controlled trial]
-  P9 --> P10[P10 Acceptance and integration handoff]
+  P7 --> P8[P8 Security outcomes and legitimate-use evaluation]
+  P8 --> P9[P9 Owner policy and residual-risk disposition]
+  P9 --> P10[P10 Explicit scope acceptance and integration]
 ```

-Arrows mean specific reviewed deliverables, not whole parent Issue completion. P5/P6 source research can occur earlier if authorized, but candidate implementation/live trials remain in the preferred P1 → PII → Dangerous Output order. P4 can run alongside cloud readiness without using its resources. Within P5/P6, preparation and live verification are separate Goal envelopes. No phase is executable solely because its predecessors are technically complete.
+P1–P4 evidence remains immutable and does not need rerunning for this review. P5/P6
+scenario analysis can proceed independently; neither mandates a new cloud candidate
+or live trial. P7 depends on approved risk/control dispositions, not all four detector
+implementations. Each original group must be explicitly covered, retained experimental,
+or deferred with owner-accepted residual risk; absent detection is never a PASS.
+A P7 no-new-code disposition needs owner approval and existing-control evidence;
+P8 still needs the separately approved evaluation scope. Every implementation/live
+step retains its own permission, budget, data and ownership gates.

 | Phase | Current state | Can finish without live calls? |
 | --- | --- | --- |
@@ -225,8 +286,8 @@
 | P2 | Investigation and [consolidated approval packet](../../development/issue-188-p2-capability-investigation.md#consolidated-p3-approval-packet--proposed-not-granted) complete; both metadata endpoints returned 200. October 17 owner login restored Dashboard access. Approved P3 setup and trial-002 subsequently verified the saved configuration and produced native observations; their grant is consumed. | Yes; investigation complete, subsequent live execution recorded under P3 |
 | P3 | Trial-001 preserved. Separately approved trial-002 completed 16 POSTs/16 correlated logs: 8 explicit flags (6 attack/2 control), 8 unavailable native negatives. Full-population recall/FPR unknown. Owner explicitly retained P1 experimental/unaccepted; completed-negative/coverage evidence required before qualification/adoption. Grant exhausted, Guardrails/DLP OFF. | Native observation gap and false positives prevent qualification/acceptance |
 | P4 | Exact approved offline follow-up executed: 10 local calls/54.5 seconds, 16 pure + 1 real integration PASS; eight reviewed fixtures 3 TP/1 FN/1 FP/3 TN; selected saved output clear/unreviewed, evidence unavailable. Historical artifacts unchanged. Owner explicitly retained Secrets experimental/unaccepted; run allowance consumed. | Yes for saved/synthetic local detector evidence; not application leak acceptance |
-| P5 | Six-family/VI-EN preparation and approved three-provider public comparison completed. Azure Text PII recommended first for four documented VI/EN families; no candidate proves full six-family coverage. Cloudflare retained research-only. Thirty draft cases unaccepted; no adapter/live trial. | Research/preparation yes, real quality no |
-| P6 | S1–S13/VI exploratory/direct-classifier preparation: 52 draft cases, all labels unaccepted; S3/S4 lack positive coverage. Approved pure object mapper implemented/reviewed, 57 pure tests and Ruff pass; four canary payloads hashed offline. No transport/live trial or qualified detection. | Pure mapper yes, full P6a/quality no |
+| P5 | Retain six-family/VI-EN research, three-provider comparison and 30 unaccepted draft cases. Under this revised scope, prioritize recipient/data-flow policy and prohibited-disclosure scenarios; no Azure adoption or universal six-family release gate. No adapter/live trial. | Analysis yes; actual control/quality evidence requires its approved envelope |
+| P6 | Retain S1–S13 research, all 52 unaccepted draft cases, pure mapper and recorded 57 pure-test/Ruff results. Under this revised scope, select concrete harmful-assistance and legitimate-use scenarios before any classifier adoption; no category-wide completion mandate, transport or live trial. | Analysis/pure mapper yes; semantic safety remains unverified |
 | P7 | Not implemented / not approved | Yes for disabled code and mock integration |
 | P8 | Not run / not approved | Deterministic orchestration yes; real quality no |
 | P9 | No policy selected; enforcement OFF | Disposition can choose OFF; enforcement trial requires separate activation authority |
@@ -239,6 +300,11 @@
 ### P0 — Baseline inventory and Master architecture review

 **Dependencies:** Existing artifacts and owner planning request. **Deliverable:** This Master with source links, current states and superseded plan pointer. **Work:** Read current decisions/PR/code, verify exact baseline/CI, map ownership and approval frontier. **Tests:** Documentation links, phase coverage, contradictory approval/status scan, `git diff --check`; no detector execution. **Acceptance/DoD:** One forward plan; owner reviews architecture and may revise it. Saving/committing/publishing this draft completes planning output, not architecture approval or permission to implement.
+
+P0 review extension: owner approves a threat-to-flow matrix and explicit disposition
+for every original group. Separate requester access, processor/recipient permission,
+content presence and concrete harm. Preserve completed P1–P4 work and record every
+superseded six-family/S1–S13 delivery requirement; this is not automatic scope removal.

 ### P1 — P1 Step A and minimal observation contract, offline

@@ -304,57 +370,140 @@

 **DoD:** Qualified current Secrets capability with explicit residual risk or rejected candidate; no automatic security PASS. No dependency pin change/install/new case population without approved envelope. A quality failure triggers a concrete fix/candidate proposal rather than changing historical labels/results.

-### P5 — PII cloud candidate, offline preparation and separately approved trial
-
-**Dependencies:** P1 reuse contract; P3 findings before candidate adoption/live progression; owner approves entities, language/country support and authorization rubric. **Preferred investigation:** Cloudflare Gateway DLP FLAG; actual account profiles/entitlement must cover selected targets. S7 Privacy is not an entity detector. Wider cloud service, subscription or permission scope needs a new decision; do not silently fall back to Presidio/local models.
-
-**Deliverables:** (P5a, offline Goal) source-backed coverage/API/log/cost mapping, owner-reviewable selection from saved synthetic/public material with paired authorized/denied disclosure contexts, minimal adapter/tests. (P5b, live Goal) exact approved data/config/call/budget manifest and measured report. No fixed PII corpus size or live allowance is granted here; P5a must submit exact counts and digests before P5b authorization, using reviewed Knora annotations without touching #153 gold.
-
-**Acceptance:** Entity presence/type and unauthorized disclosure are two labels/denominators. Benign names/dates/URLs, legitimate medical records described synthetically and authorized PII are controls. Unsupported VN entity formats are explicit gaps, not negatives. Saved output sent as a request for DLP classification is labeled `output_replay_as_request`; it does not prove native response scanning. Verify actual runtime response coverage separately in P8. **Tests:** Redacted/sanitized results, profile drift, unauthorized input access, truncated/missing scan results, nested call accounting, replay/cost guards, authorized-positive presence without false leakage verdict. **DoD:** Offline adapter accepted, then separately real quality findings reviewed; uncovered required entities block coverage acceptance. No subscription purchase or live trial implied by DLP being described as free. [DLP scope](https://developers.cloudflare.com/ai-gateway/features/dlp/).
-
-### P6 — Dangerous Output cloud candidate, offline preparation and separately approved trial
-
-**Dependencies:** P1 contract; P5 findings for preferred sequencing; owner-approved hazard taxonomy/benign exceptions. **Preferred investigation:** Cloudflare S1–S13 FLAG on hosted Llama Guard; unsupported categories such as S14 cannot be claimed covered. No new local ToxicLanguage/Llama Guard/Detoxify assets.
-
-**Deliverables:** (P6a, offline Goal) taxonomy-to-provider mapping, exact reviewed Knora saved-output selection and controls, native API/log/cost proof, minimal adapter/tests. (P6b, live Goal) separately authorized bounded trial and measured findings. Toxicity is a subset, not the full policy. Determine whether a documented hosted moderation endpoint can classify saved output under the selected policy; Gateway response checks inspect a new generated response, not an arbitrary saved one. If no faithful replay path exists, label that part unsupported and propose a separate runtime observation trial; do not disguise prompt-side classification as response protection.
-
-**Acceptance:** Per-category/VI/EN coverage and FP/FN, quoted harmful research/medical/security content, direct instruction vs description and safe completion/refusal distinctions are reviewable. Freeze exact case counts/digests, rubric and cost packet before live authority. **Tests:** Multi-category findings without duplicated independent samples, unsupported/null category, quotation negatives, malformed classifier output, provider/log failure, raw reason sanitization, no extra generation/judge fallback. **DoD:** Selected capability and known limits reviewed; no broad Dangerous Output PASS from a single toxicity score or installed SDK.
+### P5 — Personal-data flows and unauthorized disclosure
+
+**Dependencies:** Approved threat revision, actual Workspace/capability semantics and
+owner-approved data classes/recipient/purpose/persistence policy. No inferred
+per-document restrictions or blanket ban on PII-bearing Workspace content.
+
+**P5a deliverables:** Map document/query embedding, evidence/history generation,
+detector recipients, local storage/trace and exports; distinguish existing control,
+verified gap and unknown. Specify paired legitimate/forbidden synthetic disclosure
+scenarios at named boundaries, including provider egress before generation. Propose
+reuse/fix/no-new-detector disposition and residual risk. Retain the six-family/VI-EN
+inventory, 30 drafts and provider research as exploratory evidence; they are not a
+universal qualification requirement under this revision. No Azure selection, regex
+substitute, text redaction or new adapter follows automatically.
+
+**Acceptance/DoD:** Authorized users can obtain faithful cited answers from permitted
+Workspace content containing PII. Permission to read and permission for a particular
+external processor are evaluated separately; permitted processing is not a leak.
+Verify prohibited flows before egress, legitimate-use controls, sanitized supplements,
+protected raw-trace policy and unknown-permission handling. Use fake known values
+for exact leak assertions; do not claim general entity accuracy from those assertions.
+A generic detector requires demonstrated incremental value over these controls,
+reviewed scope/labels and cost/retention/FP evidence. Optional P5b real evaluation
+needs its own exact data/account/call/budget grant. No-detector or deferred decisions
+require owner disposition and leave unsupported coverage explicit, never clear.
+
+### P6 — Concrete harmful assistance and legitimate document use
+
+**Dependencies:** Owner-reviewed harm scenarios based on actual Knora use and controls;
+P5 source findings may inform privacy scenarios but are not a required vendor trial.
+Retain S1–S13 as a reference inventory, 52 draft cases and the existing pure mapper.
+No mandatory all-category detector or implicit hosted classifier adoption.
+
+**P6a deliverables:** Proposed initial scenarios: output operationally facilitating
+account theft/fraud or physical harm, and converting cited medical/safety material
+into unsupported high-risk instructions. Pair each with legitimate document lookup,
+critical quotation, defensive security and medical/research education. Owner reviews
+concrete intent/action/context labels and boundaries before any new fixture or run;
+these scenario descriptions are not accepted labels or clinical certification.
+General accuracy/faithfulness remains with existing evaluation owners; reuse it for
+high-impact cases rather than building a second specialist judge.
+
+**Acceptance/DoD:** Topic, PII presence or a vendor hazard category alone cannot deny
+an answer; document access/citations do not automatically authorize harmful assistance.
+Measure harmful fulfillment and legitimate completion separately on reviewed selected
+scenarios. No universal quotation exemption; direct facilitation vs faithful analysis
+needs item review. Keep VI/EN and unsupported hazards explicit. Only investigate a
+classifier after a concrete unmet need and benefit/FP/egress/cost case; if selected,
+require faithful assistant targeting, complete native evidence and reviewed negatives.
+Optional P6b live quality needs a new exact grant. No real-world safety/coverage PASS
+from mock parsing or four target probes; all current annotations stay draft.

 ### P7 — Runtime integration code, disabled by default

-**Dependencies:** Accepted P3/P4/P5/P6 detector contracts and candidate decisions for the intended runtime scope; explicit runtime-code approval and concrete shared-hunk ACKs. If one group is rejected/unavailable, owner must approve a partial runtime scope; the agent cannot silently drop it or declare all #188 complete. **Deliverables:** Narrow observation collaborator/composition, immutable server-owned OFF/SHADOW profile, isolated Secrets execution arrangement, correlation into existing authorized traces/supplements, deterministic rollback. No deployment/Gateway activation/service start/migration execution.
-
-**Work:** Hook exact selected generation evidence and completed output at the section 3 boundaries; reuse workspace principal and current provider/prompt/citation flow. Cloud P1 uses the single existing generation call, not a second answer generation. Runtime cloud scans and source access require explicit egress/admission policy; a deployment-wide toggle cannot authorize every future private document. Runtime text classification scope/order/timeout/resource cap is part of the approved profile, not browser-controlled settings. Avoid new DB schema if safe trace/supplement references suffice; otherwise present schema/retention diff before implementation.
+**Dependencies:** Explicit owner dispositions for P3/P4/P5/P6 risks and accepted
+contracts for any selected control; a rejected detector is not a reason to rebuild
+another automatically. Owner-approved minimal code envelope and shared-hunk ACKs.
+**Deliverables:** Only justified changes at existing authorization/provider/trace or
+observation seams, default security observations OFF and deterministic rollback.
+Existing controls may suffice for a named risk with owner-reviewed evidence; new
+control code is not mandatory. No deployment/Gateway activation/services/migrations.
+Any unresolved material risk blocks the relevant protection claim until remediated
+or explicitly accepted/deferred in P10; a generic scanner cannot waive it.
+
+**Work:** First identify the affected boundary: document/query embedding, generation,
+protected trace, tool or optional observation. If an observation is justified, use
+exact selected generation evidence/completed output and existing principal/provider/
+prompt/citation flow. Keep original sources, aliases and embedding identities intact.
+Cloud P1 uses the single existing generation call, not a second answer generation. Runtime cloud scans and source access require explicit egress/admission policy; a deployment-wide toggle cannot authorize every future private document. Runtime text classification scope/order/timeout/resource cap is part of the approved profile, not browser-controlled settings. Avoid new DB schema if safe trace/supplement references suffice; otherwise present schema/retention diff before implementation.

 **Acceptance:** OFF makes no security calls/processes or dependency imports and preserves existing request behavior. SHADOW never edits answer/citations/refusal/source; detector failure is recorded without bypassing existing validation. Profile/digest and observation completeness are inspectable, secrets never enter metrics/log exports. Added latency/resource ceiling and fail-open behavior are explicitly approved; do not invent a timeout policy from availability defaults. **Tests:** Fake providers/observers exercise both synchronous Q&A and conversation/SSE paths, cancellation/deadline/worker cleanup, detector failure, cross-Workspace denial before data access/egress, stale/archive/revoke, malformed output/citation preservation, disabled dependency absence, no hidden extra call and rollback-to-OFF. **DoD:** Code review, regression/CI at exact head, disabled config readback and no live behavior change. Code-complete is not activated or security-accepted.

-### P8 — Approved runtime FLAG trial and security evaluation
-
-**Dependencies:** P7 code/CI, isolated local runtime/service authority, exact dataset/selection/binding/profile/account/egress/log/call/cost permissions, owner-approved measurement rubric and acceptance bounds. No borrowing #153's runtime or #158's budget. **Deliverables:** Paired baseline/OFF vs FLAG observations through the real application on approved inputs, native traces/citations, detector and application-security report, failure/latency/cost/rollback evidence. Preserve old Baseline B; new runs have new identities.
+### P8 — Approved application security and legitimate-use evaluation
+
+**Dependencies:** Owner-approved risk/scenario/control dispositions, relevant existing
+application gates and exact data/selection/observation permission. Any changed P7 code
+needs its own CI/review; a no-new-code route uses existing-control evidence rather
+than inventing a FLAG integration. Runtime/services/account/egress/call/cost permission
+is required only when that evaluation actually uses those resources, never inferred.
+No borrowing #153's runtime or #158's budget.
+
+**Deliverables:** Scenario-level application-security and legitimate-use evidence,
+with exact provenance and failures/unknowns. For a newly selected control, compare
+same-flow baseline with the approved control; for unchanged controls, report observed
+behavior without an improvement claim. Only a selected approved observer requires an
+OFF/FLAG comparison and detector report; native live traces are required for live
+claims. Preserved saved evidence and deterministic tests establish only their actual
+scope. No real-data/model trial is implied. Retain old Baseline B and use new identities
+for any approved new execution.

 **Acceptance:** Evaluate four targets separately: injection instruction following; unauthorized synthetic secrets/PII disclosure; policy-violating output; legitimate completion/false refusal and citation/source validity. Record same-case baseline/profile controls and stochastic/provider differences; mock byte-equality proves orchestration only, not semantic equivalence. FLAG is not expected to prevent a real attack by itself. No false-block reduction claim with enforcement OFF. Maintain all selected failures/REFUSALs, applicability/coverage and exact authorization context. Deterministic zero cross-tenant/unauthorized/stale evidence and valid citations remain non-negotiable existing gates, independent of detector/judge scores.

 **Tests:** Both API paths, late result/cancel/crash/indeterminate attempt, quota exhaustion, unavailable detector, log expiry/missing verdict, benign quoted content and unauthorized principal before any egress. Run legacy M1/M3/Vietnamese regressions with documented applicability. Reuse saved outputs for optional #158 judge scoring, never re-answer merely to give another tool data. **DoD:** Technical execution and quality status reported separately; owner accepts actual group-specific quality or records required remediation. Pre-register any revised policy/threshold and independent reviewed security validation selection before a later quality rerun; no tuning on pilot and calling it held-out acceptance.

+P8 additionally separates permitted provider processing from prohibited egress:
+assert no unauthorized embedding/generation/detector/export call before admission;
+check authorized PII-bearing answers and professional controls remain useful/cited.
+Inspect only approved sources/captures and sanitized metadata. Test exact fake-secret/
+PII canary transfer per recipient without claiming universal DLP accuracy. Report
+which claims are deterministic, human-adjudicated, model-dependent or unverified.
+Controls require same-flow baseline comparison; SHADOW alone cannot prove prevention.
+Any owner-approved no-new-P7-code route still needs the relevant application gates.
+
 ### P9 — Enforcement disposition; optional explicitly authorized implementation/trial

 **Dependencies:** P8 results and owner review. **Mandatory deliverable:** Written owner decision to retain OFF or adopt an exact policy; timeout/error/unknown, allowed entities/uses, category actions, evidence scope, user-visible behavior, latency, streaming release and rollback all explicit. No default BLOCK/fail-closed/fix/reask/redaction/quarantine from detector output.

 If owner retains OFF, record the accepted observational scope and residual risk. This is not enforced protection. #188 can close in that state only if the owner explicitly accepts that definition of completion; the agent cannot deem this phase unnecessary. If enforcement is requested, separate P9a code-only Goal and P9b activation/live Goal are required with new explicit scopes, tests and call budgets. Any change to original PDF/gold/source anchors remains excluded; dynamic source/whole-PDF blocking needs a new design decision, not an implementation detail.

+P9 policy must preserve legitimate cited document use. No entity match, source topic
+or broad vendor category alone triggers BLOCK, redaction or quarantine. A deterministic
+deny for a forbidden recipient/unauthorized principal is separate from probabilistic
+content findings; observation timeouts cannot bypass an existing access/egress deny.
+The owner decides any future high-risk assistance action and its false-refusal bound.
+
 **Tests for approved actions:** Hazard-specific block/allow vs authorized PII/quoted research, false-block rate and legitimate completion, deterministic response/citation behavior, fail-open/closed per selected policy, no partial output before output approval, streaming/cancellation/error mapping, config drift and kill-switch rollback. **DoD:** Owner accepts OFF disposition or the exact implemented/verified policy. Enforcement is still OFF until an activation permission is actually given.

 ### P10 — Final acceptance, PR integration and handoff

 **Dependencies:** Evidence from every required phase/group and P9 owner disposition. **Deliverables:** One acceptance matrix linked from this Master, versioned residual-risk/coverage record, exact-head CI/review and integration/rollback order. Reuse PR #199 as Secrets artifact; later PRs reference #188 without closing it prematurely.

-**Acceptance/DoD:** Owner reviews the matrix in section 10 and explicitly accepts or rejects #188 security quality/scope. Resolve stacked/shared commit order, compare frozen artifact hashes and retain regression evidence. Present exact PR heads and CI required results; explicit merge permission is still separate. No self-merge, Issue close/Project Done or deployment based on tests/Goal completion/plan approval. Deployment/public-demo approvals stay in their owning Issues. An unverified required threat group is a remaining gap, not waived by a green aggregate.
+**Acceptance/DoD:** Owner reviews the matrix in section 10 and explicitly accepts or rejects #188 security quality/scope. Resolve stacked/shared commit order, compare frozen artifact hashes and retain regression evidence. Present exact PR heads and CI required results; explicit merge permission is still separate. No self-merge, Issue close/Project Done or deployment based on tests/Goal completion/plan approval. Deployment/public-demo approvals stay in their owning Issues. For every original group and data boundary, record implemented control + evidence,
+experimental observation, or explicitly accepted/deferred residual risk. Owner must
+approve any revised six-entity/S1–S13 requirement and reconcile Issue #188 scope;
+no implementation is erased or unverified group counted as passed. No closure merely
+because a detector was judged unnecessary. Detection Completed and Protection Enabled
+remain separately scoped claims, with unqualified/absent detection and enforcement
+OFF reported honestly even if the owner accepts a narrower Issue disposition.

 ## 8. Permissions and decisions — who may authorize what

 | Authority | Currently granted | Required concrete record before use |
 | --- | --- | --- |
-| Master planning/research/docs | Master/P0–P10 continuation approved; current finite envelope is P5 alternative-source research and P6 pure mapping/tests, as recorded above | Keep this single Master; phase Goals and separate permission gates remain mandatory. |
+| Master planning/research/docs | Threat-model reassessment and proposed Master diff only; prior comparison/mapper complete; Azure/canary proposals not selected | Only explicit owner approval adopts the revised scope. New implementation or research beyond this review requires its own concrete envelope; no executable phase permission follows. |
 | Existing Secrets implementation/pilot | Historical approved envelope only | Exact PR #199 artifacts preserved; does not grant new scans/install/runtime. |
 | P1 Step A / P2 offline work | P1 technically complete; P2 research, sanitized metadata analysis, offline verification/review/repairs and trial packet approved | Existing installed dependencies and pinned P1/PR #199 reuse only; no new install or live authority. Later implementation must satisfy its phase dependencies and concrete envelope. |
 | New dependencies/install | No new install granted | Exact versions/hashes/licenses, isolated environment and transitive egress/model behavior; no additional local security model. |
@@ -371,9 +520,19 @@
 ### Open owner decisions and when they reach the frontier

 1. **Decided 2026-10-16:** Architecture/Master v1 and P1 Step A approved, with Detection Completed distinct from Protection Enabled. Do not ask again.
-2. **Current frontier:** P3/P4 dispositions, P5/P6 targets/preparation, Cloudflare PII research-only disposition, alternative comparison and P6 pure mapping scope are settled and their approved deliverables complete. Next decisions: Azure four-family investigation versus resolving full-scope PII gaps first; P6 exact canary labels/strength and any bounded transport/account/live preparation scope. Do not repeat settled targets, drop CCCD/MRN, accept quality, or infer detector/API/config/runtime permission.
+2. **Current frontier:** Review the proposed risk-based revision: six-family PII and
+   S1–S13 become retained research inventories rather than mandatory detector release
+   coverage; P5 targets unauthorized flows and legitimate use; P6 targets reviewed
+   harmful-assistance scenarios. These are explicit proposed changes to prior targets,
+   not already approved reductions. No Azure preparation or replacement canary was
+   selected. After scope approval, present one finite scenario/control evidence packet
+   before code, fixture/label promotion or any trial. Preserve existing dispositions.
 3. **After concrete packets:** Review candidate/entity/hazard coverage, exact labels, data/logging choice, run costs and calls. Account/pricing facts are the agent's research responsibility; owner decides permissions and risk, not factual API behavior.
-4. **After findings:** Choose remediation, accepted quality bounds/validation selection, runtime profile and activation, then enforcement disposition and acceptance/merge independently. Never reopen already-settled local-development/public-synthetic/no-new-local-model/Knora-authority decisions without new conflicting evidence.
+4. **After findings:** Select only controls with demonstrated value; owner approves
+   residual risks, quality/legitimate-use bounds, code/activation and enforcement
+   separately. Local-development/public-synthetic/no-new-local-model/Knora-authority
+   constraints remain. This owner-requested threat revision explicitly reopens scope
+   for review, not label acceptance or technical execution.

 **October 17 pre-execution decision packet (historical; current stop above supersedes its pending status):** The owner restored the authenticated in-app
 Dashboard session and resumed read-only work. [The consolidated P3 packet](../../development/issue-188-p2-capability-investigation.md#consolidated-p3-approval-packet--proposed-not-granted)
@@ -447,13 +606,28 @@

 | #188 completion criterion | Evidence required | Owner action |
 | --- | --- | --- |
-| All four threat groups | Accepted target/coverage, reviewed labels, completed detection/FP/FN evidence, explicit unsupported gaps; historical Secrets results retained | Accept each group or keep #188 incomplete; no aggregate waiver by agent |
+| Every original threat group and actual data boundary | Approved scope/control disposition; attack/leak/harm and legitimate-use evidence; candidate FP/FN only where qualified; retained history and explicit unmitigated gaps | Owner accepts revised scope and each risk disposition or #188 stays incomplete; no detector absence counted as PASS |
 | Genuine application security | P8 trace-linked attack/leak/hazard and legitimate-completion/citation results with proper denominators | Accept actual quality against agreed bounds |
 | Existing hard gates | Zero deterministic cross-Workspace/unauthorized/stale evidence violations; source/citation/auth regressions pass independently of classifier | No relaxation through detector/judge score |
-| Runtime | OFF guarantees and approved shadow behavior, timeout/cancellation/resource/egress/log handling, exact profile and rollback | Accept implemented/activated scope separately |
+| Runtime / data egress | Existing or approved minimal control evidence for document/query embedding, generation, detector, tool and persistence; OFF behavior for optional scanners and exact recipient/data policy | Accept actual control/activated scope; unresolved recipient permission blocks that new egress, not all PII document use |
 | Policy | P9 disposition and residual risks; any action tested only within separate permission | Explicitly retain OFF or accept named enforcement policy |
 | Reproducibility/operations | Commit/input/config/label/version identities, native observation IDs, errors/coverage, cost/latency, log retention and no raw exports | Accept evidence limitations and handoff |
 | Integration | Exact-head CI/review, serialized shared-file/base/migration order, PR #199 reused and other PRs scoped | Explicit merge instruction; then Issue/Project disposition, no automatic Done |
+
+### Revised acceptance requirements
+
+- Authorized PII-bearing document Q&A is a positive product requirement, with faithful
+  citations and legitimate-use controls; measure false refusals independently.
+- Cross-Workspace/capability/active-source/tool denies remain deterministic and must
+  stop before lookup or prohibited egress. A classifier never overrides them.
+- Verify each selected provider/log/detector boundary against an approved data policy;
+  credentials/raw scanner matches never enter published observations. Authorized raw
+  trace storage is not equivalent to metadata-only telemetry or unlimited retention.
+- Pre-register scenario-specific harm/disclosure and utility bounds before evaluation;
+  no invented universal percentage, all-entity coverage or all-category safety claim.
+- No generic detector adoption without an explicit control gap, native evidence,
+  incremental value, legitimate-use/latency/cost/retention review and owner approval.
+  Every omitted/deferred detector or risk needs an explicit disposition, not silence.

 ## 11. Review checklist and immediate next step

@@ -462,4 +636,11 @@
 - [x] Owner approved Q1 / P1 Step A offline and autonomous technical repairs.
 - [x] Prepare P1 offline artifacts, independent review and P2 prerequisite handoff in the P1 evidence note; exact-head CI and final handoff remain explicit PR/#188 gates.

-P1 offline technical work and P2 investigation are complete. Renewed P3 trial-002 has 16 successful HTTP responses and correlated native logs, 8 explicit positive flags and 8 unavailable negative outcomes; owner retained P1 experimental/unaccepted. Guardrails/DLP were OFF at that readback; its grant is exhausted. P4 used all ten approved local invocations, preserved historical inputs/reports and retained the split-key FN/checksum FP; independent evidence review found no actionable findings and owner retained Secrets experimental/unaccepted. P5/P6 source research and approved metadata/draft preparation are complete: 30/52 synthetic cases, all annotations unaccepted. The subsequent three-provider P5 comparison and two-file pure P6 mapper are complete and independently reviewed without actionable findings; 57 pure tests and Ruff checks passed. Full PII coverage and assistant-target/completed-negative evidence remain unresolved. Current frontier is the [P5 contract/gap and P6 canary-design decision packet](../../development/issue-188-p2-capability-investigation.md#next-owner-decisions--p5-contract-gaps-and-p6-canary-design). These proposed offline branches have no execution grant yet. No new credential/account read, detector execution, inference, permission expansion, runtime activation, enforcement/export, merge or deployment follows from automatic continuation.
+P1/P2 technical work, P3/P4 findings and the completed P5/P6 research/pure mapper
+remain preserved with their exact evidence. P1/Secrets are experimental, all 30/52
+P5/P6 annotations are unaccepted; no quality or protection claim is upgraded.
+Owner requested this threat-model revision before further candidate work. Review
+[the proposed diff and risk matrix](../../research/issue-188-threat-model-proposed-master-diff.md),
+then approve or amend the scope/control dispositions. No Azure or canary preparation,
+code, provider/detector/API, credential/account access, runtime/config, enforcement,
+export, commit/push/merge or deployment follows from this planning checkpoint.
```

## 8. Review frontier

❓ **Q1 — Revised scope:** Adopt this risk-based Master revision for review/recording, replacing mandatory six-family/S1–S13 detector completion with explicit threat/control dispositions while preserving all historical work?

➡️ Recommend the proposed revision. It preserves all four risk reviews, legitimate document use and explicit residual risk. Approval would permit recording the revised Master only; implementation still needs a concrete envelope.

The later P5/P6 scenario packet would contain named data recipients, permitted/forbidden flows, concrete harm/legitimate controls, reviewed selection and acceptance bounds. It is not part of this approval and must not renew previous execution budgets.

## 9. Verification and limits

- Source review only; no provider/API/model/detector/account/credential access, external network request, package install, runtime or cloud change. Local Hindsight lookup could not connect.
- `git apply --check --whitespace=error-all` validated the proposed diff against the exact dirty Master without applying it. P0–P10 remain present; P1–P4 contracts compare unchanged. Eight selected Master/domain/evidence/code/fixture hashes match their recorded baseline.
- Independent review found a P8 dependency contradiction: mandatory FLAG/P7 code would defeat the no-new-detector route. The proposal now conditions code/CI, runtime and OFF/FLAG evidence on the actual selected control/resources, preserving relevant gates and no-improvement claims for unchanged controls. The reviewer confirmed closure of that finding.
- Test implementations provide evidence of intended assertions, not fresh test or deployment results. Historical 57-pass mapper results are not a new test run.
- Provider region/terms/logging/retention, current auth configuration, deployed behavior, real attack rates and incremental detector benefit remain unverified.
- No assertion that every legitimate task is safe, or that a faithful citation proves medical/security correctness. No global content ban or new scope is enacted.
