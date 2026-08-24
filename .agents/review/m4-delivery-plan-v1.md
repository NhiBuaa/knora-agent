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
- When the only reachable external-review transport is the authenticated in-app browser, the
  stricter browser policy requires one fresh action-time repository-owner confirmation for each
  live upload/message after the exact subject, packet digest and request ID are known. Broad
  workflow continuation does not infer that representational send. A governed non-browser
  `ExternalReviewerGateway` may be used instead only when its authority and evidence are reachable.
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
5. Obtain exact spec/design external review. High cadence has 11 required eligible review slots:
   one spec/design review, five latest-approved ticket-contract reviews and five latest-approved
   guide reviews. Superseded `REQUEST_CHANGES` attempts remain immutable history but do not fill a
   final eligible slot. Rebuild the cadence envelope after every review or acceptance evidence
   change; `blocked` is expected before completion, while final delivery requires `ready`.

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

1. Update the roadmap/release ledger inside Issue #79 before its guide execution and acceptance, so
   the accepted #79 head already contains the final M4 completion projection. Any later roadmap or
   release-ledger change selectively invalidates affected #79 evidence and must be rerun.
2. After #75–#79 are accepted, integrated and closed, fetch remote state and prove local
   `main == origin/main == 6312c4c4230032aa92ca5915803fcfaf564354fa`. Pin one immutable descriptor
   containing `base_commit`, `merge_base_commit`, `head_commit`,
   `merge_base_semantics: true`, a non-empty commit list and exact
   `git diff <base_commit>..<head_commit>` command. Freeze that integration head and run the single
   final Standards+Spec review stage. Require `APPROVE` with zero Critical and Major findings.
   If local or remote `main` moved, reconcile integration, rerun every affected acceptance case and
   repin before review; a stale-base reviewed head may never merge.
   A remediation changes the head, reruns affected acceptance, repins the descriptor and reruns the
   final review; allow at most two remediation/re-review cycles.
3. Validate the complete cadence envelope. Require `ready`, 11/11 external reviews, five approved
   human Evaluations, correct event ordering and final-review evidence.
4. Mark feature-delivery complete while `main` remains unchanged. Store exact-head review/cadence
   output outside the reviewed Git head and record its immutable reference/digest in #74. Any later
   commit invalidates the fixed point and requires a new descriptor and final review.
5. Open the final #74 PR from integration to `main` using `Refs #74`, fetch/recheck the pinned base,
   merge with a merge commit, fast-forward local `main`, and rerun full post-merge verification.
6. Close #74 only after post-merge verification. Stop M4 Compose services without deleting volumes,
   remove clean/reachable M4 worktrees and local/remote branches, fetch/prune, and prove every
   registered worktree is clean. Preserve unrelated worktrees, branches and `stash@{0}`; if an
   unrelated worktree becomes dirty, report and stop rather than mutating it.

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
- Revision 8 was committed at `478992d3a18ae85832cb3c355c772a8cea08a03c` and read back verbatim
  from Issue #77. Canonical packet v8 is a contract-valid delta over the self-contained packet v6 at
  `.agents/review/m4-issue-77-ticket-review-packet-v8.json`, with packet digest
  `sha256:2468e6f0289fac5ab48ead158781caffae9f3ab4cc2027319439e924d1b1b14d` and request ID
  `review-request-sha256:074a23c1b4ef074988afb0f51c4f0ba2f6633f27ed34f14b09843919fdb9ab08`.
  Deterministic next transition is automatic external review in a fresh independent session.
- External review v8 completed in fresh ChatGPT High session
  `6a8abbe1-0220-83ec-8391-d509247e225c`. A same-session transport correction bound the unchanged
  packet to exact subject `fc4c9e7431f19da31bf99e4be4b72c09213c0a75`; the corrected response is
  contract-valid with digest
  `sha256:194ce8a6ceaea13f7adc473db10e7b86d5307efc4647596568e091c3d108ae4f`.
- Verdict is `APPROVE` with zero Critical, Major or Minor findings and complete AC-01 through AC-10
  coverage. Ticket-contract review gate is closed. Deterministic next transition is
  `manual-acceptance -> test-craft` guide preparation; implementation remains locked until the guide
  has external approval and explicit human digest lock.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v1 review-ready

- `test-craft` completed all twelve contract Test Cases across data/contract, lifecycle,
  concurrency and security axes at `.agents/review/m4-issue-77-test-cases-v1.json`; UI/visual
  transitions are explicitly omitted because #77 has no UI.
- Draft guide `m4-77-authorized-execution-v1` is
  `.agents/manual-tests/milestone-4/77-authorized-execution-v1.md` with digest
  `sha256:250c78a9c2670b4fb755ec58ffb6cbc5ef027922c76881b4918f92d0979ec82c`.
  It locks exact PostgreSQL/SQLite independence, fault barriers, counting sentinels, focused/full
  commands, sanitized release evidence and the #77/#78 boundary.
- Canonical external guide-review packet is
  `.agents/review/m4-issue-77-guide-review-packet-v1.json`, digest
  `sha256:2bbb3999990294ebb51126c9aaa2778b026a05e8de5cf73eadf1f57efa5bb9c7`, request ID
  `review-request-sha256:450f0fde899b79425d52083d616fddee1e3943d8a85a1d1057d8f728b29503ce`.
  Next transition is independent external guide review. No implementation may begin until external
  `APPROVE` and explicit human approval lock this exact guide digest.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v1 request changes

- Independent ChatGPT High review session `6a8ac4e0-44d0-83ec-9208-da92f90fefef` returned
  `REQUEST_CHANGES` against exact subject `33f007e2cabc2a760a725fcfa0b98b56a7c73af2`, packet
  `sha256:2bbb3999990294ebb51126c9aaa2778b026a05e8de5cf73eadf1f57efa5bb9c7` and guide
  `sha256:250c78a9c2670b4fb755ec58ffb6cbc5ef027922c76881b4918f92d0979ec82c`.
- Counts are 0 Critical, 3 Major and 0 Minor. The three guide-only gaps are: complete observable
  active/retiring `m4r1` key lifecycle outcomes; expired-owner fencing that proves zero new
  observation/audit append and zero PostgreSQL write; and an executable production-composition
  proof that the typed registry is closed with no runtime plugin/discovery/registration seam.
- These findings do not change the approved Issue #77 abstractions or move reconciliation behavior
  from #78. Deterministic next transition is `test-craft` plus immutable guide v2 preparation,
  followed by fresh external review. Implementation remains blocked.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v2 review-ready

- `test-craft` v2 preserves the twelve locked cases while directly closing all three v1 findings:
  TC-03 has the complete key-lifecycle admit/deny and epoch matrix, TC-10 proves zero expired-owner
  observation/audit append or PostgreSQL write, and TC-12 exercises the production closed-registry
  and no-runtime-plugin/discovery/registration boundary.
- Draft guide `m4-77-authorized-execution-v2` is
  `.agents/manual-tests/milestone-4/77-authorized-execution-v2.md`, digest
  `sha256:1fd51587723113f6e55fddaf6f9bf4e07c6a8aaa6f3fe038f1fe2c24bfb18238`.
- Canonical packet v2 is `.agents/review/m4-issue-77-guide-review-packet-v2.json`, digest
  `sha256:3339916fdc4ee8f5bbc8b722a3b170480c92fc097351db3e1b8b28c768ad50bd`, request ID
  `review-request-sha256:c30c0c135b3808b23aa4839fa9fc816499d831136bd9f973a1365e70fedcfe31`.
  Next transition is fresh independent external review; implementation remains blocked until
  external `APPROVE` and explicit repository-owner lock of this exact digest.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v2 request changes

- Fresh ChatGPT High session `6a8acb51-6d60-83ec-9009-24fda2a88c7f` reviewed both canonical
  parts after bounded file-upload failure. The premature PART-1-only `BLOCK` is a non-authoritative
  transport artifact; the final schema-valid response is bound to subject
  `89b7e1c408a1d4a9034256202954eadbe1d24f4b`, packet
  `sha256:3339916fdc4ee8f5bbc8b722a3b170480c92fc097351db3e1b8b28c768ad50bd` and response
  `sha256:edca8011408db973899a5ca5788aaae0db1e85ea82dd98b37a2e37fc463f602a`.
- Verdict is `REQUEST_CHANGES` with 0 Critical, 4 Major and 0 Minor findings. The reviewer confirms
  all three v1 findings are closed, then identifies four fresh deterministic gaps: exact denials
  for every non-key TC-03 mutation; provider cross-binding rejection before lookup/SQLite; runtime
  isolation of test-only signer/mutators; and a fully enumerated immutable public-result matrix.
- These changes remain within `test-craft`/guide ownership, preserve all approved abstractions and
  do not add #78 reconciliation. Next transition is immutable guide v3 preparation and fresh
  external review. Implementation remains blocked.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v3 request changes

- Guide v3 and its canonical packet were committed at exact review subject
  `f6f87a4456d7bfa1ce9ceb8411427ae39bfa6abe`. Guide digest is
  `sha256:8e75255ec3756ec1d16a6ba5e8eee5e85b29b2abb1ab1f8002a4365e9b5ea906`;
  packet digest is
  `sha256:dde5fbe09b0d4680305cb65f32cc656fa612aa02c6723be4b4530f448859701f`.
- Independent ChatGPT High session `6a8ad2d8-e1e4-83ec-8018-87b4b204af0a` returned a
  contract-valid `REQUEST_CHANGES` response with zero Critical, one Major and zero Minor findings.
  Response digest is
  `sha256:55931b1e9e093ad688f857760ed7a17a45976cc12930651747940d88b1a90461`.
- The reviewer confirmed six prior findings closed. The sole remaining Major was
  `incomplete_post_acquisition_result_matrix`: TC-03 denials occurred after acquisition but were not
  classified into exact application and HTTP response shapes.
- No implementation or code review ran. The correction remained within guide/test-craft ownership
  and preserved the approved Issue #77/#78 boundary and static typed registry.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v4 review-send gate

- Guide v4 classifies every TC-03 post-acquisition denial into an exact
  `ProposalNotExecutable` application projection and exact closed HTTP error envelope. It locks the
  status, public code, complete field/value domains and forbidden fields for Workspace/resource/
  execution authority, all capability/binding/policy mismatch dimensions, reference integrity,
  trusted-store and key-lifecycle denial rows.
- TC-10 now loads both execution-outcome and post-acquisition-denial matrices independently from
  production result types, enums, serializers and HTTP mappers, and compares every application/HTTP
  row exactly once.
- Exact review subject is `c63d10c5b683d4d99e166b1c1d97627ebff38f18`. Guide v4 is
  `.agents/manual-tests/milestone-4/77-authorized-execution-v4.md` with digest
  `sha256:ca7a3aed942864408e08db0a3bc2cdf85f63dcaf2c71abd8650bad43901101f0`.
  Canonical packet is `.agents/review/m4-issue-77-guide-review-packet-v4.json`, digest
  `sha256:32fe199ba0366f2cd39f1c413ea7d403692c6c761899599d81aaed34d68d8ca4`,
  request ID
  `review-request-sha256:c7eca9a7571fc1af39b922c207781b70fbb1a850e6559160baa2a3519a9dde4a`.
- Deterministic next transition: after explicit browser action-time owner confirmation, send this
  exact v4 packet and guide through one fresh independent ChatGPT High session. Persist and validate
  the response. On `APPROVE` with zero findings, request the repository owner to lock the exact
  guide digest. On `REQUEST_CHANGES` or `BLOCK`, revise only the reported guide/test-craft gap and
  repeat external review.
- Implementation remains forbidden until external `APPROVE` and explicit human guide-digest lock.
  No per-ticket code review runs. The single final fixed-point M4 `code-review` runs only after
  Issues #75–#79 are accepted, integrated and closed, as required by the approved delivery plan.
- Validated Resume Contract:
  `C:/Users/Nhi/AppData/Local/Temp/agent-handoffs/m4-tools-human-approval-issue-77-guide-v4-review-send-v1.json`
  with digest
  `sha256:f81fbbdfe00420ce7b1841e597b4719bb93b5ac4cc48ba4f90450b30a5a1dd58`.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v4 request changes

- The exact guide v4 and canonical packet were reviewed in a fresh authenticated ChatGPT High
  session `6a8ad946-5a1c-83ec-a111-fe70a1290014` against exact subject
  `c63d10c5b683d4d99e166b1c1d97627ebff38f18`.
- The normalized response is contract-valid at
  `sha256:95e5fb4cbe5449438a0a293698c1794ee367ccca6b8565dfcc9eb70f2077d507`
  and returned `REQUEST_CHANGES` with zero Critical, two Major and zero Minor findings:
  `post_lock_finalization_clock_source_not_proven` for AC-08/TC-10 and
  `denial_matrix_identity_values_not_independently_closed` for AC-09/TC-03/TC-10.
- Guide v5 may change only the reported guide/test-craft oracles. It must add separate
  observation/finalization races that start before the generation-1 lease deadline, block on the
  governing PostgreSQL lock, cross expiry, skew non-database clocks and prove the decision uses a
  captured post-lock `clock_timestamp()`; before-expiry controls and independent state/write
  evidence remain required.
- The post-acquisition denial matrix must also define `proposal_id` and
  `logical_execution_id` as canonical lowercase RFC 4122 UUIDs exactly equal to independently
  seeded and durably reloaded scenario identities captured before the application/HTTP invocation.
  The independent fixtures must never derive expected identities from the returned projection or
  production mapper, and release evidence must capture expected-versus-actual values per row.
- These changes preserve the approved abstractions, generation-1-only #77 scope, #78 recovery
  ownership, static typed registry and no-plugin-framework constraint. No implementation or code
  review may run. The deterministic next transition is `manual-acceptance -> test-craft` to prepare
  immutable guide/test-case/packet v5, then obtain action-time confirmation for one fresh external
  ChatGPT High review.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v5 review-send gate

- Guide v5 changes only TC-03/TC-10 and their evidence projections. TC-10 now runs observation and
  finalization as distinct generation-1 operations that start before the lease deadline, block on
  the governing PostgreSQL row lock, cross expiry under skewed non-database clocks and capture the
  operation's deciding post-lock `clock_timestamp()`. Same-path before-expiry controls prove the
  operation is not spuriously fenced.
- Every post-acquisition denial now binds `proposal_id` and `logical_execution_id` to canonical
  lowercase RFC 4122 UUIDs obtained from independent seed authority and direct durable reload before
  application/HTTP invocation. The expected values cannot come from the returned projection or a
  production mapper, and neither identity is added to the closed HTTP error body.
- Exact review subject is `3bff38a6813f620daf97ec009cf35d65b1ecdc8c`. Guide v5 is
  `.agents/manual-tests/milestone-4/77-authorized-execution-v5.md` with digest
  `sha256:69059cf83119a407d34d74d3b1e5249ba5a95672ce53c78946f1d92d5fcd605c`.
  Canonical packet is `.agents/review/m4-issue-77-guide-review-packet-v5.json`, digest
  `sha256:3bd8ef211bd57998986cb99563d41b29d231c6ddda128da17f287e66a8fd4d43`,
  request ID
  `review-request-sha256:6834cd9141b887c3847941fd4a63b77ddc4fc907811dae18d824629dbfb9723f`.
- Packet validation is `VALID`; only packet Test Cases TC-03 and TC-10 changed. Acceptance criteria,
  design decisions, out-of-scope boundaries, generation-1 ownership, #78 recovery ownership and
  static typed registry remain unchanged.
- The workflow-level packet-send authorization is preserved, but each live browser message/upload
  remains subject to the browser transport's action-time representational-communication gate.
  Deterministic next transition: after the repository owner confirms this exact v5 send, use one
  fresh independent ChatGPT High session, persist and validate the response, then request the exact
  guide-digest lock only on `APPROVE` with zero findings.
- Implementation and every per-ticket code review remain forbidden. The single final fixed-point M4
  `code-review` runs only after Issues #75–#79 are accepted, integrated and closed.
- Validated Resume Contract:
  `C:/Users/Nhi/AppData/Local/Temp/agent-handoffs/m4-tools-human-approval-issue-77-guide-v5-review-send-v1.json`
  with digest
  `sha256:3dfd60efe9aa307362d24c33c77752de12d758ceccf08db612658fbb513c4160`.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v5 request changes

- The exact guide v5 and canonical packet were reviewed in fresh authenticated ChatGPT High
  session `6a8ae39b-ff88-83ec-8db4-f7ff5e02263e` against exact subject
  `3bff38a6813f620daf97ec009cf35d65b1ecdc8c`.
- The normalized response is contract-valid at
  `sha256:90e6fc7e1444e24662f46ef397425438955db2c9c886d33e969f0ba6baaac12b`
  and returned `REQUEST_CHANGES` with zero Critical, two Major and zero Minor findings:
  `pre_acquisition_denial_matrix_not_fully_exercised` for AC-01/TC-01 and
  `provider_conflict_non_finalization_not_durably_proven` for AC-09/TC-07/TC-10.
- The reviewer explicitly confirmed all eight prior guide findings closed, including the two guide
  v4 findings. Guide v6 may therefore change only the two new guide/test-craft gaps.
- TC-01 must use one independently sourced pre-acquisition denial matrix that explicitly covers
  unauthenticated principal, proposal/approval expiry where applicable, invalid execute input,
  Workspace/resource/execution denial, and material stale/mismatch rows. Each row must lock its
  application result and closed HTTP status/body, durable before/after projection where applicable,
  zero acquisition/admission/audit-start/provider activity, named sentinels and release-evidence
  inclusion.
- TC-07/TC-10 must link provider conflict evidence to an operation-correlated PostgreSQL proof. On
  the conflict path and after PostgreSQL restart/reload, the generation-1 execution remains
  `executing` with unchanged proposal/logical-execution identity and fingerprint, no terminal
  outcome/finalization row, no terminal audit append and exact zero finalization writes, while the
  existing `409 ExecutionInProgress(provider_idempotency_conflict)` public matrix row remains exact.
  The same durable non-finalization proof applies to every non-finalizing matrix row.
- These changes preserve the approved abstractions, generation-1-only #77 scope, #78 recovery
  ownership, static typed registry and no-plugin-framework constraint. No implementation or code
  review may run. Deterministic next transition is `manual-acceptance -> test-craft` to prepare
  immutable guide/test-case/packet v6, then obtain action-time confirmation for its fresh external
  ChatGPT High review.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v6 review-send gate

- Guide v6 changes only TC-01, TC-07 and TC-10 plus their evidence projections. TC-01 now uses one
  independently sourced literal row for every named authentication, input-validation, Workspace/
  resource/execution-authority, capability/binding/policy mismatch, `m4r1` trust/key/expiry and
  proposal-expiry variant. Each row locks the exact application/transport oracle, closed HTTP body,
  durable before/after projection and named zero-activity sentinels.
- TC-07 adds a sanitized content-addressed provider-conflict correlation record. TC-10 links that
  record to before/after/post-PostgreSQL-restart snapshots for every non-finalizing matrix row and
  proves generation 1 plus immutable proposal/logical-execution/fingerprint/admission identities,
  zero terminal/finalization rows, zero terminal-audit append, zero operation-correlated
  finalization writes and an unchanged terminal digest. Non-terminal observation/audit activity is
  measured separately and remains permitted.
- Exact review subject is `93d12b907ec82e71ee03620fe6c565c7fbc352c3`. Guide v6 is
  `.agents/manual-tests/milestone-4/77-authorized-execution-v6.md` with digest
  `sha256:f0d24858b8f33951c1f2e0a44f252f953e8158fbf67137950a44a775dd9cd386`.
  Canonical packet is `.agents/review/m4-issue-77-guide-review-packet-v6.json`, digest
  `sha256:f84a852e20efba84cca3c8157c9306cea3b732d1befe4d4f600d11e6c7aac081`,
  request ID
  `review-request-sha256:820aa5d135c09f3d9e92218f5b56d41fe093d368784255bf893218756df62f0b`.
- Packet validation is `VALID`. Acceptance criteria, design decisions, invariants, command
  projections, out-of-scope boundaries, static typed registry and the generation-1 #77 versus
  recovery-only #78 ownership boundary are byte-for-byte unchanged from packet v5.
- Workflow-level canonical-packet authorization remains active, but the stricter browser transport
  policy requires fresh action-time repository-owner confirmation for each live external reviewer
  message/upload. The v5 confirmation has been consumed and does not authorize v6 transport.
- Deterministic next transition: after explicit confirmation of this exact v6 send, use one fresh
  authenticated ChatGPT High session, persist and validate its JSON response, and request human lock
  of the exact guide digest only if the verdict is `APPROVE` with zero findings.
- No Issue #77 implementation or per-ticket code review may begin. The one final fixed-point M4
  `code-review` remains forbidden until Issues #75–#79 are accepted, integrated and closed.
- Validated Resume Contract:
  `C:/Users/Nhi/AppData/Local/Temp/agent-handoffs/m4-tools-human-approval-issue-77-guide-v6-review-send-v1.json`
  with digest
  `sha256:07f68a6fc6f171b743579496f36d8536f058e75406dc3b6a063d938292e2e680`.

### Acceptance checkpoint — 2026-08-23, Issue #77 guide v6 request changes

- The exact guide v6 and canonical packet were reviewed in fresh authenticated ChatGPT High
  session `6a8af484-7eec-83ec-a492-0d4f0d7ec657` against exact subject
  `93d12b907ec82e71ee03620fe6c565c7fbc352c3`.
- Native upload failed after the bounded retry, so the already governed fallback sent one pasted
  attachment containing the byte-exact packet and guide. The first response preserved the review
  semantics but used the wrong `coverage.criteria` shape; one same-session technical retry changed
  only that array to the required ten string IDs.
- The normalized response is contract-valid at
  `sha256:0e66eb00a6999db9c6aa3a8dd4ff85062b5d350683460930d030978a6658daef`
  and returned `REQUEST_CHANGES` with zero Critical, two Major and zero Minor findings:
  `material_reference_mismatch_stale_invalidation_not_exercised` and
  `post_acquisition_reference_denial_matrix_incomplete`.
- The provider-conflict durability finding is closed. The two remaining guide/test-craft gaps are:
  an explicit material reference-mismatch stale/invalidation row in TC-01; and complete
  post-acquisition protected-scope-corruption/reference-expiry rows bound to TC-03/TC-04/TC-10
  application, HTTP, durable-state and post-restart non-finalization evidence.
- Adjudication sustains both findings, but the first exposes a contract-level ambiguity: ticket v8
  requires a typed material-reference stale reason, while the approved design closes
  `CompatibilityCheckerV1` and its reason taxonomy over capability, scope-binding and policy only.
  Guide v7 must not invent a new reason or silently reinterpret it as an existing binding reason.
- Recommended Design correction is to restore the approved split without changing abstractions:
  material capability/scope-binding/policy incompatibility becomes stale; malformed, integrity,
  trust, key and expiry reference denials fail closed and require a new proposal without creating a
  new `CompatibilityReason`. After that ticket correction is externally reviewed, guide v7 can add
  the exact protected-scope and reference-expiry post-acquisition rows required by the second
  finding.
- No implementation or code review may run. Deterministic next transition is an owner-authorized
  exceptional ticket-contract correction v9, followed by external ticket review and then guide v7.

## Multi-session continuation plan — revision 2, 2026-08-23

This section is the durable forward plan from the current checkpoint to verified closure of #74.
It does not replace the fixed decisions or ticket lifecycle above. The mutable ledger remains the
transition authority; every later session resumes from its exact `next_valid_transition`.

### Current checkpoint

- Canonical `main` remains pinned at `6312c4c4230032aa92ca5915803fcfaf564354fa`.
- Integration is `nhibuaa/m4-tools-human-approval` at
  `b1d101e3636bb3a1ee013d304f70e37b9cb61418`.
- Issue #77 worktree is `D:/Developer/Projects/knora-agent-worktree/issue-77-m4.3`, branch
  `nhibuaa/issue-77-m4.3`. Commit `0ca6010dfadb6643abf199f2744aee536ba43211`
  is the source checkpoint before this plan revision; exact live head/clean/synchronization state
  must always be read from Git and the mutable ledger because embedding the plan's own future
  commit would be self-referential.
- #75 and #76 are closed and integrated through PRs #80 and #81. #77 is open; #78 and #79 remain
  blocked by the native graph. No #77 implementation or PR exists.
- Guide v6 review is `REQUEST_CHANGES`. Adjudication requires a contract correction before a new
  guide can be sealed; no code review is authorized.

### Contract checkpoint — 2026-08-23, Issue #77 revision v9 locally approved

- Exceptional correction v9 is `.agents/review/m4-issue-77-revision-v9.md`, exact Git blob
  `c6a552166658099bf6148b5b184caf69a6913c75`, digest
  `sha256:bce76ae5dd7c7a7668c7675c8df2e3251dbfe41424ac7687ea3e83fd1fa875b5`.
- It preserves the existing abstractions and restores the authoritative split: only material
  capability, scope-binding or policy incompatibility uses the closed `CompatibilityCheckerV1`
  stale/invalidation taxonomy. Reference syntax, integrity, scope, trusted-store, key and expiry
  failures fail closed; replacing the immutable target/reference requires a new proposal and human
  approval without inventing a `reference_*_mismatch` compatibility reason.
- It adds distinct post-acquisition protected-scope-corruption and reference-expiry rows with exact
  application/HTTP denial mappings, zero admission/provider activity, fresh PostgreSQL-time and
  restart-stable non-finalization evidence. Reconciliation, takeover, retry and generation 2+
  remain wholly owned by #78.
- Independent Standards/ADR-0015 and Spec/Issue-#74/Design/adjudication audits both returned
  `APPROVE`; aggregate counts are zero Critical, Major, Minor and Nit findings.
- Revision v9 was committed/pushed at `67858a056d14319525ca7bf7152e08f10bd7c012`, published to
  Issue #77 and read back exactly equal to the artifact. Canonical packet v9 is a contract-valid
  delta over self-contained packet v6 at
  `.agents/review/m4-issue-77-ticket-review-packet-v9.json`; packet digest is
  `sha256:097514f4b155d43aa40293d827a397e66962523761423c02d311bfc8f564476a`, request ID is
  `review-request-sha256:bdc313483f34566d012d86082d4edba1f214963e259f6ca068ae3fab6be178fa`
  and raw file digest is
  `sha256:2a8bed72c71b6696964e72bff473f2690f63c51f0a41c1d402aedda947d50a12`.
- Packet validation reconstructs 10 acceptance criteria, 12 required Test Cases, 6 evidence groups
  and the exact two adjudicated findings marked `ADDRESSED_IN_V9`. An independent packet audit
  returned `APPROVE` with zero Critical, Major or Minor findings and found no sensitive-field or
  abstraction/scope drift.
- No implementation, guide v7 or code review is authorized yet. After this packet-ready checkpoint
  is committed/pushed, its commit becomes the exact external-review subject. The stricter browser
  transport gate then requires fresh action-time owner confirmation before one new authenticated
  ChatGPT High session receives the exact v9 packet and ticket body.

### Ticket review v9 outcome and packet-correction checkpoint — 2026-08-23

- The owner confirmation was consumed once; packet v9 was sent through the fresh authenticated High
  session `https://chatgpt.com/c/6a8b02e6-6270-83ec-8c5d-157070135a92` against subject
  `b9cc7c9e09597e36183fa5ee1e23fd73d12bdbf2`. The reviewer returned `REQUEST_CHANGES` with
  `0 Critical / 4 Major / 0 Minor`; this is a packet-observability correction, not an abstraction
  or ticket-contract revision.
- The four sustained classes are: complete dispatch-epoch/static-registry mutation and lock-order
  oracles; field-by-field atomic `DispatchAdmissionWitness` durability; negative production
  composition/DI reachability proof for test-only harness/signing/mutation adapters; and valid-lease
  observation/finalization coverage before retaining the post-expiry fencing matrix.
- The transport response used two non-canonical reviewer category labels. The canonical response
  projection maps `concurrency_authorization -> oracle` and `postgresql_durability -> evidence`
  without changing severity, wording, coverage or verdict. The normalized response is schema-valid
  at `sha256:ea8e083db65b8f236466e3cf23dbfe815d111892a368e88156b83661147eb56c`; the raw transport
  digest remains `sha256:d7affa25caa184cfa8406ae9662240348961c956afec2af61174e2b365a964de`.
- Adjudication `.agents/review/m4-issue-77-ticket-v9-adjudication-v1.json` records
  `packet_correction_required`, `abstraction_change_required: false`, and the next valid
  transition `packet-v10-on-contract-v9`. No implementation, guide preparation, PR, or code review
  is authorized. Packet v10 must retain the exact v9 ticket digest/revision and add only the four
  requested oracle families before a fresh external review.
- Canonical packet v10 is `.agents/review/m4-issue-77-ticket-review-packet-v10.json`, a round-2
  delta over self-contained packet v6 that explicitly supersedes v9 while retaining the exact v9
  ticket revision/digest. It validates at
  `sha256:5c51d81118c1f43a7972268657e99d5f2bdbb1bec248ce96af4d7e9db1c985e9` with request ID
  `review-request-sha256:7d84b7cdef42b7f9e2046fc985e5bbad976fc2f62d3000469dded064942c6d60`.
  Independent packet audit returned `APPROVE` with zero Critical, Major, Minor or Nit findings,
  verified all four v9 findings as `ADDRESSED_IN_V10`, and found no abstraction or #78 scope drift.
  The exact packet checkpoint must be committed/pushed before a fresh action-time-confirmed review.
- The owner confirmed that exact send. A fresh ChatGPT High session at
  `https://chatgpt.com/c/6a8b0bbb-a858-83ec-897d-ccb36fe3b6a2` reviewed packet v10 on
  subject `d4064c4d8afcc9c552d01489f3ae400063382049` and returned `APPROVE` with zero Critical,
  Major or Minor findings and complete AC-01 through AC-10 coverage. The contract-valid normalized
  response digest is `sha256:5f198dba77d20faaa14b6c746b642b11560a3669c67bef075251b1fc5708d4ad`;
  normalization only bound the placeholder session ID to the observed chat identity and sealed the
  response digest. This review fills the current Issue #77 ticket-review cadence slot.
- The next transition is `manual-acceptance -> test-craft` to create a new guide revision from the
  approved v10 oracles. Guide v6 remains immutable `REQUEST_CHANGES` history; implementation,
  PR creation and code review remain unauthorized until the replacement guide is externally
  approved and human-locked.

### Guide v7 preparation and packet checkpoint — 2026-08-23

- `manual-acceptance -> test-craft` produced
  `.agents/review/m4-issue-77-test-cases-v7.json` and
  `.agents/manual-tests/milestone-4/77-authorized-execution-v7.md`. All twelve v6 cases remain;
  the v9 taxonomy correction, two missing post-acquisition reference denials and all four v10
  oracle families are now explicit without adding #78 recovery behavior.
- An independent guide audit initially found three Major ambiguities: grouped admission-witness
  field names, accidental public treatment of `provider_outcome_not_found`, and an admission
  identity assertion on pre-admission denials. The corrected exact bytes were re-audited
  `APPROVE` with zero Critical, Major, Minor or Nit findings.
- The final guide digest is
  `sha256:c345a3f1ef55aa229238e66ebcb4c18c9228f5715449c6a9469efbfe09cc8d93`;
  the test-case artifact digest is
  `sha256:f1d842747a0c49b930d8e82b71efca658b3e231686b786dfaf96b9b699412771`.
- Canonical self-contained packet
  `.agents/review/m4-issue-77-guide-review-packet-v7.json` validates at semantic digest
  `sha256:930b5430659c8f1bd179115d45b6ff4125383c3c2f71fffb7df89dc9ac6d0765`,
  request ID
  `review-request-sha256:81f08de470b6d9e1cfef0cf5d8621d4e135896b2ef92563af34f79449795cb1a`
  and raw-file digest
  `sha256:c542c2d66f1f35bfe74d9b25367c252e12fc80a21f0d84e755bf23ab99380dd5`.
  Independent packet audit returned `APPROVE` with zero findings and confirmed no stale v8
  taxonomy, sensitive-field leak or #78 scope drift.
- Implementation, PR creation and code review remain unauthorized. After this exact checkpoint is
  committed and pushed, the next valid transition is fresh action-time owner confirmation followed
  by external guide review in a new authenticated ChatGPT High session. An external `APPROVE` and
  explicit human lock of the exact guide digest remain mandatory before implementation.

### Guide v7 external review outcome — 2026-08-24

- The owner supplied fresh action-time confirmation. Exact packet v7 was sent as one pasted-text
  attachment to the new authenticated ChatGPT High session
  `https://chatgpt.com/c/6a8b8733-e20c-83ec-86a6-f3dbc218225a` against subject
  `a7e59d6aba182bc2cba1a7dcae799d18eba5c539`.
- The reviewer returned `APPROVE` with `0 Critical / 0 Major / 0 Minor`, complete AC-01 through
  AC-10 coverage and GR-001 through GR-016 closed. The raw response preserved exact packet and
  guide digests but supplied placeholder/stale non-contractual transport metadata; the normalized
  response binds the observed chat identity and exact pushed subject, then seals at
  `sha256:240b0f1718024568262cfadbd9fd9a1f66dd192a28b17ceecfa3a20f99c5121c`.
  The canonical response validator returns `VALID / review_response_valid`.
- This review fills the current Issue #77 guide-review cadence slot. The next valid transition is
  explicit repository-owner lock approval for exact guide revision
  `m4-77-authorized-execution-v7` at
  `sha256:c345a3f1ef55aa229238e66ebcb4c18c9228f5715449c6a9469efbfe09cc8d93`.
  Implementation, PR creation and code review remain unauthorized until that lock is recorded.

### Guide v7 human lock — 2026-08-24

- The repository owner explicitly read and locked exact guide revision
  `m4-77-authorized-execution-v7` at
  `sha256:c345a3f1ef55aa229238e66ebcb4c18c9228f5715449c6a9469efbfe09cc8d93`.
  `.agents/review/m4-issue-77-guide-approval-v7.json` records the immutable approval at digest
  `sha256:c1d9e08476c1d90c5a7b2fa3b4590a0a6463835ba6a57d7f08c723aab903dc24`.
- The guide is now immutable. Any semantic implementation-discovered change returns to Design and
  requires a new externally reviewed and human-locked guide revision. The next valid transition is
  Issue #77 implementation through `implement -> tdd`. Per-Issue code review remains disabled;
  the sole code review remains the final M4 fixed-point review after #75–#79 complete.

### Forward transitions

1. **Reconcile Issue #77 contract.** Skills: `feature-delivery`, `codebase-design`.
   Prepare exceptional contract correction v9 without changing the deep
   `WriteProposalWorkflow.handle` Interface: restore the approved capability/scope-binding/policy
   stale taxonomy, keep integrity/trust/key/expiry reference denials fail-closed, and make the
   post-acquisition protected-scope/reference-expiry oracles explicit. Publish the corrected Issue
   #77 body, generate a canonical packet, obtain its required independent external review and do
   not prepare a guide until the ticket verdict is `APPROVE` with zero findings.
2. **Prepare and lock Issue #77 acceptance.** Skills: `manual-acceptance -> test-craft`,
   `feature-delivery`. Create immutable guide/test-case/packet v7 containing only the surviving
   v6 corrections, externally review it, and ask the repository owner to lock the exact approved
   guide digest. No implementation starts before that lock.
3. **Deliver Issue #77.** Skills: `implement -> tdd`, `manual-acceptance`, `feature-delivery`;
   `resolving-merge-conflicts` only for a real conflict. Implement generation-1 authorized
   execution, run focused/full/Ruff/Compose/clean-Alembic verification serially, publish a child PR
   into integration, execute the locked guide on the exact candidate, obtain human PASSED approval,
   reconcile with integration, rerun affected evidence, merge, synchronize, close #77 and remove
   only its clean/reachable worktree and branches. Do not run per-Issue code review.
4. **Deliver Issue #78.** Skills: `manual-acceptance -> test-craft`, `implement -> tdd`,
   `feature-delivery`. First verify the native frontier and reconcile the #78 ticket contract with
   final #77 v9, then externally review that exact ticket. Create an isolated clean-baseline
   worktree from the current integration head; prepare/external-review/human-lock its guide,
   implement provider-first observation, orphan recovery, stale takeover, current retry
   authorization and same-identity retry; verify, execute exact-SHA acceptance, obtain human PASSED
   approval, reconcile selective invalidation, merge its child PR, synchronize, close and clean it.
   Do not run per-Issue code review.
5. **Deliver Issue #79.** Skills: `manual-acceptance -> test-craft`, `implement -> tdd` only for
   integration gaps/harness, `feature-delivery`. Verify the native frontier, externally review the
   exact ticket, create an isolated clean-baseline worktree from current integration, and include
   the final roadmap/release-ledger projection before acceptance. Prepare/external-review/human-lock
   and execute the integrated M4 release guide, preserve full #75–#78 and M1–M3 evidence, obtain
   exact-SHA human PASSED approval, reconcile selective invalidation, merge its child PR,
   synchronize, close and clean it. Do not run per-Issue code review.
6. **Run the one final M4 review.** Skills: `code-review`, `feature-delivery`; remediation uses
   `implement -> tdd` and `manual-acceptance`. Only after #75–#79 are accepted, integrated and
   closed, fetch/assert the pinned `main` base, create the complete fixed-point descriptor described
   above, and run one Standards+Spec review stage. Remediate at most twice with affected acceptance
   reruns, repinning and re-reviewing every changed head, and require `APPROVE` with zero Critical/
   Major findings. Then validate cadence evidence as `ready`.
7. **Publish and close M4.** Skills: `feature-delivery`; `resolving-merge-conflicts` only if `main`
   moved. Open the parent PR from the exact reviewed integration head to `main`, re-fetch and
   revalidate the base, merge with a merge commit, fast-forward canonical `main`, run post-merge
   pytest/Ruff/Compose/clean-Alembic verification, close #74, stop M4 Compose services without
   deleting volumes, remove all clean/reachable M4 worktrees and local/remote branches, fetch/prune
   and prove the completion invariants.

### Session checkpoint rule

After every transition, update `m4-workflow-ledger-v1.json`, append one validated observability
event and commit/push the owning branch. Before a context boundary, use `session-continuity` to
publish one Resume Contract containing the exact issue, branch, worktree, source/base/head SHA,
ticket and guide revision/digest, Evaluation history, PR/integration state, completed transitions,
blockers and one `next_valid_transition`. A new session validates that contract against Git, GitHub,
this plan and the ledger before acting. Conversation history is never transition authority.

Completion is proven only when Issues #74–#79 are closed, PRs #80/#81 plus the #77/#78/#79 child
PRs and the parent PR are merged, final review and cadence gates are green, post-merge verification
passes, `main == origin/main`, canonical and all retained worktrees are clean, and no M4 worktree or
local/remote branch remains.
