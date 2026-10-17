# Evaluation Workbench takeover checkpoint — 17 October 2026

Status: implementation and acceptance remain separate. No quality acceptance or release is claimed.

## Verified baseline

- Worktree: `C:/Developer/Projects/knora-agent-worktree/issue-192-evaluation-workbench`.
- Branch: `codex/issue-192-workbench-contract`; takeover HEAD
  `7ee019d4d755fe2adcd8e4a4949671782323d577`; working tree was clean before this follow-up.
- [PR #202](https://github.com/NhiBuaa/knora-agent/pull/202) remains Open/Draft.
  All six checks, including CI required, succeeded for that exact SHA in
  [CI run 38916031299](https://github.com/NhiBuaa/knora-agent/actions/runs/38916031299).
  The GitHub review and inline-comment lists were empty at takeover; earlier independent review
  claims refer to development evidence, not a formal GitHub approval.
- [PR #190](https://github.com/NhiBuaa/knora-agent/pull/190) merged on 15 October. That does not
  accept the quality gate of #158 or the Workbench product.

This checkpoint supersedes older pending-CI, missing-corpus-adapter and missing-UI-launch statements
in the implementation plan and earlier PR checkpoints. It does not turn those historical checks
into current verification or extend their scope.

## Accepted fixture and saved execution

The latest [UI checkpoint](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6219118185)
records a new run started from the Runs UI using the
[owner-approved fixture](https://github.com/NhiBuaa/knora-agent/issues/195#issuecomment-6207368916):

| Identity or result | Retained evidence |
| --- | --- |
| Dataset / version | `a7330648-8b01-4895-abc4-0818ae444c0a` / Gold v1 |
| Gold digest | `fc9f3ffedefd421b3db588f048829f2e9f28da76269146422fb1f12a511e208e` |
| UI run | `faacf17180f24a2bb5ab6c9e36917c6a` |
| Profile | `deterministic-pdf-v1` |
| Execution / quality | COMPLETED / SEMANTIC_PENDING |
| Populations | dataset 2, selected 2, context-only 0, attempted 2, observed 2, applicable 1, evaluable 1 |
| Retrieval group coverage / generation diagnostic | 0/1 / 0/1 |
| Expected ANSWER case | REFUSAL, zero candidates; trace `f3730b6e-3bc6-4aa8-9cac-811e5f908288` |
| Expected REFUSAL case | REFUSAL, retrieval N/A; trace `4a57f649-7a4e-44d3-a816-5d321adc83a2` |

These are saved observations, not a current live session or quality PASS. There is no answer in
this run for DeepEval to score: the R2 mapping explicitly reports `NO_ANSWER_TO_SCORE` for the
false refusal and uses deterministic refusal checks for the expected refusal. Do not fabricate an
answer, lower a threshold, remove the missed case, or replay the historical run to get a score.
The prior failed run `f39ff79c93394accbb526ada94cfcb42` remains historical evidence.

## Runtime retention and availability

Read-only inspection found no listeners on the historical Workbench ports 3200, 18000 and 55432.
The native PostgreSQL 18 cluster remains under `%TEMP%/knora-wb-runtime-55432`, with no
`postmaster.pid`. `%TEMP%/wb-postgres-owner.log` ends on 16 October at 22:49:13 +07 after process
exceptions, failed startup recovery and "database system is shut down". This is evidence that it
stopped, **not proof of a clean shutdown or recoverable logical contents**. The cluster was not
started or queried during this audit.

The separate `%TEMP%/knora-wb-objects` store retains seven copies of the 2,309-byte synthetic PDF,
SHA256 `91c195401b5201a2d77fa01fbc65c4eb819572f36d195a4c881f6ccc52388ee5`.
Launch wrappers and the simulated-auth deterministic harness remain in `%TEMP%`. Saved report,
case and trace screenshots and `wb-ui-faacf171-checkpoint.md` remain there too. These temporary
files establish local retention only; screenshots were not visually reverified in this takeover.
The old READY preflight has expired and cannot authorize another run.

## Acceptance matrix

| Scope | Evidence already present | Still required |
| --- | --- | --- |
| #192 contract | Approved contract; source-backed immutable gold, selection, binding and metric semantics implemented | Owner product acceptance and final A3-to-R3 demonstration |
| #193 R1 | New deterministic UI Q&A, durable observations/report and exact trace links | Real-provider compatibility and applicable owner acceptance |
| #194 A1 | Retained PDF upload/extraction/source review; tests cover multiple-file partial retry and visible extraction failure | Additional multi-PDF/failure UI demonstration beyond the inspected single-PDF walkthrough |
| #195 A2 | Manual author/review/freeze UI; owner approved exact fixture content and digest | Simulated actor/time does not establish the real Keycloak approval path or broader acceptance |
| #198 R3 | Approved manual gold to fresh UI run/report/case/source/trace; false refusal remains in denominator | Missing/ambiguous binding and extraction-failure UI evidence; actual quality and owner acceptance. Ragas/DeepEval do not block its deterministic contract |
| #196 R2 | Exact saved-capture scoring and append-only batches; explicit missing/not-applicable reasons | Live judge compatibility, human comparison/calibration and owner acceptance. PostgreSQL contention follow-up is below |
| #197 A3 | Existing Ragas adapter mapped to retained PDF snapshots, bounded drafts, diagnostics and unreviewed A2 import | Authorized provider demonstration: PDF to proposals to human review/freeze, then parent A3-to-R3 demo |
| #158 | Earlier DeepEval/Ragas/Langfuse adapters technically integrated | Owner acceptance of real quality. Langfuse export stays OFF; activation/retention/deletion evidence is conditional on separate authorization |

Existing technical tests are evidence for the behavior they exercise, not substitutes for the UI,
identity, real-provider or owner acceptance requirements above. No issue is Done from this audit.

Project 5 reflects those remaining gates: #158/#192/#193/#194/#195/#198 remain In Progress;
#196 and #197 are Blocked for the remaining live/human evidence, as recorded in the
[R2 checkpoint](https://github.com/NhiBuaa/knora-agent/issues/196#issuecomment-6231074157) and
[A3 checkpoint](https://github.com/NhiBuaa/knora-agent/issues/197#issuecomment-6231076308).
The Blocked status of R2 does not add a DeepEval gate to deterministic R3 acceptance.

## PostgreSQL scoring contention follow-up

The new `test_evaluation_scoring_concurrency.py` uses two real database connections contending on
the same saved run. It proves same-request single dispatch ownership, preservation of distinct
reserved batches, and preservation of both concurrent batch checkpoints and saved Q&A/report.

The isolated test database is `knora_issue110_task2` on loopback port 55492 in disposable container
`knora192-scoring-tests`, label `knora.owner=issue-192-scoring-verification`, capped at 1 CPU and
256 MiB. It uses the already installed pgvector PostgreSQL 16 image and does not use the historical
Workbench cluster, #153 databases or daily services. Migrations through Workbench0051 applied only
to this disposable database; combined #153 ancestry remains an integration gate.
After verification, its exact container ID/owner label were checked and that disposable container
was stopped and removed. The retained native Workbench cluster and other containers were untouched.

- Initial table-only PostgreSQL run: 3 passed; this was insufficient to verify migrated constraints.
- Temporary in-memory mutation removing the store's row locks: all 3 failed for the intended
  duplicate-ownership/lost-update defects. No production source file was edited for that probe.
- First full repository run: 2,172 passed, 4 skipped, 3 fixture setup errors. All three errors were
  the new fixture missing the workspace required by the migrated evaluation_runs foreign key.
  Production behavior was not implicated. The fixture now creates its own UUID workspace, uses
  migrated tables without creating a reduced schema, and deletes its run before its workspace.
- After the fixture correction, normal scoring/store regression run: 19 passed. Repeating the
  row-lock mutation against the migrated schema produced the same three intended failures.
- Ruff format/check/lint: passed, 427 Python files checked.
- Independent review and follow-up review of the fixture correction: no actionable findings.
- Full repository pytest after the correction: **2,175 passed, 4 skipped, 26 warnings in 463.75s**.
  JUnit evidence: `%TEMP%/knora192-takeover-full-fixed.xml`. Warnings are the existing Alembic
  path_separator deprecation. Skips are three opt-in locked PDF acceptance fixtures and one
  explicitly enabled real Ollama grounding test; the new contention tests ran.
  OpenAPI exporter check, Compose configuration and diff check pass;
  Compose warns that local canonical MinIO credentials are unset. No application services started.
  The test interpreter is the existing local
  `.venv-eval` (Python 3.13.15), since this worktree has no `.venv`.

## Shared edits and activation boundaries

The exact #153 Q8 patch was reviewed and
[ACKed for S2 only](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6228374786), SHA256
`f3d5ca3519f434c2fb304dd0394fa05d8543f9ea7c498eeb395af8c0893f8b17`. Scope is lexical snapshot
revalidation before generation, its typed port, and strict schema3 validation/revalidation inside
the existing trace transaction. No Workbench shared file was edited. Subsequent main, reader,
OpenAPI, frontend and migration integration diffs need separate finite ACKs. The subsequent
[four finite ACKs](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6231034695)
cover only the supplied S2 retrieval facade, document readiness projection, three generated
OpenAPI artifacts and operator UI patches, with exact hashes and required post-application gates.
They do not cover later wiring, tie policy, parent-child linkage or runtime acceptance. #188 remains the
consumer/projection owner for its shadow outputs; no enforcement or canonical contract expansion.

Live Q&A, Ragas and DeepEval profiles remain denied. Current scoring/proposal services reject live
profiles; merely registering a callback does not make an approved execution envelope. The existing
Cloudflare judge has durable HTTP-attempt/time limits, but no explicit output-token limit in its
request. Provider-specific token enforcement, exact input approval and profile admission remain
work before any live validation. The false-refusal run cannot supply missing ANSWER captures.

The owner requires external Edge, without Computer Use. An attempted terminal launch of Edge was
rejected by automatic policy; no alternate launch mechanism was attempted. Browser sign-in and
read-only same-account Workers Free/quota verification remain pending. Do not ask for credentials
in chat or inherit quota/approval from #153/#188.

Current [Cloudflare pricing documentation](https://developers.cloudflare.com/workers-ai/platform/pricing)
states Free includes 10,000 Neurons/day and operations fail after limits are exceeded; Paid charges
overages. Reset is 00:00 UTC (07:00 Asia/Saigon). This documents the product rule, not this account's
plan, current quota, model compatibility or permission to make a request. Before a live approval
request, bind exact data/provider/purpose, HTTP attempts including retries, enforceable tokens/time,
fresh quota and stop conditions to a concrete envelope with USD 0 paid budget. Unknown or Paid plan,
unknown quota/token compatibility, ambiguous transport or exhausted budget must stop dispatch.

No provider call, model download, billing/configuration change, live-profile unlock, merge,
deployment, Langfuse export or Guardrails enforcement was performed in this follow-up.
