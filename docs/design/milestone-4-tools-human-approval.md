# Milestone 4 — Tools and human approval design

Status: approved shared-understanding checkpoint, 2026-08-22

This design records the approved M4 boundary. It extends the existing capability-first seams
without introducing a plugin framework, generic workflow engine, or vendor coupling.

## Capability scope

M4 proves one static typed read capability, `ticket_lookup`, and one write capability,
`create_ticket`. A `SupportToolGateway` owns the external provider contract. A fake adapter is
for deterministic unit tests; release evidence uses a deterministic reference provider with an
independent external-state and idempotency ledger. The reference implementation uses Python's
standard-library SQLite boundary so provider truth remains durable and separate from Knora's
PostgreSQL workflow state. M4 claims contract-level provider semantics, not guarantees of a
specific vendor.

## Authority and provenance

`WorkspacePrincipal` authenticates a request and authorizes one Workspace. It is not an action
actor. A proposal records both the authenticated caller provenance and a typed `ProposalActor`
(`human`, `model` or `system`). Approval records an `ApprovalActor` as a separate semantic, derived
from a current human approval authority. Models and systems cannot approve. Separation-of-duties is
action policy, not a blanket `approver != proposer` rule.

Execution is separately authorized. `ExecuteApprovedProposal` revalidates current Workspace,
capability and execution authority immediately before the provider side effect. Human approval does
not grant execution authority; a bounded execution worker or another explicitly authorized actor
must pass the current execution policy.

## Exact proposal binding

Proposal and approval bind an immutable provenance bundle containing:

- capability identity/version/digest;
- Workspace-to-external-scope binding identity/version/digest;
- authorization, approval and execution policy identity/version/digest sufficient for a declared
  compatibility check;
- integrity-protected external resource reference;
- canonical target/parameter digest and one immutable logical execution identity.

Material capability, scope-binding or policy incompatibility makes the proposal stale and
non-executable. The old approval is never applied under a new policy or target; a new proposal and
approval are required. Temporary execution-authority revocation may leave an otherwise valid
proposal `approved` and block only the execution attempt.

`ExternalResourceReference` is server-minted or integrity-protected and is bound to Workspace,
capability/version, scope-binding snapshot, resource identity and reference-key version. Raw
caller-supplied global resource IDs are not an authorization reference.

## Workflow and lifecycle

`WriteProposalWorkflow.handle` accepts typed commands:

```text
ProposeWriteAction
ApproveProposal
RejectProposal
ExecuteApprovedProposal
ReconcileExecution
```

The lifecycle is `proposed -> approved/rejected -> executing -> succeeded/failed`.
`indeterminate_external_outcome` and `provider_outcome_not_found` are typed execution observations,
not additional lifecycle states.

Approval/rejection uses an atomic compare-and-swap on the immutable proposed revision. Exactly one
decision wins; the loser receives a typed already-decided result. Material edits are forbidden and
must create a new proposal identity.

Expiry blocks starting a new execution from `approved`, but does not block observation or
reconciliation of an execution that already began.

## Authorization-before-lookup

`ticket_lookup` executes authentication, Workspace authorization, static capability resolution,
Workspace scope-binding resolution, resource-reference integrity verification and resource-scope
authorization before `SupportToolGateway.lookup_ticket`. Any failure returns before gateway
invocation. The gateway repeats scope checks as defense in depth.

## Execution, crash recovery and reconciliation

Concurrent execution uses one immutable logical idempotency identity. `ToolActionStore` persists
execution owner, lease expiry/generation, request fingerprint and observations; atomic acquisition
prevents two current owners, while the provider ledger enforces the external no-duplicate
guarantee.

`ReconcileExecution` handles both known indeterminate attempts and orphaned `executing` records
with no durable observation. It first reads provider outcome using the same logical identity. A
stale lease can be taken over atomically; stale owners cannot finalize after generation changes.
Provider `not found` is non-terminal and permits safe retry with the same key. If a write retry is
needed, the current `ExecutionAuthorizer`, exact capability/scope/policy compatibility and current
Workspace/resource authorization all run again. Observation authority alone never grants write
authority.

The reference provider owns the authoritative external resource and idempotency ledger separately
from `ToolActionStore`. Provider success/rejection is reconciled into the Knora lifecycle; unknown
outcomes remain explicit and cannot be fabricated as success or failure.

## Application and verification seams

- Existing `authenticate_principal -> WorkspacePrincipal` seam.
- `HumanApprovalAuthorizer`, `ExecutionAuthorizer` and `WorkspaceResourceAuthorizer` policy seams.
- Integrity-protected `ExternalResourceReference` mint/verify seam.
- `ReadTool.execute(ReadToolCommand, principal)`.
- `WriteProposalWorkflow.handle(TypedWriteCommand, principal, actor_context)`.
- `ToolActionStore` atomic transition/idempotency/audit seam.
- `SupportToolGateway` lookup/create/reconcile provider seam.
- HTTP seams for lookup, proposal, approve/reject, execute and reconcile.
- Reference-provider contract harness with independent SQLite state/idempotency ledger.

Acceptance must cover authorization-before-lookup, actor/authority separation, exact binding and
policy compatibility, concurrent approval and execution, both crash windows, stale-owner fencing,
provider not-found recovery, duplicate suppression, definitive failure visibility and audit
reconstruction. Existing M1–M3 regression evidence remains required.

## Delivery ordering

- Issues #75 and #76 are the parallel frontier. #75 owns the read capability, resource-reference
  and provider boundary; #76 owns the write proposal, human decision and durable proposal state.
- Issue #77 composes both accepted seams and is blocked by #75 and #76.
- Issue #78 adds crash recovery and provider reconciliation after #77.
- Issue #79 is the integrated acceptance and release gate and is blocked by #75–#78.

The graph has no M4.1-to-M4.2 dependency. Their implementation and focused tests may proceed
independently; PostgreSQL-backed verification is serialized because the local baseline uses one
shared test database. Every ticket reconciles with the latest integration head before acceptance
and merge.
