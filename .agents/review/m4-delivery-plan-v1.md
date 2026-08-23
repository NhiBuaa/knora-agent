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
  remaining sequence is: externally review and human-lock guide v4; remediate with TDD; execute the
  locked guide; obtain explicit human approval of PASSED; reconcile/integration-verify; merge PR
  #81; synchronize integration; close #76 and clean its branch/worktree. There is no child review
  v4.
- Guide v4 must prove deep policy-snapshot immutability; policy-selected, digest-bound expiry through
  production composition; one canonical-json-v1 implementation; complete PostgreSQL provenance,
  replacement, stale and expiry reconstruction; an explicit zero-count provider-write sentinel;
  and the reconciled #75 registry/reference integration boundary. All prior v3 history stays
  append-only and invalidated.

### Exact next transition

- Exact #76 subject: `23186fbdffb3f5e2ba25733dcf035b505a7488e0`.
- Exact guide digest:
  `sha256:a500127fc886aa53a9f0374a72e9d3a4301d64e541d5afb2d3f6243afcb22862`.
- Canonical external guide-review packet digest:
  `sha256:9ac8bf11c65b66be770d445b82676f24db86d92b8ddaaa0ac4aab5c0933c62b1`.
- Review request ID:
  `review-request-sha256:03537afc4887aa24240ab1a9c6794e66df6111557e79df35271eb4e18d772651`.
- A later read-only check proved the connected ChatGPT session is authenticated and the new-chat
  composer is ready. No packet has been transmitted.
- Resume only after the human gives action-time confirmation to send this exact redacted packet.
  Reuse the packet/request identity above, validate the external guide response, then present the
  externally reviewed guide digest for explicit human lock approval. Implementation remains blocked
  until external `APPROVE` and human guide lock both pass.

After #76, advance #77, #78 and #79 in graph order using the same guide → implementation → manual
acceptance → integration lifecycle, without per-Issue code review. After #79 closes, run the one
final M4 code review and cadence gate, then publish/merge #74 to `main`, post-merge verify, close
#74 and complete all cleanup invariants.

At every context boundary, `session-continuity` writes a validated Resume Contract containing this
plan/ledger, exact branch heads, guide/Evaluation identities, blockers and one deterministic next
transition.
