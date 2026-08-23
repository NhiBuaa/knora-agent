# Milestone 4 delivery plan

Status: approved for execution, 2026-08-22

Workflow identity: `feature-delivery:m4-tools-human-approval`

Parent: GitHub Issue #74. Tickets: #75, #76, #77, #78 and #79.

This is the durable execution plan for completing Milestone 4 across multiple sessions. The
mutable transition ledger is GitHub Issue #74 plus `m4-workflow-ledger-v1.json`. A future session
must resume at the ledger's `next_valid_transition`; conversation history is not authority.

## Fixed decisions

- `commit_policy: per-slice`; `acceptance_mode: human_required`.
- The feature integration branch is `nhibuaa/m4-tools-human-approval`, pinned from `main` commit
  `6312c4c4230032aa92ca5915803fcfaf564354fa`.
- #75 and #76 are the parallel frontier. #77 is blocked by both, #78 by #77, and #79 by #75–#78.
- One child PR for each Issue #75–#79 targets the integration branch and uses a merge commit. Actual
  PR numbers/URLs are recorded in the ticket ledger only after GitHub allocates them. The final
  parent feature PR targets `main`. Child issues close only after accepted integration and local
  synchronization; #74 closes only after the final merge, post-merge verification and local
  synchronization.
- M4 remote branches are deleted after verified merge. All M4 worktrees and local branches are
  removed only when clean and reachable from `main`. Unrelated worktrees and `stash@{0}` are
  preserved.
- PostgreSQL-backed suites never run concurrently. The local database is reset and migrated between
  full worktree runs and uses `127.0.0.1`, not `localhost`.
- Human approval is required twice per ticket: approve the externally reviewed locked guide, then
  approve the recorded PASSED Evaluation. PR publication, merge, issue closure and cleanup are
  authorized after all governed gates pass.
- Code review uses `final_feature_only` cadence. There is no child/per-Issue code-review gate.
  Historical child reviews remain immutable audit evidence but do not gate any later ticket.
  An Issue is complete after its locked guide passes, the PASSED Evaluation receives explicit human
  approval, reconciliation/integration verification is green, its PR is merged into the integration
  branch, local integration is synchronized, and the Issue is closed. The one Standards+Spec
  `code-review` runs only after #75–#79 are all complete.

## Application contracts

- `knora.tools` owns a static typed registry for `ticket_lookup` and `create_ticket`; there is no
  dynamic plugin framework.
- `canonical-json-v1` and lowercase `sha256:` digests bind normalized intent. `create_ticket` accepts
  only NFC-normalized `title` (1–200) and `description` (1–10,000), rejects leading/trailing
  whitespace and NUL, and never trusts caller digests.
- Application seams are `ReadTool.execute`, `WriteProposalWorkflow.handle`,
  `HumanApprovalAuthorizer`, `ExecutionAuthorizer`, `WorkspaceResourceAuthorizer`,
  `ToolActionStore` and `SupportToolGateway`.
- Write commands are `ProposeWriteAction`, `ApproveProposal`, `RejectProposal`,
  `ExecuteApprovedProposal` and `ReconcileExecution`.
- `ExternalResourceReference` is the single `m4r1.<payload>.<HMAC-SHA256>` representation backed by
  a trusted reference store. It carries no raw provider ID, verifies active/retiring key version,
  MAC, expiry and exact claims before resource authorization, and rejects unknown/revoked keys.
  Proposal, approval and execution actors are derived from trusted application context, never
  request-body claims.
- `CompatibilityCheckerV1` requires exact identity/version/digest equality for capability, binding
  and every policy-provenance entry. It forbids `latest`; current execution-authority denial is a
  temporary non-stale denial, while compatibility mismatch creates a stale/non-executable
  projection.
- PostgreSQL owns proposal, decision, execution lease/generation, observations and append-only audit.
  A Python standard-library SQLite reference provider owns independent external state and
  idempotency. In-memory fakes are unit-test adapters only.
- `SupportToolGateway` exposes typed lookup/create/outcome-observation operations. The SQLite adapter
  atomically binds logical execution ID to fingerprint and terminal outcome, replays same-key/same-
  fingerprint outcomes, rejects conflicts, survives Knora restart and provides deterministic
  before-receive, after-commit-before-ack, definitive-failure and observation-unavailable fault
  seams.
- Execution acquisition durably captures an authorized opaque binding snapshot. Reconciliation uses
  a distinct observation-only resolver so an already-started execution can observe/finalize provider
  truth after token expiry or key revocation, while every provider retry still fails closed unless
  full current side-effect authorization and exact compatibility pass.
- PostgreSQL database time owns lease staleness. Typed acquire/takeover/observe/finalize CAS results
  fence stale generations and owners. The immutable request fingerprint covers the complete provider
  scope, target/resource binding and normalized parameters and is reused with the same logical ID.
- Provider terminal failure uses the closed `target_not_found|validation_rejected|policy_rejected`
  enum; unknown responses are contract-invalid or observation-unavailable, never definitive.
- HTTP surfaces are ticket lookup, proposal create/read, approve/reject, execute and reconcile under
  `/v1/workspaces/{workspace_id}`. Request schemas forbid actor/authority/digest/provider/logical-ID
  overrides. Authentication/authorization errors map to 401/403; invalid input to 400/422; missing
  resources to 404; stale, expired and conflict outcomes to 409; definitive provider failure to 502.
  Indeterminate and provider-not-found reconciliation return 202 non-terminal projections.
- Public errors use the closed M4 mapping in the design. In particular read-provider scope denial,
  not-found, unavailability and contract-invalid map respectively to
  `403/TOOL_RESOURCE_ACCESS_DENIED`, `404/TOOL_TICKET_NOT_FOUND`,
  `502/TOOL_PROVIDER_UNAVAILABLE` and `502/TOOL_PROVIDER_CONTRACT_INVALID`; proposal
  already-decided/stale/expired use their exact 409 codes and invalid reject reason is
  `422/TOOL_REQUEST_INVALID`.
- The read 502 matrix never applies to ambiguous writes. Execute timeout/ack loss/unavailable or
  unknown/malformed response with possible receipt is `ExecutionIndeterminate` 202; reconcile
  observation-unavailable/timeout/unknown is `ReconciliationIndeterminate` 202; not-found is a
  distinct 202 projection. Only a found closed provider terminal failure finalizes failed/502.

## Governed execution sequence

### 1. Governance reconciliation and cadence

Skills: `feature-delivery`.

1. Commit the approved Current World Model, Architecture Standard, ADR 0015, M4 design, initialization
   evidence, this plan and ledger on the integration branch; push the branch.
2. Verify the content formerly held dirty on canonical `main` is present on integration by digest,
   then restore `main` to a clean pinned checkout without touching unrelated state.
3. Reconcile #75/#76 worktrees onto the governance head and rerun required baseline checks.
4. Run the deterministic cadence planner with risk `high`, change kinds `authorization`, `security`,
   `concurrency`, `schema`, `public-api`, `logic`, ticket IDs `#75`–`#79`, all ticket risks `high`,
   and `human_required`. Persist the plan and record it in #74.
5. Obtain exact spec/design external review. High cadence requires 11 external reviews total: one
   spec/design review, five ticket reviews and five guide reviews. Missing external-review authority
   blocks delivery and is never silently downgraded.

### 2. Ticket lifecycle template

Skills: `manual-acceptance -> test-craft`, `implement -> tdd`, and `feature-delivery`; use
`resolving-merge-conflicts` only for a real in-progress conflict. `code-review` is deliberately
absent from this per-ticket lifecycle and is reserved for the final feature fixed point.

For each current-frontier ticket:

1. Externally review the exact ticket contract.
2. Prepare Test Cases and a manual guide; externally review the guide; revise if necessary; obtain
   explicit human guide approval and lock the revision before implementation.
3. Implement only the approved slice through public seams, using TDD where behavior is testable.
4. Run focused tests, then full pytest, Ruff, Compose config and Alembic against a reset database.
5. Commit, push and open a draft child PR into the integration branch.
6. Execute the exact locked guide against the PR subject SHA, append the Evaluation, and obtain
   explicit human approval of a PASSED result.
7. Reconcile with the latest integration head, resolve conflicts without changing approved seams,
   rerun affected tests/acceptance, merge with a merge commit, fast-forward the local integration
   worktree, verify, close the issue, and record/remove the clean worktree and branches.

Any code change after an accepted Evaluation invalidates every affected Test Case and requires an
append-only rerun before merge. Green automated tests alone do not replace the locked manual guide or
the explicit human approval required by `acceptance_mode: human_required`.

`design_required` returns to Design and creates a new guide revision. At most two design revisions
are allowed per ticket.

### 3. Ticket outcomes

- #75: static read capability; integrity-protected reference mint/verify; Workspace/resource
  authorization before gateway invocation; typed SupportToolGateway lookup; HTTP lookup; fake and
  SQLite reference-provider lookup contract.
- #76: static `create_ticket` descriptor; immutable proposal/caller/actor provenance; exact
  capability/binding/policy/target/parameter/logical-ID binding; human-only atomic approve/reject;
  proposal persistence/audit and proposal HTTP surfaces; no provider write. It consumes only the
  typed `CapabilityResolver.resolve_for_proposal` seam with a fake test adapter and must not import
  #75's concrete registry/provider implementation.
- Merge #75 first. Reconcile #76 with that integration head before its final acceptance and merge.
- #77: approved execution; current execution authorization; exact compatibility checks; atomic
  lease and fencing; immutable complete-intent fingerprint and binding snapshot; provider create;
  closed definitive outcomes and audit.
- #78: reconcile indeterminate and orphaned executing records; provider-outcome observation before
  retry; observation after reference expiry/revocation through the stored binding snapshot; typed
  stale-lease takeover and stale-owner fencing; both crash windows; non-terminal provider not-found;
  current read authority for observation and current write authority for retry.
- #79: integrated release guide and harness covering #75–#78, audit reconstruction, reference-
  provider evidence and full M1–M3 regression. It adds only missing integration glue or deterministic
  release evidence, not new product scope.

### 4. Final delivery and publication

Skills: `feature-delivery`, `code-review`; remediation uses `implement -> tdd` and
`manual-acceptance`.

1. After #75–#79 are accepted, integrated and closed, update the roadmap/release ledger on the
   integration branch.
2. Pin the merge-base fixed point and run final Standards+Spec code review. Require `APPROVE` with
   zero Critical and Major findings. Allow at most two review-remediation cycles.
3. Validate the complete cadence envelope. Require `ready`, 11/11 external reviews, five approved
   human Evaluations, correct event ordering and final-review evidence.
4. Mark feature-delivery complete while `main` remains unchanged. Store exact-head review/cadence
   output outside the reviewed Git head and record its immutable reference/digest in #74.
5. Open the final #74 PR from integration to `main` using `Refs #74`, fetch/recheck the pinned base,
   merge with a merge commit, fast-forward local `main`, and rerun full post-merge verification.
6. Close #74 only after post-merge verification. Stop M4 Compose services without deleting volumes,
   remove clean/reachable M4 worktrees and local/remote branches, fetch/prune, and prove every
   registered worktree is clean.

## Verification and completion proof

Every relevant worktree runs:

```powershell
$env:KNORA_DATABASE_URL = "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora"
& D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe -m pytest
& D:\Developer\Projects\knora-agent\.venv\Scripts\ruff.exe check .
docker compose config --quiet
```

Migration verification runs `alembic upgrade head` against a freshly recreated local Knora
database. Completion additionally requires Issues #74–#79 closed, the five recorded child PRs plus
the recorded parent feature PR merged, `main == origin/main`, a clean canonical checkout, no M4
worktrees or branches, final cadence `ready`, final review `APPROVE`, and green post-merge
verification.

## Resume rule

At every session boundary, use `session-continuity` to suspend with the current ledger, exact branch
and worktree heads, guide revisions, Evaluation histories, blockers, completed transitions and
`next_valid_transition`. Resume only after validating that contract against Git, GitHub and this
plan. Never infer progress from conversation memory.

## Durable execution checkpoint — 2026-08-23, final-review-only policy

This is the current resumable checkpoint. It supersedes every earlier statement that required a
child/per-Issue code review. The authoritative mutable state is
[m4-workflow-ledger-v1.json](.agents/review/m4-workflow-ledger-v1.json); conversation history and
historical child-review evidence cannot reintroduce a removed gate.

### Review policy

- Ticket and guide external reviews remain preparation evidence required by the high-risk cadence;
  they are not code reviews and cannot derive acceptance verdicts.
- No `code-review` or `code-check` runs after an individual Issue implementation or acceptance.
- A child PR may merge after its exact locked guide has a human-approved PASSED Evaluation,
  reconciliation/selective invalidation is resolved, and integration verification is green.
- The single code-review gate is the final M4 Standards+Spec fixed point over
  `merge-base(main, integration)..integration-head`, and it runs only after Issues #75–#79 are
  accepted, integrated and closed.
- Any final-review remediation occurs on the integration branch, reruns every affected acceptance
  case, and then re-pins the one final feature fixed point. It does not recreate child reviews.

### Durable progress

- `main` remains clean and unchanged at `6312c4c4230032aa92ca5915803fcfaf564354fa`.
- #75 is accepted, merged through PR #80, integration-verified and closed. Its historical child
  review remains audit evidence only.
- #76 PR #81 remains open on `nhibuaa/issue-76-m4.2`. Historical child review v3 found four Major
  and one Minor gaps; its accepted v3 Evaluation was append-only invalidated. Those findings are
  remediation input, not a continuing code-review gate.
- The user authorized one exceptional #76 remediation cycle. Under the superseding policy its
  remaining sequence is: externally review and human-lock the accepted guide successor; remediate
  with TDD; execute the
  locked guide; obtain explicit human approval of PASSED; reconcile/integration-verify; merge PR
  #81; synchronize integration; close #76 and clean its branch/worktree. There is no child/per-Issue
  code review.
- External guide-v4 review returned `REQUEST_CHANGES` with zero Critical and two Major findings:
  authorization-before-proposal-lookup was not directly observable, and denial/stale/expiry
  projections were not re-observed after PostgreSQL-backed restart for every condition.
- Guide v5 changes only those evidence contracts: TC-03 installs an ordered counting proposal-lookup
  sentinel, and TC-07 requires condition-by-condition before/after-restart projection pairs bound to
  the same durable proposal. It preserves deep policy immutability, digest-bound expiry, the single
  canonical-json-v1 authority, complete PostgreSQL provenance/replacement evidence, the zero-count
  provider-write sentinel and accepted #75 integration boundary. All prior history remains
  append-only and invalidated.
- External guide-v5 review returned `APPROVE` with zero Critical, Major or Minor findings and
  complete AC-01–AC-08 coverage. The sealed response digest is
  `sha256:671c463831bbb27a75a41004109995fa1f0d41febc1574b5eada5d3858362512`.
- The user explicitly approved and locked exact guide digest
  `sha256:d5034d0dbbc9421a9fa9f9e99b123436bb1b7728a4783876ea8bc28caf70a2ee`;
  approval evidence is committed on Issue #76 at
  `88cc7bb5be94d2e441ee212fef39dabb5e20f31d`.

### Exact next transition

- Externally reviewed #76 subject: `5a49abc237445c4998034af8cda484a5e1c02b95`.
- Current PR #81 guide-lock head: `88cc7bb5be94d2e441ee212fef39dabb5e20f31d`.
- Exact guide digest:
  `sha256:d5034d0dbbc9421a9fa9f9e99b123436bb1b7728a4783876ea8bc28caf70a2ee`.
- Canonical external guide-review packet digest:
  `sha256:a3d80b5cfb50d2085f51c5b96f2a19cb3e462d430cc006625de97df5beb84bd1`.
- Review request ID:
  `review-request-sha256:2ff6c0cd9e577ebc8d261bc360fedaf3692af21c343e726c9c667ea6f4f3679f`.
- The guide-v5 packet and response are contract-valid, committed and pushed. External review is
  complete at `https://chatgpt.com/c/6a8a6cad-a048-83ec-84c1-729ab5ab9428`.
- The next transition is bounded Issue #76 remediation through `implement -> tdd`, driven by the
  locked TC-01–TC-08 seams. After focused and governed verification, execute the unchanged guide v5
  against the exact candidate head and append a PASSED candidate Evaluation with human approval
  pending. No child/per-Issue code review runs.

After #76, advance #77, #78 and #79 in graph order using the same guide → implementation → manual
acceptance → integration lifecycle, without per-Issue code review. After #79 closes, run the one
final M4 code review and cadence gate, then publish/merge #74 to `main`, post-merge verify, close
#74 and complete all cleanup invariants.

At every context boundary, `session-continuity` writes a validated Resume Contract containing this
plan/ledger, exact branch heads, guide/Evaluation identities, blockers and one deterministic next
transition.

### Resume checkpoint — 2026-08-23, Issue #76 acceptance pending

- Issue #76 exceptional remediation cycle 3 completed by TDD. Production/test implementation is
  commit `3698689e330cbb2b60d48b5a036fe912c44b0532`; immutable implementation evidence is
  `.agents/review/m4-issue-76-remediation-result-v3.json` on candidate commit
  `56cd3be0f291cd40b46f3cbd9dbc43173094d5b7`.
- Locked guide `m4-76-write-proposal-v5` retained digest
  `sha256:d5034d0dbbc9421a9fa9f9e99b123436bb1b7728a4783876ea8bc28caf70a2ee`.
- Exact run `m4-76-write-proposal-v5-20260823-01` on subject
  `56cd3be0f291cd40b46f3cbd9dbc43173094d5b7` passed TC-01–TC-08 technically: focused
  `134 passed`; full `851 passed, 3 skipped`; Ruff, Compose, diff check and clean Alembic head
  `20260822_0037` passed; installed provider-write sentinels reported zero writes.
- Candidate Evaluation is append-only at
  `.agents/manual-tests/milestone-4/76-write-proposal-v5.evaluations.jsonl` in PR #81 head
  `7a832aaee611cbd8c8834f33d1fcae4852d0bd65`. Its technical result is PASSED and governed verdict
  remains BLOCKED only because `human_approval` is pending.
- Deterministic next transition: receive explicit repository-owner approval for that exact run and
  subject SHA; append the approved PASSED record, commit/push it, then reconcile PR #81 with the
  current integration head. Do not run child/per-Issue code review.
- After approval: integration-verify, merge PR #81 with a merge commit, synchronize integration,
  close #76, clean its worktree/branch, then begin #77 using the persisted lifecycle above.

### Resume checkpoint — 2026-08-23, Issue #76 integrated

- The repository owner approved exact run `m4-76-write-proposal-v5-20260823-01` on subject
  `56cd3be0f291cd40b46f3cbd9dbc43173094d5b7`; the append-only approved record is
  `m4-76-write-proposal-v5-20260823-01-approved` with verdict PASSED.
- Reconciliation merged integration head `fd19e4040a08d86419dde087a87a9dd6787f8175` into #76 at
  `7398784eb7dad82a9b3852c17f905053ed103ab6`. Only governed metadata changed, so all acceptance
  cases were preserved; reconciliation verification passed `134 focused`, `851 passed, 3 skipped`,
  Ruff, Compose and clean Alembic `20260822_0037`.
- PR #81 merged into integration as `d7742d1d266807b2f487ae1d7917271c1556114a`. Post-merge
  integration verification repeated the same green totals and gates.
- Deterministic next transition: commit/push integration evidence, close Issue #76, verify the
  issue branch is reachable and its worktree clean, remove the Issue #76 worktree/local/remote
  branch, then initialize Issue #77 from the new integration head. No code review runs here.

### Resume checkpoint — 2026-08-23, Issue #77 frontier

- Issue #76 is closed. Its accepted PR head is reachable from integration, and its clean worktree,
  local branch and remote branch were removed; `main` remains clean at `6312c4c`.
- Native blocker inspection confirms #75 and #76 are closed, so open/unassigned Issue #77 is the
  current frontier. #78 and #79 remain blocked.
- Deterministic next transition: externally review the exact Issue #77 contract, then use
  `manual-acceptance -> test-craft` to prepare and externally review its guide. Obtain explicit
  human guide approval before any #77 implementation. Final M4 code review remains forbidden.

### Resume checkpoint — 2026-08-23, Issue #77 exceptional contract revision 4

- External ticket reviews v1-v3 returned `REQUEST_CHANGES`. The repository owner explicitly
  authorized exceptional contract revision 4 to close the remaining authority-to-permit
  linearization and provider-deadline time-authority findings.
- Revision 4 is `.agents/review/m4-issue-77-revision-v6.md`, published verbatim to Issue #77 and
  committed at `3db5edac91809fb6a6ac803a54b53a66e837dadd`. Its digest is
  `sha256:4124dd29385a1ff4469c89303e1b71bee8a75c13b0ac928d41841f1e4360ec9b`.
- `codebase-design` Design It Twice selected one deep `ExecuteApprovedProposal` Module with a
  Workspace-scoped PostgreSQL authority epoch and a PostgreSQL receipt guard held through the short
  deterministic SQLite commit. This preserves the existing application Interface and #78 ownership
  of takeover/reconciliation.
- Canonical external-review packet v4 is
  `.agents/review/m4-issue-77-ticket-review-packet-v4.json`, with packet digest
  `sha256:e08d370648eb00fc29a4f5aa69586b03ab12a8ff36420f32d36fef45402980ef`
  and request ID
  `review-request-sha256:b81da32fe6b2aead00a4214d7a9e68dccf5276b24e4c51171e5b50ba7ab3cd44`.
- Deterministic next transition: send this exact packet through a fresh independent ChatGPT High
  external-review session. Require `APPROVE` with zero Critical and Major findings before invoking
  `manual-acceptance -> test-craft` to prepare the Issue #77 guide. Do not implement and do not run
  the final M4 code review.

### Resume checkpoint — 2026-08-23, Issue #77 contract v4 blocked

- External review v4 ran in isolated ChatGPT High session
  `6a8a92f5-34a8-83ec-b5ef-afc701d05456` against exact packet digest
  `sha256:e08d370648eb00fc29a4f5aa69586b03ab12a8ff36420f32d36fef45402980ef`.
  The validated response digest is
  `sha256:8b0732b7202a45aeea3040af890b1e82bcb637cacd71634174c9fc77b49559aa`.
- Verdict is `BLOCK` with one Critical and six Major findings. The Critical finding proves the
  stated PostgreSQL guard-session-loss `proof no write` cannot be guaranteed across an independent
  SQLite commit: PostgreSQL locks can disappear before SQLite durability and the SQLite transaction
  can still commit.
- Major findings require: epoch-linearization races for every mutation class; post-lock expiry
  oracles at permit issuance and finalization; removal of generation-2/takeover fixtures from #77;
  explicit pre-acquisition denial/no-execution tests; and exact complete audit reconstruction.
- Exceptional contract revision 4 was the last authorized revision. Therefore no guide may be
  prepared and no implementation may begin. Final M4 code review remains forbidden.
- Deterministic next transition: obtain explicit repository-owner direction. A further contract
  revision requires new exceptional authority and must address every v4 finding before another
  external review. The alternative is to change Issue #77/#78 scope or stop M4; neither may be
  inferred by the workflow.
- Validated Resume Contract:
  `C:/Users/Nhi/AppData/Local/Temp/agent-handoffs/m4-tools-human-approval-issue-77-contract-v4-block-v1.json`
  with digest
  `sha256:345a1af6c23bc0896b5fed239fecce5c8d0cf975fb1ce804d4acd7247bb4680f`.

### Resume checkpoint — 2026-08-23, Issue #77 contract v5 review-send gate

- The repository owner explicitly authorized exceptional ticket-contract revision 5 to address all
  one Critical and six Major findings from external review v4. Final M4 code review remains
  forbidden until #75–#79 complete.
- Revision 5 is `.agents/review/m4-issue-77-revision-v7.md`, published verbatim to Issue #77 and
  committed at `fd23a742888713589dbebf8906328fda683a47de`. Its digest is
  `sha256:5bf7370820d903b62c38912d254caa1132144f7692b797eaf691079f3dc25562`.
- `codebase-design` Design It Twice replaced the unimplementable cross-store live receipt guard
  with one durable PostgreSQL `DispatchAdmission`. Admission commit is the logical start of the
  provider write; post-admission session/crash uncertainty is receipt-possible, and the independent
  SQLite ledger remains the at-most-one-effect authority.
- Revision 5 also fixes the full mutation-adapter epoch race matrix, post-lock proposal/reference/
  lease expiry oracles, observation and finalization expiry fencing, pre-acquisition zero-state/
  zero-call coverage, exact audit reconstruction, byte-identical admission recovery across key
  rotation, and the no-admission versus existing-admission #78 recovery branches. #77 still contains
  no takeover, generation 2+ or reconciliation implementation.
- Canonical external ticket-review packet v5 is
  `.agents/review/m4-issue-77-ticket-review-packet-v5.json`, with packet digest
  `sha256:752b28ffa44817432f5fc6402313a44615396ff034bd0df1ceb1aa2737649b33`
  and request ID
  `review-request-sha256:6f418e735acffd7de2e3c4022e4e0c015a2ba875c092e69c6df86774e236c581`.
- Deterministic next transition: obtain action-time human confirmation, then send this exact packet
  through a fresh independent ChatGPT High external-review session. Require `APPROVE` with zero
  Critical, Major or Minor findings before invoking `manual-acceptance -> test-craft`. Do not create
  a guide, implement #77 or run final M4 code review before that gate.

### Resume checkpoint — 2026-08-23, Issue #77 contract v5 request changes

- The repository owner confirmed packet v5 transmission and preauthorized future canonical M4
  external-review packet sends without a separate action-time confirmation. This transport policy
  does not waive human guide approval, human manual-acceptance approval or authority for exceptional
  contract/design revisions.
- External review v5 ran in fresh independent ChatGPT High session
  `6a8aa12d-780c-83ec-a310-ffb859ff5069` against exact review subject
  `b05123caa97debfac969e44e7d0169eec0987bc8`, packet digest
  `sha256:752b28ffa44817432f5fc6402313a44615396ff034bd0df1ceb1aa2737649b33`
  and request ID
  `review-request-sha256:6f418e735acffd7de2e3c4022e4e0c015a2ba875c092e69c6df86774e236c581`.
- The contract-valid response digest is
  `sha256:42f508596aaa1e7ddae12cc571153a57cdd0d1248a2b1502125f938c49e097cc`.
  Verdict is `REQUEST_CHANGES` with zero Critical, eight Major and zero Minor findings.
- The eight Major classes are acquisition atomicity/loser zero-call evidence, post-acquisition
  `m4r1` reverification, exact durable-admission field witness, admission-first non-cancellation,
  reachable provider fingerprint-conflict testing, #77/#78 acceptance-scope separation,
  provider-ledger not-found non-terminality and read/observation-to-write non-escalation.
- No guide or implementation may begin. Exceptional ticket-contract revision 6 is not authorized.
  Deterministic next transition is repository-owner direction on whether to authorize revision 6;
  if authorized, revise the contract to close all eight findings, publish it verbatim, prepare and
  automatically send the next canonical packet, and require external `APPROVE` before guide work.
  Final M4 code review remains forbidden until #75–#79 complete.

### Resume checkpoint — 2026-08-23, Issue #77 contract v6 review-ready

- The repository owner authorized exceptional ticket-contract revision 6 to close all eight Major
  v5 findings and automatic external review before guide creation.
- `codebase-design` Design It Twice compared a minimal Interface, provider-focused and common-caller/
  #78-boundary design. The selected hybrid keeps one deep `WriteProposalWorkflow.handle` Interface,
  persists complete acquisition/admission witnesses and exact envelope bytes, uses a private
  provider contract harness for the valid fingerprint-conflict path, and exposes only a read-only
  `NoAdmission | AdmissionOutstanding` downstream seed to #78.
- Revision 6 is `.agents/review/m4-issue-77-revision-v8.md`, published verbatim to Issue #77 and
  committed at `20f3a3d070529f2fe44add794d3341059a377394`. Contract digest is
  `sha256:bedf225e465f6897e5354500a7956f33e33793ea31b9cd6df474afa6f191ddaf`.
- Canonical ticket-review packet v6 is
  `.agents/review/m4-issue-77-ticket-review-packet-v6.json`, with packet digest
  `sha256:fc292332c86d0ea2426a0ada78afb990584a63643be5c96c9ab657a45b503ded`
  and request ID
  `review-request-sha256:1dfb0672037e10b08f8cbe40f08cd852f5c432fa797365f9fc8b7fe373fade8b`.
- Deterministic next transition: automatically send the exact packet to a fresh independent ChatGPT
  High session under the recorded M4 transport authorization. Require external `APPROVE` with zero
  findings before `manual-acceptance -> test-craft`. Do not create a guide, implement #77 or run the
  final M4 code review before that gate.

### Resume checkpoint — 2026-08-23, Issue #77 contract v6 request changes

- External review v6 ran automatically under the recorded M4 transport authorization in fresh
  independent ChatGPT High session `6a8aabea-c860-83ec-bec2-e6c7c3324be1` against exact subject
  `9247621531a01742523f55942a04b329b1f928fe`, packet digest
  `sha256:fc292332c86d0ea2426a0ada78afb990584a63643be5c96c9ab657a45b503ded`
  and request ID
  `review-request-sha256:1dfb0672037e10b08f8cbe40f08cd852f5c432fa797365f9fc8b7fe373fade8b`.
- The contract-valid response digest is
  `sha256:4b276bd674f80c70302bcb21314e487292316cf1ccabfdaad4eb0730e9dfbb6a`.
  Verdict is `REQUEST_CHANGES` with zero Critical, three Major and zero Minor findings.
- The three remaining gaps are direct oracles/evidence, not application-abstraction changes:
  deterministic readback after ambiguous admission commit/ack; complete state fencing for delayed
  success and each closed failure after lease expiry; and atomic durable SQLite evidence for
  `target_not_found`, `validation_rejected` and `policy_rejected`, each retaining exact logical
  identity/fingerprint across provider restart with no target effect.
- No guide or implementation may begin. Exceptional ticket-contract revision 7 is not authorized.
  Deterministic next transition is repository-owner direction on revision 7. If authorized, change
  only these three oracle/evidence clauses, publish Issue #77 verbatim, prepare and automatically
  send canonical packet v7, and require external `APPROVE` with zero findings before guide work.
  Final M4 code review remains forbidden until #75–#79 complete.
- Validated Resume Contract:
  `C:/Users/Nhi/AppData/Local/Temp/agent-handoffs/m4-tools-human-approval-issue-77-contract-v6-review-block-v1.json`
  with digest
  `sha256:9968f899144ffc8b426d3328d73c7e7cd5fdcd07ced280a88d93890f57c4764e`.

### Resume checkpoint — 2026-08-23, Issue #77 exceptional contract revision 7

- The repository owner authorized exceptional ticket-contract revision 7 to close all three Major
  findings from external review v6 and retained automatic external-review packet transmission.
- The revision preserves the sole deep `WriteProposalWorkflow.handle` Interface and all Issue #77/
  #78 ownership. It adds only deterministic oracle/evidence detail: two-branch admission commit/ack
  readback, complete post-expiry zero-write observation/finalization snapshots, and separate atomic/
  restart evidence for `target_not_found`, `validation_rejected` and `policy_rejected`.
- Local contract digest is
  `sha256:f0c5cf68b4cfec0889d7c5127817293c12bb61b0f53781dcf8ef4d7b219ee922`.
  Next transition is verbatim publication to Issue #77, then canonical packet v7 generation and
  automatic independent review. No guide, implementation or final M4 code review may begin before
  external `APPROVE` with zero findings.
- Revision 7 was committed at `bab205b02d3961c221e0a262250c9989a2d219a4` and read back
  verbatim from Issue #77. Canonical packet v7 is a contract-valid delta over packet v6 at
  `.agents/review/m4-issue-77-ticket-review-packet-v7.json`, with packet digest
  `sha256:748458cb2c501781f3538ee2661938d176e59d0c6f9d710ffe533e99d798b05b`
  and request ID
  `review-request-sha256:a7e46ff73246f0690b0e6e4ef8e353187798c482f275d7523dc56b140757c333`.
  Deterministic next transition is automatic external review in a fresh independent session.

### Resume checkpoint — 2026-08-23, Issue #77 contract v7 request changes

- External review v7 ran in fresh independent ChatGPT High session
  `6a8ab38d-bf38-83ec-805b-917743be619f` against exact subject
  `caff4a7e94b7373f03e18c1cc001a09c7f2464f2`. The response is contract-valid with digest
  `sha256:6ee3612ed850828441a6ceaef3eeb80a2d38a45a129710884bf12bb4a13c0918`.
- Verdict is `REQUEST_CHANGES` with zero Critical, four Major and zero Minor findings. The reviewer
  explicitly confirms revision 7 closed all three v6 findings and preserved the deep Interface,
  generation-1 scope, static registry and #78 ownership.
- Four new direct-oracle gaps remain: branch-specific provider/store state for all three
  post-admission fault windows; independent proof of server-owned fingerprint/logical-ID provenance;
  durable approved-versus-stale proposal state after temporary authority denial versus material
  incompatibility; and explicit allowlist/forbidden-field checks for every public result projection.
- No guide or implementation may begin. Exceptional ticket-contract revision 8 is not authorized.
  Deterministic next transition is repository-owner direction. Final M4 code review remains
  forbidden until #75–#79 complete.
- Validated Resume Contract:
  `C:/Users/Nhi/AppData/Local/Temp/agent-handoffs/m4-tools-human-approval-issue-77-contract-v7-review-block-v1.json`
  with digest
  `sha256:fa32a1b31b84c63225af0b8ec42b930630c47881e65d1178901b1a24d8bec643`.

### Resume checkpoint — 2026-08-23, Issue #77 exceptional contract revision 8

- The repository owner authorized exceptional ticket-contract revision 8 with authorization digest
  `sha256:40fd2a98d12b3352f99c576ec7212f55d6546bb6f27729225b0921eac6bc1d37` and retained automatic
  external-review packet transmission.
- The revision preserves the sole deep `WriteProposalWorkflow.handle` Interface, generation-1-only
  execution boundary, static typed registry and Issue #78 ownership. It adds only four direct oracle
  families required by external review v7: branch-specific post-admission provider/Knora state;
  server-owned logical-ID/fingerprint provenance and caller non-influence; temporary-authority
  approved preservation versus material-incompatibility stale invalidation; and exact public
  projection allowlists/forbidden-field assertions for every result variant.
- Local contract digest is
  `sha256:10989a737bb502116984ba4ef628341eb395e4a2759056bf20b9a04e6d3d7707`.
  Next transition is verbatim publication to Issue #77, then canonical packet v8 generation and
  automatic independent review. No guide, implementation or final M4 code review may begin before
  external `APPROVE` with zero findings.
