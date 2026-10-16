# Issue #183 — Master Implementation Plan

> **For agentic workers:** Use `executing-plans` for one explicitly approved phase at a time. A Codex Goal references this Master commit and phase, never another roadmap. Checkboxes track progress; they do not grant permission.

**Status:** Owner approved v1 at `f5631b2`, retained P0–P6 and authorized P1 offline ([approval record](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6207043333)). P1 investigation is complete; its exact proposal below awaits owner approval before P2 behavior changes. Q21 remains postponed; no live inference window is active.

**Goal:** Complete general answer-list presentation without losing source meaning, conditions, order, citations or accepted #169/#178 behavior; submit PR #184 for explicit acceptance and separately authorized integration.

**Architecture:** Reuse Cloudflare's presentation selector, fixed `before/items/after` contract, existing Markdown composer and public citation validator. Treat generation fidelity, retrieval coverage and rendering as separate boundaries. Put a finite remediation-design gate before implementation; do not build a semantic evaluation subsystem.

**Tech stack:** Existing Python/Pydantic/httpx, PostgreSQL, Next/React Markdown, Keycloak and Cloudflare Workers AI. No new dependency, framework or provider abstraction.

**Spec:** [#183](https://github.com/NhiBuaa/knora-agent/issues/183), [ADR0017](../../adr/0017-structured-generated-lists.md), [architecture](../../standards/architecture.md), accepted [#169](https://github.com/NhiBuaa/knora-agent/issues/169)/[PR175](https://github.com/NhiBuaa/knora-agent/pull/175) and [#178](https://github.com/NhiBuaa/knora-agent/issues/178)/[PR182](https://github.com/NhiBuaa/knora-agent/pull/182). Latest owner decisions take precedence over superseded proposals.

## 1. Authority and one source of planning

- This is the **only forward implementation plan** for #183. Issues hold decisions/approvals; reports hold measured evidence; this file holds phase sequence/status and evidence links. Goal objectives reference it instead of copying a roadmap.
- The [former plan](../../development/issue-183-structured-list-plan.md) is a historical pointer. Its full Q1–Q19 content remains in Git history at `305f8b9e50fdb7655bc4d3ccdbdb4a6c07269fae`. Old unchecked tasks do not define current pending work or permission.
- [Initial verification](../../development/issue-183-list-formatting-verification.md), [research](../../development/issue-183-provider-output-research.md) and [runtime checkpoint](../../development/issue-183-structured-runtime-status.md) retain dated facts. Their next-step proposals are superseded here; preserve failures and historical results.
- Follow AGENTS, CONTEXT, domain/issue-tracker guides, architecture and M1/M2 seams. Reuse `C:/Developer/Projects/knora-agent-worktree/issue-183-answer-lists`, branch `fix/issue-183-answer-lists`. Never modify another worktree/runtime.
- Master approval, phase execution, live-request allowance, product acceptance and integration/merge approval are distinct. Dependencies do not grant permission. Q1–Q20 windows are closed; Q21 is postponed, not a reusable quota reservation.
- Owner resolved acceptance scope when starting P1: generation with sufficient supplied evidence. Default M1 retrieval belongs to #153; neither containment rollout nor M1 acceptance is implied. P4 still requires its own exact runtime/configuration/window approval.
- Reuse #188's structure, not its permissions/infrastructure: [Master publication](https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6198892594), [phase-specific approval](https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-6199169575). Technical completion, quality acceptance and integration remain separate.

## 2. Verified baseline and remaining work

Inputs read for this plan: full #183 body/34 comments, PR184 body/12 comments/review state/commit and file lists, #191/PR200 decisions, maintained provider/composer/tests/docs, original PDF text and Q20 request/final payload/usage/guard. No fresh inference. PR184's generated summary overstates semantic rejection/preservation; its original bot guide still describes obsolete prompt v5. Neither is acceptance authority.

| Surface | Verified state | Reuse/limit |
| --- | --- | --- |
| Product candidate | `305f8b9e50fdb7655bc4d3ccdbdb4a6c07269fae`, PR184 OPEN/Draft. Later planning commits do not change product behavior. | Selector, fixed slots, required nullable paragraph bold, server bullets/emphasis/citations and local gates. |
| Prompt/model | `cloudflare-presentation-v1`, `cloudflare-gpt-oss-cited-answer-v17`, GPT-OSS20B, 1024 completion tokens **per generation request**. | Same question/Evidence Set feeds both stages; two generation requests per turn. Other providers unchanged. |
| Technical verification | Q19 full local1983 passed/16 skipped; focused101 and HTTP/PostgreSQL17; independent offline review found no actionable issue. [Q19 result](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6193511242). | Historical tree-specific evidence, not fresh tests or model compliance. |
| CI | [38736957441 attempt2](https://github.com/NhiBuaa/knora-agent/actions/runs/38736957441/attempts/2): CI required/all five components SUCCESS at305f8b9. | Attempt1 frontend child status/null and Windows readiness timeout remain unexplained. Preserve both attempts; do not weaken deadlines. |
| Corpus | Original #169 Report guidelines.pdf; Document `06541705-cf19-4377-a94c-e6b1fa180883`, Version `b9c52a63-185d-4078-956c-ec42bdd807af`, 23 chunks/vectors. | Reuse after read-only digest/identity verification; no ingestion/re-embedding. |
| Q20 count | Turn `cce2cb5b-12f1-433e-a06c-456ecd4c2cda`, answered/final_validated; count_list, bold **7 chương**, seven separate items in source order, one chip. | Working layout/composition/Turn/trace/source-path observation. |
| Q20 semantic blocker | **FAIL:** E2/PDF p.1 contain merge/split conditions, output omits them; after=[]; finish=stop,548 completion tokens. | This corrects the earlier “unverified” assessment. Schema/alias/public validation did not detect semantic omission. |
| Q20 missing cases | Second Turn `405c78ea-7e3a-4c91-8bf2-0fb6e7032185` blocked before provider by >600s observations; third not sent. Exactly3 physical requests. | No v17 general-list/short-answer success. Unused allowance expired. |
| Browser/safety | DOM read at1440×960/390×844 and source chip opened p.1; guard38 offline tests; OAuth additions cleaned, owned services stopped. | Partial display evidence; DOM alone does not certify visual fit. Mobile viewport is not a phone. Actual request-specific charge unknown. |
| #191/PR200 | Offline refactor accepted at `17f199810970c40d2bcd060e68a03fc0aacc210b`; Draft PR200 stacked on184 and includes305f8b9. | Separate extraction/parity, not a fix or acceptance proof for183. |

### Q1–Q20 decision/evidence ledger

Numbers identify decisions/windows, not reusable grants. Keep detailed usage/failures in the linked records. Do not manufacture a lifetime request total: early probes lack one complete consolidated ledger.

| Decision/window | Settled result/limit | Record |
| --- | --- | --- |
| Initial A/v4–v8 | v4 trace/Turn had no newlines before display; v8 showed7/6/0 bullets but general list lacked sufficient support, source order and conditions. | [Initial](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6162230653), [source audit](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6162792717). |
| Q1 | Natural paraphrases with source support, not mandatory verbatim text. | [Q1–Q4](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6166011635). |
| Q2 | Proven total allowed with incomplete members if missing portion disclosed; no assertion of unproven total. | Same checkpoint/owner decision. |
| Q3 | Preserve clear source order; reasonable arrangement only when sources have no shared order. | Same checkpoint. |
| Q4 | All needed sources; prefer chip after last consecutive shared-source block; accuracy takes precedence over appearance. | Same checkpoint; public alias uniqueness remains. |
| Q5 | Exactly6 comparative20B/120B diagnostic calls at4096; neither passed. No evidence for switching model. | [Results](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6170904376). |
| Q6 | Simpler paragraph/list/text/anchors, no count/basis/witness; v13/4f8e940 code/tests. | [Q6](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6172048020). |
| Q7 | Helper main-guard error before provider,0 calls; recovery needed new permission. | [Q7](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6172405428). |
| Q8 | One recovery materialized23 chunks; combined7/8 calls. M1 count lacked evidence, list remained paragraph/lost conditions, short quote capitalization failed. | [Q7/Q8](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6172692531). |
| Q9 | Aliases replaced literal quotes/quote-position gate; v14/c5e1d59. Full outline was excluded by M1 REDUNDANT_OVERLAP. | [Q9](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6183412750). |
| Q10 | Runtime-only containment supplied full outline;2/6 calls, v14 paragraph-only/literal stars/missing conditions; payload through DOM agreed. | [Q10](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6183587668). |
| Q11/architecture round | Prompt Policy/Builder/Versioning routed to separate191; no runtime pass or extra allowance. Session numbering is not a missing provider window. | [#191](https://github.com/NhiBuaa/knora-agent/issues/191). |
| Q12 | Two-stage selection/answer v15/67a149f; code/tests only. | [Q12](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6186035384). |
| Q13 |2/9 calls; helper UTF-8/cp1252 failure before answer admission, repaired offline. | [Q13](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6186191164). |
| Q14 | Authorized replacement used3 calls; selector correct, answer HTTP400; helper missed error body. | [Q14](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6186295548). |
| Q15 | One identical replay: HTTP400/code3030/internal error; exact unsupported keyword not established. | [Q15](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6186391826). |
| Q16 | One schema-only comparison200 but length/content=null at1024; cumulative Q13–Q16=7, all windows closed. | [Q16](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6186509117). |
| Q17 | Fixed before/items/after, one main list group, existing selector/local gates; v16/c775a83; zero inference. | [Approval](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6186608013), [checks](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6187082118). |
| Q18 |3/9 calls; optional wire bold/required local bold mismatch caused rejection; separate missing conditions. Stale Billing fallback and frontend3000 interruption violated approval, disclosed. | [Corrected result](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6188072720), [audit](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6191882261). |
| Q19 | Required nullable bold aligned wire/local; v17/305f8b9; tests/CI passed, no semantic fix or inference. | [Final](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6193511242). |
| Q20 |3/9 calls; count layout/source opening succeeded, conditions omitted; second blocked on stale preflight, third unrun. This Master corrects semantic status to FAIL. | [Result](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6194629838), [follow-up](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6194708201). |

## 3. Root causes and evidence limits

| Finding | Supported cause/boundary | Disposition |
| --- | --- | --- |
| Original flattened list | Provider output lacked structure; persistence/renderer preserved it. | Composer handles structure when correct items supplied; no renderer rewrite. |
| M1 count refusal | Full outline existed but overlap selection excluded it; refusal matched supplied evidence. | Separate retrieval/config gap. Containment supplies evidence, not default-M1 acceptance. |
| v13 anchor rejection | Model changed quote capitalization; literal gate rejected supported prose. | Superseded by Q9 aliases; do not reintroduce catalogs/quote repair. |
| v15 HTTP400 | Upstream errors before decoder; one schema-only comparison avoided400. Error3030 identifies no keyword. | Compatibility hypothesis only; current shallow slots supersede old schema. |
| Output truncation | v12/Q16 exhausted output cap with missing content. | Independent from semantic errors; Q20 stop/548 tokens is not truncation. |
| v16 bold mismatch | Wire permitted absent bold, local count required it; captured payload reproduces error. | Q19 fixes structural mismatch, not semantics. |
| Current omitted conditions | Q20 E2 and prompt contain requirements; generated slots omit them before composition. Composer preserves supplied text and has no semantic coverage gate. | Generation source-fidelity failure; exact model-internal reason unknown. Shape/alias validity cannot prove completeness/entailment. |
| Harness/preflight/OAuth | Main guard, encoding, error capture, stale grant and Q18 unsafe fallback/shared-process interference are distinct operational defects. | Reuse corrected helpers with denial tests and fresh provenance; do not alter product semantics to mask harness failures. |

PDF p.1 has a **suggested** seven-chapter software-report outline, not a universal mandatory count. Small reports may merge chapters3/4 and possibly5 depending on report length; chapter5 may split when necessary. General-list answers must retain conditions on supplementary/index sections. Correct citation identity alone cannot establish support for every assertion.

## 4. Recommended remediation decision and file ownership

No proven algorithm currently guarantees semantic completeness. P1 is a finite offline design gate, not permission to keep trying prompts until a lucky result passes.

| Route | Benefit | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| A: reuse selector/fixed slots/composer; one targeted generation-policy change for qualification retention | Uses existing before/after prose and aliases; natural answers, little code. | Still a hypothesis: needs exact diff, identified ambiguity/priority conflict, predeclared source criteria and stop rule. | Recommended **P1 investigation**, not an approved implementation or guaranteed fix. |
| B: explicit qualification collection/coverage contract | Can expose a structural omission class. | Someone must identify relevant conditions; a required empty/wrong field cannot prove completeness. More complexity/overlap with153/158. | Not selected; separate design approval required, never automatic escalation from A. |
| C: unchangedv17 plus two remaining questions | Fills list/prose coverage in at most6 future calls. | Cannot resolve the known count semantic failure. | Q21 postponed; not a path to full DoD. |

P1 compares exact instruction ordering, existing qualifier-slot capacity and captured failures, then proposes one smallest justified diff with alternatives/limits. If none is justified, report that and block P2. No new20B/120B comparison, larger cap, block union, quote/line catalog, semantic judge, automatic reask/repair, text-splitting regex or dependency.

| Files/surface | Responsibility and reach after phase approval |
| --- | --- |
| `backend/src/knora/providers/openai_compatible/generation.py` | Cloudflare generation policy/version/transport. P1 reads; P2 edits only approved hunk. No module moves. |
| `backend/src/knora/providers/openai_compatible/answer_blocks.py`, `presentation.py` | Existing fixed schema/local gates/composer/selector. Reuse unchanged unless P1 decision explicitly names a necessary contract change. |
| `backend/test/providers/openai_compatible/test_answer_slots.py`, `test_answer_blocks.py`, `test_generation.py`, `test_presentation_generation.py`, `test_application_integration.py` | Supplied qualifier preservation, schema, aliases, errors/refusal, metadata and no repair/mutation. Fixtures cannot certify generated semantic completeness. |
| `backend/test/adapters/postgres/test_cloudflare_application.py`, `backend/test/answering/test_generation_validation.py` | Public citation/result/trace/Workspace regression. |
| `backend/src/knora/providers/generation.py`, `backend/src/knora/answering/module.py` | Existing provider/application metadata seams. No edits proposed; necessity needs exact shared-file agreement. |
| `frontend/components/conversations/AnswerContent.tsx` | Existing renderer, read/test only. Revisit only with a proven new payload-to-DOM mismatch. |
| Ignored `frontend/test-results/issue183/` | Private payload/source/helpers/screenshots/window ledgers; reuse Q20 guard, no general harness framework. Never commit secrets/raw reasoning/full PDF. |
| This Master, ADR0017, CONTEXT, evidence notes | Current sequence here; confirmed domain decisions in ADR/CONTEXT; dated results in reports. No second plan. |

Before intersecting code edits, post base SHA, exact paths/hunks, behavioral impact and tests to183/191 and obtain an explicit coordination ACK for overlapping work. Silence is not agreement. #183 owns behavior/prompt/schema/acceptance; #191 owns extraction/parity. Do not import PR200 into184 as a semantic fix. [Current191 boundary](https://github.com/NhiBuaa/knora-agent/issues/191#issuecomment-6193697128).

### 4.1 P1 offline investigation and decision package

Investigated unchanged product baseline `305f8b9` through documentation head `f5631b2`; zero new inference. Original PDF, Q18/Q20 requests, safe final JSON text, safe usage metadata and current code were compared. Private artifacts stay in ignored `frontend/test-results/issue183/master-plan-review/`; no raw reasoning was inspected or published.

| Artifact | SHA-256 / result |
| --- | --- |
| Original12-page PDF, updated25/08/2024; Document Version `b9c52a63-185d-4078-956c-ec42bdd807af` | `219b5a71a5de2d909421a1bbb984664eaae2495958467b32c4e04325f2ef32d6` |
| Q18 answer request | `95320870a030a5dc805cb8d32ac8139ce5a79f572617a6567d10bf1584627ac0` |
| Q18 final JSON text | `45d0329ea145b1c3e3d7240ead3da6ef1b858c609887223426e5e720a7334016` |
| Q20 answer request | `715a0706abb4c66112dac977d4ad3d9c6aec88ee49ba9f647864f58ab1aa846d` |
| Q20 final JSON text | `88e6063e7644625ee047e14b4160197996e6865ffc6b0563dfd292eeeda9f63d` |
| E2 UTF-8 content, identical in Q18/Q20 | `52a86d817d05454f5c7c3bc8972afb71673ae2d1559f2880915884f9778e51bf` |
| Q20 offline composed Markdown | `b000fda867c83b696eb1a7e5a2258aaca0478efbd3539ca80874416fdc601d07` |

Q18/Q20 have identical question/Evidence Set/user messages. Both finals have one lead, seven members, no `after`, and neither merge/split condition. Q18 is rejected for missing bold; Q20 matches the current outgoing v17 policy and wire schema exactly, composes seven bullets/bold/one E2 marker unchanged, and is accepted structurally. Q20 HTTP200/stop/548 completion tokens rules out observed truncation; it does not explain why the model omitted conditions. No literal-quote/coverage gate exists to reject this semantic omission. Existing `test_fixed_slots_render_one_list_between_supported_paragraphs` already preserves supplied qualifications; adding a duplicate composer mechanism would not fix generation.

**Source expectations frozen before another candidate:** PDF physical p.1–2 and index guidance p.10 were inspected as rendered pages as well as extracted text. Count: suggested software-project outline, titles1–7 in source order, small-report merging3/4 (possibly5) depending on report length, and splitting5 when needed for more specific/clear content. Other-list: prescribed cover/information pages, contents/index pages, abstract, references, required/conditional appendices without duplicate categories; image/table/formula indexes stay conditional. P.10 also treats image/table/symbol indexes as conditional and forbids an empty table index when no table exists. Do not assert p.10-only detail unless supplied evidence supports it. Outline and detailed frontmatter have different granularity/order; retain an actual clear local sequence without inventing a common global order or a fixed bullet count. The short answer should state the common goal of a comprehensive view of the group's research and implementation; no unrelated outline. Abstract length is not required merely to name parts; any voluntarily added fact needs support.

**Bounded hypothesis, not a proven model-internal cause:** v17 already explicitly requires qualifications, including merging/splitting. There is no demonstrated contradiction. However, `after` is described only as concluding paragraphs, while scope/background rules do not explicitly say that conditions governing an answer belong within its scope. The exact candidate below makes that scope and placement explicit using existing slots. It does not force a nonempty after, duplicate a condition already stated, append unrelated background to short prose, or inspect source text with product matching code. One candidate is proposed; no offline assertion proves it improves GPT-OSS20B compliance.

| Decision | Benefit | Cost/limit |
| --- | --- | --- |
| **A — recommend the exact v18 policy-only candidate below** | Reuses selection, schema, composer and existing aliases; states where relevant shared/member conditions go. | More explicit policy still may be ignored. Needs one separately approved final-candidate runtime window; stop on the first failure, no prompt search loop. |
| B — qualification collection/coverage schema | Exposes a qualification field structurally. | Empty/wrong extraction still passes; requires identification/checking logic and expands the contract already simplified after failures. No evidence justifies that complexity inside183. |
| C — retain v17/Draft | No change or quota. | Known semantic failure remains; two missing cases cannot make AC2 pass. |

**P2 envelope requested, not yet granted:** Only the exact Cloudflare policy/version hunk in4.2; update the three version expectations shown there, extend existing transport/slot fixtures only where needed, and document this approved hypothesis in ADR0017/CONTEXT. No schema, selector, composer, transport algorithm, retrieval, model/cap, retry, dependency or module movement. Before edits, obtain191 overlap ACK on this exact base/hunk. Reuse the existing qualifier fixture and test a generic supplied member condition plus shared merge/split conditions without question-specific product logic; fixtures prove preservation only. Assert actual outgoing policy/version and unchanged user/evidence/schema/model/cap in MockTransport, keeping refusal/errors/no-retry coverage. Re-run focused/application/PostgreSQL/full formatting/config/CI gates and independent review under P2. P3 may prepare offline denial/readiness checks after technical pass; no runtime/OAuth/inference permission is requested by this patch.

**Offline evidence:** `p1_replay.py` asserts safe captured final content through current composer, current Q20 prompt/schema equality, E2 equality and no mutation: PASS. Existing `test_answer_slots.py` + `test_answer_blocks.py`: **55 passed**; `test_presentation_generation.py`: **32 passed**. These are unchanged baseline tests, not candidate or model-compliance passes. CI atf5631b2 is all SUCCESS ([run38787263237](https://github.com/NhiBuaa/knora-agent/actions/runs/38787263237)). Full application suite is not rerun for this documentation-only investigation. Owner approval and191 ACK are still pending; semantic FAIL remains.

### 4.2 Exact proposed P2 behavior diff — NOT applied

The following unified diff applies to product baseline305f8b9 (same affected files atf5631b2). It is review text only. Tests may add the technical regression assertions described above without expanding behavior; any different behavior hunk requires another owner decision.

<!-- P1_EXACT_DIFF -->

```diff
--- a/backend/src/knora/providers/openai_compatible/generation.py
+++ b/backend/src/knora/providers/openai_compatible/generation.py
@@ -25 +25 @@
-CLOUDFLARE_PROMPT_VERSION = "cloudflare-gpt-oss-cited-answer-v17"
+CLOUDFLARE_PROMPT_VERSION = "cloudflare-gpt-oss-cited-answer-v18"
@@ -39,2 +39,7 @@
-    "omit important conditions, or infer unsupported members. Retain conditional context. "
-    "Answer only the question's scope. Count questions follow the count rules below. "
+    "omit important conditions, or infer unsupported members. For lists, keep relevant source "
+    "conditions on an individual member in that item's text. Put relevant shared source "
+    "conditions not already stated in before or items in after, with all supporting aliases; "
+    "use after=[] only when no such conditions remain. "
+    "Answer only the question's scope, including source conditions that govern the total, "
+    "member inclusion or applicability of a listed structure. "
+    "Count questions follow the count rules below. "
--- a/backend/test/providers/openai_compatible/test_generation.py
+++ b/backend/test/providers/openai_compatible/test_generation.py
@@ -275 +275 @@
-    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v17"
+    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v18"
--- a/backend/test/providers/openai_compatible/test_presentation_generation.py
+++ b/backend/test/providers/openai_compatible/test_presentation_generation.py
@@ -137 +137 @@
-    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v17"
+    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v18"
--- a/backend/test/providers/openai_compatible/test_application_integration.py
+++ b/backend/test/providers/openai_compatible/test_application_integration.py
@@ -183 +183 @@
-            "cloudflare-gpt-oss-cited-answer-v17"
+            "cloudflare-gpt-oss-cited-answer-v18"
```

<!-- END_P1_EXACT_DIFF -->

## 5. Acceptance criteria and evidence reuse

| ID | Required outcome | Current gap |
| --- | --- | --- |
| AC1 | Count question without “hãy liệt kê”: natural lead, bold proven number/unit, individual chapter bullets; no hardcoded question/count/title logic. | Q20 format/order succeeded once; qualifications fail. Seven is source-derived expected evidence, not a product constant. |
| AC2 | All material assertions/members/totals/conditions supported; no dropped conditions, concealed incomplete members, duplicate members, or “may/should” promoted to “must”. | Q20 merge/split FAIL; older general-list conditional-index/support FAIL. |
| AC3 | Source order and all necessary citations; correct source/version/page/locator; chip after last consecutive shared-source group where possible, no source discarded to reduce repetition. | Single-source Q20 mapping reusable; actual support of each new output must be reviewed. Mixed/repeated aliases retain offline coverage. |
| AC4 | “Báo cáo cần có những phần nào ngoài các chương nội dung?” gives distinct, supported bullets in source order with conditional indexes/appendices intact. | No v17 success; older v8 is not final-policy acceptance. |
| AC5 | “Mục tiêu chung của mọi báo cáo là gì?” gives concise prose about a comprehensive view of group research/implementation, without unrelated chapter outline. | No v17 runtime result. |
| AC6 | Real Edge1440×960 and mobile viewport390×844: inspect actual screenshots/DOM, visible bullets/bold, no clipping/overflow/raw markers/duplicate chip artifacts; open every resulting citation/source. | Q20 DOM is partial evidence, not comprehensive visual QA/physical phone proof. |
| AC7 | Preserve169/178 language, source excerpts/history, citation validation/mapping, refusal and Workspace access. Invalid generation stays error, not repair or fabricated refusal. | Existing regression baseline; rerun affected/full gates for changed candidate. No extra live refusal/ACL requests by default. |
| AC8 | Correlate exact code/prompt/schema/provider/model/cap/config/source through both payloads→Markdown→Turn/trace→DOM. Final tests/format/review/CI pass; failures/skips/unknown cost reported. | Q19 technical pass is historical; new code/base needs fresh gates. |
| AC9 | Authorized bounded physical ledger, fresh fail-closed account/Free/quota, isolated OAuth/runtime, cleanup; explicit accepted retrieval scope. | No active permission. Q18 deviation cannot be repaired retroactively; actual request-specific costs unknown. |

**Retrieval decision before acceptance:** Default `retrieval-m1-v1` did not supply the full outline in the observed case. Owner must choose containment-scoped183 acceptance with the default gap explicitly retained separately, or require the default path to pass before183 acceptance. Recommend keeping retrieval implementation separate and accepting a scoped claim only if owner expressly agrees. Never silently pass M1, enable containment in production, create a new blocker/Issue or waive an AC.

For a changed generation policy, reuse Q20 as historical composition/mapping proof, not semantic acceptance of changed policy. Run only the three required cases once on the final candidate; count must return because it is a known failure. Do not repeat old model/schema experiments or ingestion. If code stays unchanged, two more cases cannot satisfy AC2.

The fixed acceptance questions are:

1. `Báo cáo dự án phần mềm được gợi ý trình bày bao nhiêu chương?`
2. `Báo cáo cần có những phần nào ngoài các chương nội dung?`
3. `Mục tiêu chung của mọi báo cáo là gì?`

For question2, source review must account for cover/information pages, contents/index pages, abstract, references and required appendices without duplicating overlapping categories. Figures/tables/formula or symbol indexes remain conditional where the source says “nếu có”. Do not require incidental abstract-length detail merely to name report parts; any extra asserted detail still needs source support. Citation excerpts are bounded previews: inspect the original PDF/full cited evidence before deciding a condition is absent.

## 6. Phase graph and current status

```text
P0 baseline/Master -> owner approval -> P1 offline remediation decision
P1 exact design approval -> P2 implementation/regression/CI -> P3 offline readiness
P3 + separate owner live allowance -> P4 provider/browser/source verification
P4 all ACs PASS -> P5 independent review/owner acceptance
P5 + separate integration approval -> P6 integration/handoff
P4 failure -> close window/report; no automatic new code direction or live window
```

| Phase | Status now | Completion boundary |
| --- | --- | --- |
| P0 | Accepted by owner atf5631b2. | Approval recorded in183; seven phases retained. |
| P1 | Offline investigation complete; exact proposal4.2 awaiting owner choice. | Decision/approval remains before P2; no product edits/inference. |
| P2 | Blocked by P1 design/execution approval and shared-file ACK. | Technical pass, not semantic acceptance. |
| P3 | Offline preparation follows approved P2 envelope/technical pass; pending that gate. | Offline readiness, not OAuth/live permission. |
| P4 | Not authorized; Q21 postponed. | Finite measurement complete; quality may still FAIL. |
| P5 | Blocked by quality pass/final CI. | Explicit product acceptance, not merge. |
| P6 | Not authorized. | Actual approved integration; deployment separate. |

### P0 — Evidence baseline and single Master

**Dependencies:** Current planning request; zero inference.

**Deliverables/files:** This Master; historical-plan pointer and short notices in evidence docs; committed link in183, Q20 semantic correction, Q21 postponement.

- [x] Audit current decisions/code/captures/source and classify failures versus unknowns.
- [x] Validate five documents,24 local links, phase/AC/permission coverage and docs-only diff. Publication is identified by this file's Git commit and the #183 link/readback, not by self-approving the document.
- [x] Obtain owner review before any implementation Goal; P0 accepted and P1 offline authorized in the approval record above.

**Tests/acceptance/DoD:** One forward plan, Q1–Q20 accounted for, known blocker visible, `git diff --check` and local-link checks pass; no source/runtime/test/config change. Publication does not approve P1.

### P1 — Offline source-fidelity remediation design

**Dependencies:** Owner approves Master and explicitly starts P1 offline; original source/captures available.

**Deliverables:** Update sections3/4/phase status here with digest-bound Q18/Q20 comparison, source expectations, exact smallest proposed diff, impacted callers/tests, alternatives/limits and owner choice. Private source remains ignored.

- [x] Read original PDF p.1–2 and relevant index guidance; record PDF digest/version/physical pages and actual request E2 identity. Missing capture stays unavailable, not reconstructed from memory.
- [x] Replay captured Q20 final JSON through `compose_answer` offline; confirm conditions absent before composition. Compare existing `test_fixed_slots_render_one_list_between_supported_paragraphs` so supplied-condition preservation is not implemented twice.
- [x] Freeze count/general-list/short expectations, merge/split conditions, conditional indexes and all needed supporting sources. Expected facts stay in verification evidence, never product matching code.
- [x] Evaluate routeA once as an exact policy/generation proposal with an identified ambiguity/priority hypothesis and before/after diff. Compare routeB's burden without implementing it. Keep current schema/model/cap unless owner chooses a different design.
- [ ] Use `grilling` to present concrete route/tradeoffs and await approval before P2. Resolve retrieval acceptance scope before a live acceptance claim.

**Tests:** Existing composer/qualifier fixtures and offline captured-payload replay; static caller/version/schema comparison. These establish preservation/contract facts only. Do not invent a failing “model semantics” test whose fixture already supplies the desired text.

**Acceptance/DoD:** One approved implementation design or a completed investigation explaining why no justified bounded fix exists. Exact model-internal cause remains unknown. No adequate route means P2 blocked, not an excuse to waive AC2 or spend quota.

### P2 — Approved minimal implementation and regression

**Dependencies:** P1 exact design + P2 execution approval; explicit overlap ACK from191.

**Deliverables/files:** Approved subset of section4 files; all affected caller/fixture/test updates, version/provenance change when policy changes, ADR/CONTEXT for confirmed decisions; candidate SHA and191 porting diff.

- [ ] Search every caller/import/fixture of changed symbols and list scope before editing.
- [ ] For changed deterministic behavior: meaningful failing test→observed RED→minimal shared fix→GREEN. For prompt-only changes: outgoing policy/version/envelope tests and qualifier-preservation composition checks, explicitly not model-compliance proof.
- [ ] Reuse existing tests; add only missing boundary regression: supplied qualifiers, mixed/repeated aliases, nullable/missing bold, literal Markdown, singleton/prose, refusal all modes, bad alias, truncation/HTTP/no retry/input immutability.
- [ ] Run focused provider/application/PostgreSQL then section8 full/format/config checks; fix in-scope technical defects without skips, relaxed deadlines/guards or model/cap changes.
- [ ] Independent code review; repair findings within approved behavior. A new UX/schema/algorithm/dependency direction stops for owner decision. Push, verify required CI and publish exact diff/results/limits to183/191.

**Tests/acceptance/DoD:** Approved diff and all affected fixtures/callers complete, meaningful regressions/full applicable gates green, no unresolved actionable review finding, CI required SUCCESS at candidate. Semantic correctness remains P4. No provider/runtime/production change.

### P3 — Offline runtime readiness and fail-closed proof

**Dependencies:** P2 technical pass and approved P2/P3 offline envelope, sufficient-evidence acceptance scope and read-only corpus identity verification. Owner authorized preparing P3 after the exact P2 design is approved; no inference/OAuth is implied.

**Deliverables/files:** Reuse private Q20 guard/helpers/tests in ignored183 evidence; readiness result and exact live proposal linked here. No product or generic framework change.

- [ ] Exercise actual sync/async adapters through MockTransport, UTF-8 reads and Windows child-import self-check. Missing/stale/future/wrong account/Billing/quota, paid/unknown plan/budget, wrong host/model/cap/schema, document embedding, duplicates, stopped/exhausted window and timeout must block unauthorized sends.
- [ ] Propose at most9 physical requests:3 query embeddings+6 generations. Enforce per-kind/total before send; exclusive durable admissions; no worker/transport retry. Count errors/indeterminate sends; unknown outcome closes the window.
- [ ] Keep600s freshness; timestamp each observation at actual read, bind digest/window/candidate, check before every send. Prepare worker/browser first. Fresh reads between healthy cases require explicit live-envelope permission; never renew after denial/stop or relabel old timestamps.
- [ ] Verify safe status/error-body/finish/usage/latency capture. Failed Turns without traces remain without traces; no invented IDs. Test repaired guard branches before reuse.
- [ ] Document ownership of own3183/8183, localhost cookie/session isolation, normal PKCE, exact additive local OAuth readback/cleanup and untouched primary3000. This offline phase does not itself authorize OAuth mutations.
- [ ] Submit exact candidate/CI, source, questions, account/Free/quota method, ceiling, stop rules and OAuth scope for owner approval. No grant from this Master alone.

**Tests/acceptance/DoD:** Denial tests prove zero unauthorized sends; valid simulated sequences bounded; duplicate/timeout cannot reopen. Existing38 Q20 tests reused/adapted, count honestly. Zero real embedding/generation. Readiness is not P4 permission.

### P4 — Bounded real provider/browser/source verification

**Dependencies:** Separate owner approval for exact candidate, proposed≤9 physical requests, paid budget0USD, runtime-only retrieval profile and temporary OAuth scope; P3 and CI pass, login/fresh gates hold. Unknown prerequisites mean zero requests.

**Deliverables:** Immutable sanitized report linked here/183; private correlated payloads/Markdown/Turn/trace/screenshots, per-request accounting, failures/unrun cases, cost uncertainty and cleanup readback.

- [ ] Reuse23 chunks/vectors. Three new conversations: AC1 count first, AC4 list, AC5 short; each≤1 query+1 selection+1 answer. No ingestion/direct replay/reask/repair/retry.
- [ ] Freshly read and individually timestamp account/Billing/Workers Free/quota before each case; coordinate shared quota, verify exact candidate/prompt/schema/model/cap. Guard remains active before each send. No actual-cost0USD claim from policy or absent usage.
- [ ] After each answer, **before next case**, compare every material assertion/member/condition/order with PDF and supplied evidence. Count needs suggested-outline/both merge-split qualifications; general list needs conditional indexes/all sources. Semantic error stops even when public validator passes.
- [ ] Correlate both payloads→Markdown→Turn/trace→DOM. Inspect actual Edge screenshots1440×960/390×844, every citation/source/version/page/support, raw markers, duplicate chips and overflow. Reading stored Turns/source adds no model calls.
- [ ] Any provider/schema/token/content/condition/order/citation/format error or stale admission denial stops whole window; expire unused allowance and retain failures. Do not continue to seek a better result.
- [ ] Cleanup exact window-owned OAuth additions using fresh representation preserving concurrent changes; stop only owned processes/reset viewport/confirm primary untouched; report actual physical count and limits.

**Tests:** The three real-provider questions, original-PDF assertion/qualification review, both-stage payload-to-public-result correlation, desktop/mobile visual/DOM/source-opening checks and post-run admission/cleanup audit. No fixture or prompt-string assertion substitutes for these checks.

**Acceptance/DoD:** A completed report can have quality FAIL. Quality PASS requires all ACs and three final-candidate cases in explicitly approved retrieval scope. Failure blocks P5 acceptance and requires new owner decision, not Goal continuation/increased complexity or a fresh allowance.

### P5 — Final review and product acceptance readiness

**Dependencies:** P4 quality pass, retrieval-scope disposition, cleanup and final technical gates.

**Deliverables:** AC evidence matrix referenced here; accurate184 body/review, exact SHAs/checks/limits and owner acceptance request. Correct generated-summary overclaims; preserve failure history.

- [ ] Link every AC to actual source/runtime/browser/regression evidence; confirm no hardcoded product questions/counts or history/source edits.
- [ ] Independently review full connected184 diff/callers, citations/refusal/error/other-provider behavior. Repair deterministic findings in scope. Behavioral changes invalidate affected runtime evidence and need approval before new live calls.
- [ ] Run applicable section8 gates at actual final code/base; investigate CI failures without weakening tests. A passing isolated rerun does not convert an earlier failed full run into a pass.
- [ ] Refresh191/200 upstream relationships, publish ready-for-acceptance packet and await explicit owner scope acceptance. Keep Draft until owner PR-state disposition; no merge/close/Done.

**Tests:** Section8 focused/full/config/format/CI checks on the final code, evidence provenance/AC coverage review and connected-code review. Reuse identical candidate results instead of rerunning them solely for a review checkpoint; changes trigger impacted checks.

**Acceptance/DoD:** No known semantic/format/citation blocker, applicable checks green and review findings resolved; owner explicitly accepts behavior and scope. A packet is not acceptance. Narrowing/waiving an AC needs an explicit changed owner decision.

### P6 — Separately approved integration and handoff

**Dependencies:** P5 owner acceptance; separate approval for base integration/merge strategy and eventual merge/closure disposition. No production deployment permission.

**Deliverables:** Actual184/main ancestry/diff/check record, authorized merge result if granted and191 exact upstream handoff.

- [ ] Read latest main/183/191/200 decisions. Resolve approved base integration in this worktree without importing191 extraction or rewriting another branch.
- [ ] Run impacted/full gates and required CI at integrated candidate; compare prompt/schema/composer/source identities to accepted runtime. Documentation-only or proven unchanged behavior need not repeat inference; relevant drift needs fresh separately approved targeted verification.
- [ ] Present final candidate/diff/checks for separate merge approval. No merge from Master approval, CI or Goal completion.
- [ ] After authorized184 merge, record actual main commit and notify191 via Issues. Its owner retargets200 only after accepted183 is proven in main, validates refactor-only diff/parity/CI and gets its own merge approval. Do not implement/merge200 here.
- [ ] Close/Done only on owner instruction; worktree/branch deletion needs AGENTS disposition. No automatic deployment.

**Tests:** Ancestry/diff and accepted-behavior identity comparison, section8 impacted/full checks and exact integrated-candidate CI; any applicable separately approved release profile. Inference is never implicitly authorized by a merge conflict or base update.

**Acceptance/DoD:** Integration complete only after actual authorized action/checks; beforehand “ready, awaiting owner”, not merged/Done. Scoped183 acceptance remains distinct from default retrieval or production rollout.

## 7. Permissions and Codex Goals contracts

| Action | Permission now | Future gate |
| --- | --- | --- |
| Read/audit/write/publish this Master/pointers | Authorized current task. | Documentation only. |
| Create/start phase Goal | P1 authorized; overall owner Goal already active. | Goal API allows one unfinished objective/thread; retain full objective and record bounded phase outcomes here rather than falsely completing it. |
| P1 offline design/replay | Authorized; investigation/proposal delivered. | No product edits/inference; exact P2 decision pending. |
| P2 code/tests/review/repair | Not granted by publication. | Exact P1 design/P2 envelope approved, overlap ACK. |
| Small technical decisions | Autonomous inside approved phase. | Test names/fixtures/UTF-8/local commands/deterministic fixes that preserve approved behavior; no permission question per edit. |
| New UX/schema/algorithm/dependency/fallback/model/cap/module boundary | Owner decision. | `grilling`: facts, choices, effects, recommendation; explicit response before dependent work. |
| OAuth/runtime mutation/inference | None; old windows closed/Q21 postponed. | Exact approved window and fresh fail-closed preflight. Free quota is not consent. |
| Default retrieval/production/account/billing changes | None. | Separate proposal/approval; no containment rollout by inference. |
| Product acceptance/Draft change/merge/closure/Done/deployment | None. | Explicit owner disposition at each applicable boundary. |

Owner requested **one finite Codex Goal per approved phase**; the current API supports one unfinished Goal per thread and already holds the owner's complete P0–P6 objective. Keep it active without redefining completion as P1. This is a tool limitation, not authority to skip phase gates: each finite outcome below remains separately tracked here and starts only with its approved envelope. Do not create a duplicate thread/roadmap or falsely complete the overall objective to replace it. Set no token budget unless explicitly supplied.

Finite Goal outcomes:

- **P1:** Complete offline Q18/Q20 source comparison and one concrete remediation recommendation; stop at owner choice, zero product edits/inference.
- **P2:** Implement approved diff, regress/review/repair technical defects and deliver exact candidate with required CI; no live/runtime/production rights.
- **P3:** Prove guarded MockTransport/readiness and prepare exact live proposal; no physical send/unapproved OAuth mutation.
- **P4:** Execute only the approved bounded window, reconcile admissions/source/browser evidence/cleanup, stop with quality pass/fail. Goal completion measures execution, not quality acceptance.
- **P5:** Deliver reviewed acceptance packet and obtain owner disposition; no inference/merge/implicit waiver.
- **P6:** Perform only specifically approved integration actions/checks/handoff; no automatic deployment/200 changes/branch deletion.

Normal RED/GREEN/fix/review is autonomous within an approved offline envelope. Repeated failures requiring new behavior or an outside dependency stop dependent work for owner decision. Auto-continuation cannot reset request counters/stop files, renew windows, retry indeterminate sends or accept failed ACs. Do not mark a Goal complete merely because its budget/time is exhausted. Update phase status/evidence here and publish a concise Issue checkpoint, not another plan.

## 8. Verification and reporting

Run from this worktree with its existing virtual environment and isolated ready test DB, never primary5432 or another task's DB. Any proxy cleanup is test-process-only and reported.

```powershell
.\.venv\Scripts\python -m pytest backend/test/providers/openai_compatible
.\.venv\Scripts\python -m pytest backend/test/adapters/postgres/test_cloudflare_application.py backend/test/answering/test_generation_validation.py
.\.venv\Scripts\python -m ruff format .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python scripts/export_openapi.py --check
docker compose config --quiet
git diff --check
```

Shared maintained files selected in frontend/package.json require `npm --prefix frontend run format:shared` then `format:shared:check`. Maintained frontend edits also require `format`, `format:check`, `test`, `typecheck`, `lint`; no frontend code edit is planned. Never hand-edit generated OpenAPI. Follow [CI runbook](../../runbooks/ci.md), including Java/report gates, without bypasses.

For Markdown-only planning, validate local links, AC/phase/permission consistency and diff; broad application/model tests add no evidence. New product code/base requires fresh applicable full gates/CI at actual candidate/merge snapshot. Preserve commands, environment, durations, exit codes, skips and original failures; historical totals are not fresh passes.

If integration requires a repository Runtime Verification release profile, propose applicable `application` run separately at exact subject SHA/current runbook. Synthetic profiles do not replace real Cloudflare/PDF semantics. OTP is not required solely because browser login is used. Do not borrow unrelated/old profile manifests as183 evidence.

Each phase result records approval link, Master commit, candidate/base, files, source/version/digests, prompt/schema/model/provider/cap/retrieval identities, commands/results, safe window/Turn/trace/citation IDs, physical attempts/errors/unknown usage, artifact links/hashes, limits and next **authorized** action. No tokens/auth URLs/raw reasoning/private source in public records. Aggregate usage is not per-request actual cost.

## 9. Definition of Done and owner review frontier

**Technical complete:** Approved minimal implementation, affected/full checks and required CI pass; no unresolved actionable review finding; identities documented. Does not mean model fidelity accepted.

**Product accepted:** AC1–AC9 pass on final candidate within explicit owner-approved retrieval scope, including merge/split qualifications and other-list/short runtime cases; owner accepts evidence/limits. Three cases demonstrate those cases, not universal semantic accuracy/stability.

**Integrated:** Actual separately authorized184 integration/checks and main SHA recorded;191 receives exact handoff. Production rollout/200 merge remain independent. Issue closure/Done needs owner disposition.

Owner review decisions:

1. **Resolved:** Owner approved Master v1 atf5631b2, kept P0–P6, accepted P0 and started P1 offline. Existing active overall Goal/tool limitation is recorded in section7.
2. After P1, approve exact generation remediation and P2 envelope; existing-contract reuse recommended, no particular prompt/schema patch is approved here.
3. **Resolved in P1 authorization:**183 accepts generation with sufficient supplied evidence; default-M1 retrieval belongs to153. P4 must still pin and separately approve its runtime-only retrieval profile; no rollout/default-M1 acceptance.
4. Prepare P3 offline inside the approved P2/P3 envelope; separately approve P4 OAuth/runtime/live allowance once exact candidate/readiness exists. Proposed9 calls are not a grant.
5. After evidence/review, decide product acceptance, PR state, integration/merge/closure separately. Silence and green CI are not approval.

**Immediate next action:** Owner reviews the exact P1 proposal in4.2 before P2 behavior changes; obtain191 overlap ACK before edit. Q21 stays postponed; no inference/OAuth/cost/production/merge permission is granted by P1 completion.
