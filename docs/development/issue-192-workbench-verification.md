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

Hosted CI for follow-up `2cd9a77ac300adbf7643a5d5525ef8e96f533350`:
[run 39012903508](https://github.com/NhiBuaa/knora-agent/actions/runs/39012903508) Database job
succeeded. Downloaded `database-reports` artifact 12093378579 records 382 tests, zero failures,
errors or skips; its selection and JUnit reports explicitly include all three new contention
cases as passed. This verifies the tests run on hosted PostgreSQL rather than being skipped.
All six jobs, including CI required, subsequently succeeded for this exact PR head. The
`ci-subject` artifact binds the PR head to its tested merge checkout; these are distinct refs.

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
The eight committed M3 vector/hybrid reports were also inspected: their observations retain
metrics and source bindings, without saved public answers or exact generation evidence required
by the current capture mapper. They cannot be imported directly as an alternative scorer input.

The [pinned primary-source token-bound research](../research/2026-10-17-cloudflare-gpt-oss-token-bound.md)
finds model schema support for `max_tokens` and Workers binding types for both token parameters,
but no inspected model/endpoint-specific guarantee that the ceiling covers all billed reasoning
and output. This remains an evidence gap, not proof that the parameters are ignored. No live
compatibility probe or admission change follows from type declarations.

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

## Subsequent read-only access and offline token-request follow-up

The owner subsequently chose the integrated browser and signed in there, superseding the earlier
external-Edge-only instruction. At 2026-10-17 11:13 UTC (18:13 Asia/Saigon), the same authenticated
account's Workers plans page showed **Free / Current plan / $0** and Workers AI daily usage showed
**78.11/10,000 neurons**. Arithmetic remaining was **9,921.89**, not a quota reservation. The daily
reset label was 00:00 UTC / 07:00 Asia/Saigon. Account identifiers are omitted from the public
[read-only checkpoint](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6233226216).
Runtime account binding and quota freshness still need validation before any future dispatch.

The DeepEval adapter/CLI now require an explicit positive integer `max_output_tokens`, send it as
`max_tokens` on every judge request and retain `requested_max_output_tokens` in supplements.
Missing/invalid caps fail before dispatch; there is no implicit default. The saved input digest,
gold, thresholds and historical runs remain unchanged. This supersedes the earlier missing-field
code observation only: MockTransport proves request construction, not the provider's treatment of
reasoning or billed output. Live Workbench admission remains denied, and no provider was called.

Verification: baseline 40 focused tests passed; new request/configuration/preflight assertions
failed before implementation, and the CLI wiring test failed before its required argument was
connected. After the change, 54 scorer/Workbench scoring tests pass. The wider existing evaluation
partition (`evals/test` plus `backend/test/evaluation`, `--ci-suite backend`) passes **618 tests**,
with 30 Windows-partition cases deselected and no skips, in 46.89s. Independent review found no
actionable findings; the reviewer did not rerun tests. Ruff format/check/lint, shared formatting,
OpenAPI exporter check, Compose configuration and diff check pass. Compose retains the missing
local MinIO credential warnings. No application/database runtime started for this follow-up; the
earlier full-suite/PostgreSQL evidence retains its original commit scope. Exact new-commit CI is separate.

## Approved local L1 — one owner, sequential capability phases

The owner approved the local envelope in
[comment6233445354](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6233445354)
in chat, then explicitly approved the ownership correction from
[comment6233631658](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6233631658):
one real Keycloak owner, changing reader → author → reviewer capabilities sequentially.
This verifies phases of the same owner, not independent-person review. Each phase ended with
logout/session revocation and at least 65 seconds before signing in again; access-token TTL is
60 seconds. Write and approve were never granted simultaneously. Agent accept/reject/freeze
remains prohibited; human review is pending.

Runtime began at **2026-10-17 19:03:12 Asia/Saigon**. The original hard stop is **20:33:12**;
startup corrections and restart did not reset that deadline. Only the new
`knora-wb192-l1` PostgreSQL/Keycloak containers and dedicated storage are used, with loopback
ports 15492/18192/18092/13092. Existing images/dependencies only; no old PostgreSQL cluster was
started, recovered, copied or queried. Application providers are deterministic-local with no
Cloudflare/OpenAI/Gemini credentials and no evaluation live profiles or worker dispatch.

| Local L1 identity/artifact | Value |
| --- | --- |
| Issuer | `http://127.0.0.1:18192/realms/knora-wb192-l1` |
| Owner subject | `95932186-5415-4307-9db4-e5394fb99b18` |
| Workspace | `73caf42b-d350-4f19-a9b2-9707a6eaa9d4` |
| New dataset | `a1734dd6-545e-46e7-836b-38ff8b73b069`, `L1 local UI walkthrough — drafts only` |
| Dataset state before human handoff | DRAFT, revision 5; two UNREVIEWED cases; no reviews/reference |
| ANSWER draft | `e066fa4c-4928-4135-b4f7-41b0af69bc06`, watering seedlings before 9 AM, one original-PDF page 1 anchor |
| REFUSAL draft | `1fe9c064-deed-482c-891d-415296af9835`, absent private password, explicit one-document scope note |

Three synthetic PDFs were selected together and uploaded through the actual Builder UI.
`community-garden-guide.pdf` and `fictional-garden-notes.pdf` became READY with separate retained
extraction snapshots. `text-empty-fixture.pdf` became FAILED / `PDF_TEXT_INSUFFICIENT`, retained
its original, and has no extraction snapshot. Both ready extracted pages were inspected in UI.
No retry, Ragas proposal, scorer, runtime binding or Q&A run was submitted.

Reader UI exposed no creation/review controls. Author created the dataset and exactly two manual
drafts, with no approve/freeze controls. After a fresh reviewer login, the session endpoint
reported the same subject and exactly `operator:read, documents:read, evaluations:approve`;
the Builder exposed review controls and omitted upload/edit/create controls. Accept/reject stay
disabled until a review note is supplied. The agent left that note empty and handed off the page.
Read-only assertions against this new database confirmed one dataset, three sources, two cases,
two extraction snapshots, zero reviews/gold versions/proposal batches/runs/preflights.

Temporary setup corrections were confined to this L1 runtime: Docker bridge networking with
explicit loopback publishing; an admin-only managed multivalued capability attribute on the new
realm; preserving synthetic profile fields during capability updates; frontend launch cwd set to
its project directory so Tailwind scans the correct sources. No maintained product file changed.

**Original-PDF visual gate is still open.** Original endpoints returned HTTP 200, but the integrated
browser showed a blank PDF both in the iframe and a separate original tab. Correcting Tailwind
restored the iframe's intended height, not PDF rendering. No cause for the remaining blank viewer
has been established. The retained garden original rendered correctly with existing local
Poppler; its preview was supplied for human comparison. This does not establish that embedded
original review works or that the human has accepted the cases/product.

Local evidence is retained under `%TEMP%/knora-wb192-l1/evidence`, including upload/failure/source
screenshots, author drafts, reviewer controls/session, phase transition times, database assertions
and the rendered original. Credentials and runtime environment files stay local and unpublished.
The owned watchdog stops application process trees and these two containers at the original
deadline or explicit completion, retaining storage. Runtime remains at human handoff until then.

Source HEAD/PR202 remains `ebb934279136e47b5d598c50323f7409c393d002` before this ledger update.
[Exact-head CI 39028447642](https://github.com/NhiBuaa/knora-agent/actions/runs/39028447642)
has six successful jobs including CI required. No repeated implementation test run is claimed.
Project 5 read-back: #158/#192/#193/#194/#195/#198 In Progress; #196/#197 Blocked. No issue is Done.
Provider calls/retries **0**, paid cost **USD 0**. The Cloudflare probe and all live validation
remain unapproved; historical gold/thresholds/runs, billing/config, export/enforcement and shared
#153/#188 source/migrations are unchanged. L1 narrows upload/extraction/identity evidence gaps;
it does not complete quality, A3/R3, human acceptance or combined migration integration.

### L1 closeout — 17 October 2026, 20:35 Asia/Saigon

The automatic follow-up at 20:34:35 found the original 20:33:12 deadline had elapsed.
Exec watchdog handle 77075 was missing; recorded API/frontend PIDs 22356/40952 and listeners
18092/13092 were absent. Both owned Docker containers were still running with their explicit
loopback ports. Thus the promised watchdog cleanup was **not verified and did not fully occur**.
The earlier ready state file was stale; it is not evidence of a live watchdog or available UI.
The reason for the missing handle/processes is unestablished.

After checking exact container IDs and Compose project labels, the agent explicitly stopped only
these two containers. Docker records PostgreSQL exit at **20:35:00.329** and Keycloak exit at
**20:35:00.637**: approximately 108 seconds after the approved deadline. A fresh check confirms no
listeners on any of the four L1 ports and both application PIDs absent. Storage/evidence are
retained; no services were restarted and no final database query was performed after expiry.
The pre-handoff DB assertions above retain their original scope, not proof of subsequent human
actions. No human review result or permission to extend/reopen L1 has been supplied.

This supersedes the earlier statement that the runtime remained available for handoff until the
deadline. L1 is now stopped with human review and original viewer evidence still incomplete.
Another runtime window requires explicit approval and reliable cleanup verification first;
the original 90-minute authorization is exhausted. Provider calls/retries remain 0 and paid cost
USD 0. Cleanup observations and exact exited IDs are saved locally in `evidence/closeout.json`.

The documentation checkpoint commit `ae5a44be9c9c56255fb088089fb803f772e21d54` has
[CI 39032513816](https://github.com/NhiBuaa/knora-agent/actions/runs/39032513816): all six jobs,
including CI required, SUCCESS. The closeout ledger change has its own later commit/CI scope.
Project status and the outstanding quality/live/integration gates above are unchanged.

## Approved local L2 — 17 October 2026, runtime and browser access

The owner resumed the precise [L2 proposal](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234552279)
with “tiếp tục” in chat. This approves one local window of at most 30 minutes, using only the
retained L1 storage, identity, Workspace, dataset, three synthetic PDFs and two drafts. It does
not approve the Cloudflare probe or any live profile. No new upload, case, dataset, proposal,
migration, historical-cluster access or model dispatch is permitted by this window.

The independent cleanup admission gate passed before startup: a one-shot Windows scheduled task
ran a harmless marker at **20:51:26 Asia/Saigon**, with task result 0. It used the current
interactive user, Limited run level, no stored password, no elevation and no recurring trigger.
The smoke task was removed after verification. The actual one-shot cleanup was then registered
and read back, targeting the exact two retained container IDs with Compose project/service checks
and application processes with PID, creation-time and command-line checks. Its action uses the
installed Python without a visible window; an additional local watchdog is secondary protection.
The scheduled cleanup and target manifest are independent of the Codex exec session.

The fixed hard deadline is **21:22:47 Asia/Saigon**, set before startup; cleanup begins at
**21:21:47**. The first container-start invocation was at **20:53:08**, and application readiness
was observed at **20:53:45**. Retries do not reset the deadline. Four ports were unoccupied and
both containers exited before startup; current application listeners use the same loopback
ports. Existing containers were started without recreation or migration replay. Deterministic
provider configuration and absence of model credentials were asserted before API startup.

Read-only assertions against the retained L1 database still find exactly one DRAFT dataset at
revision 5, three sources, two unreviewed cases and two extraction snapshots. Reviews, gold
versions, proposal batches, runs and preflights remain zero. These are fresh pre-handoff facts,
not proof of a later human review. No review note, accept/reject or freeze was submitted by the
agent. An authenticated read of the retained Keycloak owner configuration confirmed the same
subject and exactly `operator:read, documents:read, evaluations:approve`, without changing any
realm/user setting. Fresh L2 browser OIDC/session verification has not yet been completed.

The integrated browser's tab inventory shows the previous Workbench connection-error page.
Attempting to acquire that tab was rejected by the browser URL security policy. The agent stopped
that browser action and asked the owner to reload the normal HTTP application route in the
integrated browser. No external browser, alternate file-serving route, browser settings change
or policy bypass was attempted. L2 original-PDF transport/rendering diagnosis and human handoff
therefore remain pending browser access; the earlier L1 original-rendering evidence keeps its
original scope. Cleanup is registered, but successful L2 shutdown is not claimed before closeout.

The [L2 start checkpoint](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234698872)
records source HEAD `e5bc5de655621f5bda16516a12417d2d431e2dc1`, its six successful CI jobs and
the exact local envelope. Project 5 read-back returns #192 to In Progress for this authorized
work; #196/#197 remain Blocked. Provider calls/retries remain **0**, paid cost **USD 0**.
No gold/threshold/history mutation, profile unlock, billing change, export/enforcement,
merge/deploy or quality acceptance follows from this local startup.

### Subsequent finite coordination with #153

- [Q10 round1 finite ACK](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234741170)
  covers only patch LF SHA256 `ef318832867fed6c64e9891fc25fae4bdffba90d43aad9791276d73b2eba82d0`
  on the eight exact manifest base snapshots. All 16 base/candidate hashes and current base files
  were checked. This is a working-snapshot delta with S2 prerequisites, not a standalone patch
  on commit `4e0134d` or an ACK of those omitted prerequisites. Parent-link trigger, transactional
  replay/rollback and concurrent parent-update/child-insert runtime evidence remain open; no S2
  database was started by this review. Combined migration integration with Workbench is separate.
- [PDF runner finite review](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234759447)
  withholds ACK for LF SHA256 `a3746638f86bdf2b78c6e10fdf228c1467ba989238f3ea87a3bedf10a6204d39`.
  An isolated pure-function reproduction shows that reordering a saved native rank-9 row ahead
  of ranks 1–8 changes reported Top8 coverage from false to true, because the comparison slices
  array order without validating/canonicalizing saved ranks. This is a malformed-input finding,
  not a claim that a real native capture was corrupt. A focused validation fix and renewed exact
  diff are requested. No shared file or frozen artifact was edited by either peer review.
- The subsequent [round1 scoped re-review and finite ACK](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234801881)
  covers new full patch LF SHA256 `70befd4684f3fb7e8c9757dfa6381e4da4ab5c50b09c0e0700dc1c27f29a865c`
  on the same two pinned bases. It shares the native-rank validator between capture and saved
  comparison. Independent exact-function assertions confirm reordered rank 9 stays outside Top8,
  remains inside Top200, inputs are unchanged, an empty window is valid, and six invalid rank
  windows fail closed. This addresses the finding above; it does not establish CLI, all-60,
  runtime, provenance, semantic quality or combined integration acceptance. Full/fix-only and
  candidate/base hashes were rechecked before the finite ACK. No shared file was applied here.

### L2 browser handoff and finite review — 17 October 2026, 21:12 Asia/Saigon

After the owner requested reopening in the integrated browser, a new tab on the normal HTTP
Builder route opened successfully. The rejected old connection-error tab was not reused or
bypassed. A normal account logout was followed by a fresh OIDC authorize/callback using the
retained Keycloak SSO session; no password re-entry is claimed. The session endpoint reported
the same owner subject and exactly `operator:read, documents:read, evaluations:approve`.
The tab was placed at Cases and marked for human handoff. The review note remains empty and
the agent has not accepted, rejected or frozen either case. No human review result has arrived
at this checkpoint; the pre-handoff database assertions above do not describe later actions.

The original garden PDF remains blank gray both in the iframe and a separate normal HTTP tab;
the extracted page is readable. API logs record two original GET responses with status 200.
Console warnings/errors were empty. Browser-visible original response headers/bytes were not
captured, so no end-to-end byte-equivalence claim follows. Source inspection finds an
`application/pdf` backend response and a BFF stream forwarding content type; this does not prove
the actual browser response or establish the cause. No viewer code, browser setting, alternate
file server or security workaround was added. The local original render is comparison evidence
only and leaves the original-viewer acceptance gate open.

Local evidence includes `l2-reviewer-session.txt`, `l2-source-garden.jpg`,
`l2-original-direct.jpg`, `l2-reviewer-handoff.jpg` and `l2-browser-check.json` under the retained
evidence directory. The fixed cleanup trigger remains **21:21:47**, hard deadline **21:22:47**
Asia/Saigon. The independent one-shot task is registered; successful shutdown is still pending
observation. No extension is implied by this handoff.

The [Q11 population-guard finite ACK](https://github.com/NhiBuaa/knora-agent/issues/192#issuecomment-6234899417)
covers LF patch SHA256 `21b56ce7cf01f1d4395c9c7603950a58899ee8911d8342823213c2f59248cbab`
on its three pinned current bases/four candidates. Independent import-path assertions ensured
the TEMP candidates, not current worktree modules, were tested: **154 offline tests passed**,
covering the new guards, S2 contracts, dense processing, generation loading and private population
validation. The exact private repeated-content snapshots and limitations are pinned in that ACK.
No actionable finite source finding remains; no shared patch was applied here. Runtime manifest,
native measurement, Q12/Q13 choices, S2 main/HTTP wiring, full corpus, migrations/concurrency and
combined integration remain outside this ACK.

Source checkpoint `25c6368a64e76d3184ceb0fe639e7fd234d4f7d0` has
[exact-head CI 39038997330](https://github.com/NhiBuaa/knora-agent/actions/runs/39038997330)
SUCCESS. This subsequent documentation update has separate commit/CI scope. Provider calls/retries
remain **0**, paid cost **USD 0**; quality, human acceptance and live approvals remain open.

### L2 final data observation — 17 October 2026, 21:20 Asia/Saigon

At 21:20:07, listeners 18092/13092 and the recorded application/watchdog PIDs were absent;
only the two owned containers remained running. Their reason for stopping is unestablished.
No service was restarted. The independent one-shot cleanup task remained Ready with its original
21:21:47 trigger. This corrects any inference that the browser remained available throughout
handoff. No human review result has been received.

A read-only transaction against the retained database at **21:20:28** confirmed the same dataset
is still DRAFT revision 5 with exactly two cases, empty reviews/proposal batches and no gold
reference. Counts remain three sources, two snapshots, zero gold versions/runs/preflights.
`evidence/l2-final-db.json` records this observation. No later database state is claimed.

### L2 closeout — 17 October 2026, 21:22 Asia/Saigon

The independent scheduled task ran at **21:21:47**, result **0**. Its closeout records cleanup
start 21:21:47.866 and finish **21:21:53.618**, before the fixed 21:22:47 deadline, with no errors
or open L2 ports. Fresh Docker inspection confirms the exact PostgreSQL/Keycloak containers
exited at 21:21:48.227 and 21:21:49.159. Independent checks found no listeners on all four ports
and no recorded application/watchdog process identities. Child PID 16568 had been reused by a
new Python process at 21:19:55 (the former child was Node); that unrelated process was untouched.
Only after these checks was the exact owned
one-shot task removed. Storage and evidence remain retained; no services were restarted.

Thus L2 cleanup succeeded within its authorization, while the earlier application availability
gap and original-viewer/human acceptance gates remain unresolved. No human review/freeze outcome
was received. The final read-only data observation above proves both cases were unreviewed at
21:20:28; no database query was made after shutdown. Calls/retries remain **0**, paid cost
**USD 0**. This closes the local window, not #192/#158 or their quality/live/integration gates.
