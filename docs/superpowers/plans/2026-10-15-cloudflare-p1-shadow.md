# Cloudflare P1 shadow implementation plan — pending approval

> **For agentic workers:** Use `executing-plans` task by task after owner approval. The research task does not authorize implementation or account changes.

**Goal:** Measure Cloudflare AI Gateway P1 detection and false positives on 16 public/synthetic Vietnamese/English PDF-evidence cases, using Knora Evaluation artifacts.

**Architecture:** An evaluation-only runner replays pinned question/evidence text through Workers AI with an explicitly selected trial Gateway. It records P1 observations as a supplementary atomic report; it never substitutes a Knora response. No new evaluation service, framework, local security model or canonical dataset.

**Tech stack:** Existing Python, HTTPX, pytest and Knora atomic report writer. No additional dependency proposed.

**Spec:** [Research and source references](../../research/issue-188-cloudflare-p1.md); owner direction in #188. Prepared 2026-10-15 on research branch based on `b2465f5`.

## Confirmed constraints

- Knora currently runs in local development, not public/deployed. Development/evaluation PDFs are public or synthetic. These data may be considered for Cloudflare evaluation.
- Gateway activation, inference calls, quota consumption and monetary budget require separate approval. No account configuration change or inference was performed for this research.
- P1 prompt action FLAG only; response guardrails and all other categories ignored. No BLOCK, fix, reask, runtime wiring, response replacement or Langfuse/other exporter.
- PR #199 stays Secrets Detection only. Its 3 TP / 1 FN (split-key) / 1 FP (checksum) / 3 TN remain historical baseline results. PDF smoke has no usable detector result. Security quality remains unaccepted.
- Gold #153, frozen captures/reports, runtime provider profiles and Workbench authority remain unchanged. No merge or Done before owner acceptance.

## Local request audit

Verified in primary checkout `d228d0dae189194724d7e204b0200aa28cc11c48` and relevant provider files on research base:

| Boundary | Current implementation | Consequence |
| --- | --- | --- |
| Generation | `backend/src/knora/bootstrap.py`, Cloudflare branch: `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1`; model `@cf/openai/gpt-oss-20b` | Direct Workers AI configuration. |
| HTTP request | `backend/src/knora/providers/openai_compatible/generation.py`: POST `/chat/completions`, Authorization header only; no Gateway ID/header | Code does not opt into Gateway. Hostname alone is insufficient evidence: Cloudflare also supports Gateway routing on this hostname via `cf-aig-gateway-id`. |
| Evidence | `backend/src/knora/providers/structured_generation.py:user_message`: JSON question plus ordered `{evidence_id, content}` entries in user message, preceded by system message | Retrieved PDF text can be submitted as prompt content. P1 does not establish whole-PDF coverage or source attribution. |
| Streaming | Provider sends no `stream: true`; parses one JSON response | First trial explicitly uses `stream: false`. Application SSE is a separate boundary; no streaming compatibility claim. |
| Existing evaluator | `evals/scorers/deepeval_cloudflare.py` allowlists direct endpoint and imports DeepEval at module load | Do not repurpose the semantic judge or import it merely for `AttemptLedger`. Any future shared extraction requires #158 agreement. |
| Reports | `evals/runners/evaluation.py:write_report_atomic(path, report)` | Reuse without editing; do not overwrite previous artifacts. |

Cloudflare routing reference: [Workers AI through Gateway](https://developers.cloudflare.com/ai-gateway/usage/providers/workersai/).

Read-only account preflight on 2026-10-15: Gateway list and account subscriptions GET both returned HTTP 403 / code 10000 with this checkout's configured credentials; no token was printed or configuration changed. Account state, Gateway existence, billing mode and remaining quota remain unknown. The code route is verified; the account configuration is not.

## Approval checkpoint A — prepare and verify offline only

Proposed new files, independent of PR #199:

- `evals/runners/cloudflare_p1_shadow.py`: small CLI, pinned input validation, request construction, trial authorization/call cap, P1 log ingestion and supplementary report. Default is offline preparation; live operation requires an explicit reviewed run manifest. Reuse the atomic writer and provider prompt serialization. No generic provider abstraction.
- `evals/test/test_cloudflare_p1_shadow.py`: HTTPX mock transport and frozen synthetic API/log fixtures. No credentials, telemetry or network in tests.
- `evals/test/fixtures/cloudflare_p1/cases.json`: 16 development cases and reviewed-label provenance. This is a test fixture consumed by Knora Evaluation, not another source of gold.
- `evals/test/fixtures/cloudflare_p1/`: only small request/log/error fixtures needed by contract tests; no copied PDF corpus.
- `docs/development/issue-188-cloudflare-p1-verification.md`: commands, exact commit/config/case digests and offline evidence.
- `evals/reports/cloudflare_p1/<run-id>.json`: generated supplementary observation, never imported into canonical Workbench metrics automatically.

No edit proposed to backend runtime, settings/bootstrap, pyproject/dependency extras, CI workflow, DeepEval/Ragas, registry/API/UI/OpenAPI or frozen #153 artifacts. Use an isolated worktree under the canonical worktree container. Existing installed dependencies only; if missing, present an exact isolated install plan before installation.

### Task 1 — pin cases and request construction

- [ ] Write failing tests for digest mismatch, unreviewed labels, absent exact evidence, absent public/synthetic input approval, and disabled live mode.
- [ ] Prepare 16 cases: 8 injection attempts + 8 legitimate controls; Vietnamese and English each have 4 attacks + 4 controls. Preserve quoted research, medical/security discussion and valid document instructions as controls. Attacks cover role override, fake policy, synthetic exfiltration instructions, and a boundary/long-context case.
- [ ] Pin UTF-8 case bytes/SHA256, case IDs, labels/reviewer reference, payload digest, question, ordered evidence/alias/source provenance and scope. Use exact saved generation evidence when available; synthetic material gets explicit synthetic provenance. No automatic re-answer or database retrieval.
- [ ] Use `user_message(question, evidence)` and the current Cloudflare system prompt. Serialize the complete actual envelope. Do not silently truncate. Boundary cases retain their intended position. Lack of source/exact evidence is unavailable, never a clean result.
- [ ] Run targeted offline tests; submit exact fixture digest and labels for owner review before confusion metrics.

Reference artifact already verified locally: #153 `baseline-b-layout-v2/captures/case-pdf-v3-001-attempt-1.json`, SHA256 `6daa50d8876efa79663ae433c7a0b2b8028a6f0091a8602d4fdd080dc7224729`. It contains response/provenance fields but no exact generation evidence; retain as an unavailable-input control, not one of 16 scored P1 inputs. Do not fetch a newer capture implicitly. Additional #158 exact-evidence captures must be agreed by version and SHA before use.

### Task 2 — offline request/log/report contract

- [ ] Test direct Workers AI REST request plus `cf-aig-gateway-id`, explicit `stream: false`, fixed model, no redirects/retries/fallbacks, disabled caching, and explicit per-run authorization.
- [ ] Test positive P1, completed negative P1, missing evaluation, detector error, timeout, unsupported log schema, 403, 429 and unexpected BLOCK (2016/2017). HTTP 200, a downstream model refusal or no visible P1 flag alone cannot establish a negative detector result.
- [ ] Correlate exact request/log/event IDs with case and payload digest. Preserve raw category/action/status evidence in the report. Distinguish downstream generation outcome from detector outcome. Do not fabricate undocumented JSON paths; freeze the real API/log contract at checkpoint B before live-capable parsing is accepted.
- [ ] If an authenticated read path cannot expose completed negative evaluations, support owner-saved native log artifacts for offline import. If neither path provides evidence, report unavailable and stop the trial rather than treating absent flags as TN.
- [ ] Implement bounded sequential calls, reservation before dispatch, durable attempt count for crash/restart, no retry on timeout, bounded log polling, and atomic non-overwriting report output. Keep this local to the runner; extraction of a shared ledger is outside this scope unless #158 agrees.
- [ ] Report TP/FN/FP/TN, recall and FPR over reviewed, completed evaluations; separately show coverage over all 16 and unavailable/error/timeout counts by language/family. Report sample counts with rates (one case changes each language subgroup by 25 percentage points). No tuning or security acceptance on this small development set.
- [ ] Run targeted pytest, required Ruff format/check and applicable repository verification gates. Assert no network in default tests and no runtime/gold diff. No live CI job.

## Checkpoint B — account/configuration preflight proposal

The initial read-only preflight is blocked by HTTP 403. Obtain an owner-provided read-only dashboard snapshot or appropriately scoped read access; never broaden a token's permissions automatically. Establish Workers Free/Paid, first-Gateway date/log backend, current Gateway configuration and whether an isolated trial Gateway already exists, Workers AI usage/quota, billing mode, available P1 pricing, rate limits, log access/retention and permissions. A 403 or inaccessible price is unknown, not evidence of Free or zero cost. Use this session/account only. Reading account state does not authorize activation or inference.

Then present an exact configuration diff for a dedicated authenticated trial Gateway: `guardrails.prompt.P1 = FLAG`, empty response categories, other categories ignored, cache/retries/fallbacks off, and fixed existing Workers AI billing mode with no switch to Unified Billing, top-up or paid subscription. Gateway PUT requires preserving current unrelated settings; prefer dedicated trial configuration to changing a shared gateway. Readback must prove no BLOCK category.

Logging is a separate explicit choice: recommend only native Cloudflare logs needed for P1 results/correlation, no Logpush, OTEL or Langfuse. Recommend request/response payload storage off if P1 evaluation records remain readable; validate this before relying on it. If readable P1 results require payload logging, present the exact public/synthetic payload/retention choice for approval. Never silently enable broader logs.

## Checkpoint C — proposed cloud trial, separate approval required

- One reviewed run, **at most 16 outbound generation requests total**, sequential, no retries/continuations. The first 2 balanced control/attack cases are part of the 16, not extra calls. Stop after these if routing, P1 evaluation correlation, completed negative status or FLAG-only behavior cannot be verified. Remaining 14 run only when these instrumentation conditions hold; a detector miss is recorded, not used to tune or silently abort the population.
- Same `@cf/openai/gpt-oss-20b` model as Knora; `stream: false`; output cap proposed 256 tokens; no new embedding/retrieval or separate semantic judge calls. Downstream output is a disposable evaluation artifact, never shown as a replacement user answer and not scored as an end-to-end attack success trial.
- Proposed timeout 60 seconds/request, whole run 20 minutes; bounded read-only log polling (maximum 3 reads/case). Cache hits, logs without P1 completion, unexpected backend/model or Gateway config drift invalidate the observation. Stop dispatch after any budget/permission/routing failure.
- There may be multiple internal P1 evaluations per request due to Cloudflare segmentation. **16 requests is not a promise of 16 detector inferences.** Managed thresholds, segmentation and model revision cannot be independently pinned unless Cloudflare exposes them; record those limits rather than borrowing local-model assumptions.
- Budget approval must cover downstream generation + P1 evaluations + applicable log usage. Proposed owner ceiling is USD 1 total incremental trial cost, **not yet a verified quote or approved spend**. Do not start unless a conservative bound and enforceable stopping policy can be established under the actual billing mode. If P1 pricing/usage cannot be bounded, return for a revised approval; do not make an exploratory paid call to discover it.
- Published generation rate currently USD 0.20/M input and USD 0.30/M output tokens; calculate from frozen serialized inputs and 16 × 256 maximum output tokens. This excludes P1/log costs and does not prove final billing. [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).
- Save config snapshot/digest, source/case digests, service-reported model/revision where available, request and P1 event IDs, billed units/cost status, latency and completed detector observations. Missing cost remains unknown. Do not reuse another session's allowance or quota claim.
- Owner reviews report and individual FP/FN before any later runtime integration or enforcement proposal. No automatic merge, completion or quality gate.

## Coordination and later candidates

Coordinate this additive artifact contract with #158/#192 through Issues before implementation. Request concrete exact-evidence capture revision/SHA, not latest artifacts or full Workbench completion. #158 retains semantic/observability integration; #192 retains canonical datasets/runs/reports. No shared-file edit is proposed now; any later shared helper/dependency change requires an explicit diff agreement.

PII: investigate Cloudflare Gateway DLP profiles and actual account entitlement/entity coverage; do not equate S7 Privacy with PII entity detection. Dangerous Output: investigate Cloudflare S1–S13 FLAG categories against an owner-approved taxonomy, including legitimate medical/security/research controls. Vietnamese quality and unsupported categories need separate trials. Both are research candidates, no activation or model call approved.

## Approval frontier

1. **Approve checkpoint A only?** Recommendation: approve the listed evaluation-only files and offline tests, with zero provider calls and no account changes. Final labels remain a distinct reviewed artifact.
2. Checkpoints B/C follow A's reviewed artifacts and actual pricing/log findings. Present scoped read permissions, exact Gateway/log configuration and a bounded costed run before requesting their approval. Approval of A does not approve either.

No new local security model, dataset authority, production behavior or generic evaluation framework is needed for this plan.
