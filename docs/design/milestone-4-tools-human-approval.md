# Milestone 4 — Tools and human approval design

Status: contract revision 4 externally approved at exact subject
`5ffb59d2bbc4175a40cda12e714851d6c1e83cb0`, 2026-08-22

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

## Canonical values and digests

M4 uses `canonical-json-v1` wherever a digest binds approved intent. Typed values are projected to
JSON with sorted object keys, array order preserved, UUIDs in lowercase hyphenated form, enums as
their lowercase wire values, UTC timestamps as RFC 3339 with six fractional digits and `Z`, and no
floating-point values. Strings are Unicode NFC with CRLF/CR normalized to LF; NUL is rejected.
Encoding is UTF-8 with no ASCII escaping and compact `,`/`:` separators. A digest is lowercase
`sha256:<64 hex>` over those exact bytes.

`CreateTicketParameters` contains only `title` and `description`. Title is NFC-normalized, has no
leading/trailing whitespace, and contains 1–200 Unicode scalar values. Description is normalized in
the same way, permits embedded LF, and contains 1–10,000 scalar values. Empty, over-limit, NUL, or
non-string values fail validation before proposal persistence. The canonical parameter digest covers
the normalized `{title, description}` object; caller-supplied digests are never trusted.

Material proposal intent consists of Workspace identity, authenticated caller provenance, proposal
actor provenance, action, verified target-reference claims, normalized parameters, capability
identity/version/digest, external-scope binding identity/version/digest, the complete policy
provenance bundle, policy-selected expiry, and the server-generated logical execution identity.
Every material field is immutable. Any replacement creates a new proposal identity and new approval
requirement.

## External resource reference

M4 chooses one representation: `m4r1.<payload>.<mac>`, where payload and MAC are unpadded base64url.
The canonical payload contains schema version, server-generated 256-bit `reference_id`, key version,
Workspace ID, capability identity/version, binding identity/version/digest, resource kind, resource-
identity digest, issued-at and expires-at. It never contains a raw provider resource ID. The MAC is
HMAC-SHA-256 over the exact canonical payload bytes and is compared in constant time.

The trusted reference store maps `reference_id` to an opaque provider-routing handle and the same
claims digest; only the provider adapter may resolve that handle to a raw provider resource ID.
`ExternalResourceReferenceMinter.mint` is callable only after current Workspace/resource
authorization. For lookup or any new provider write,
`ExternalResourceReferenceVerifier.verify_for_side_effect` parses the envelope, resolves the key
version, verifies MAC and expiry, compares Workspace/capability/binding claims, then resolves and
matches the trusted store record. It returns a `VerifiedExternalResource`; only a subsequent current
`WorkspaceResourceAuthorizer` decision may produce the `AuthorizedExternalResource` accepted by the
gateway.

Execution acquisition persists an immutable `AuthorizedExecutionBindingSnapshot` in the same
PostgreSQL transaction as `state=executing`. The snapshot contains the verified `reference_id`,
claims digest, opaque routing handle, resource kind/identity digest and exact external-scope binding
identity/version/digest. It contains no raw provider ID and can be created only from the fully
verified and currently authorized resource above.

`ObservationReferenceResolver.resolve_started_execution(snapshot, principal)` is the separate,
read-only reconciliation path. It requires current path-Workspace equality and current
`WorkspaceResourceAuthorizer` permission for the stored exact scope/resource, verifies that the
snapshot still matches the immutable execution/proposal record, and resolves only its trusted opaque
routing handle. Because authenticity and scope were durably established before execution began,
token expiry or later key revocation does not block provider-outcome observation or terminal
finalization. A missing/mismatched snapshot or trusted-store record returns a typed non-terminal
observation denial/unavailable result and never fabricates `failed`.

The key ring has exactly one `active` mint key and may retain `retiring` verify-only keys. For lookup,
execution acquisition or any provider write/retry, `unknown` or `revoked` keys, malformed payload/MAC,
expiry, claim mismatch and missing/mismatched store records fail closed. Rotation does not retarget an
approved proposal: its exact non-revoked key version and token remain valid until expiry. Revocation
or expiry makes the proposal non-executable for a new provider call and requires a new proposal; it
does not erase an already-started execution snapshot or prevent authorized outcome observation.
Syntax failure maps to `INVALID_TOOL_RESOURCE_REFERENCE`; authenticated integrity or scope failure
maps to the non-leaking `TOOL_RESOURCE_ACCESS_DENIED`. No unverified provider identity reaches
`SupportToolGateway`, and the observation-only resolver can never produce provider write authority.

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

`CompatibilityCheckerV1.check(approved, current)` owns compatibility. Its inputs are the approved
and current capability, external-scope binding and policy-provenance tuples. M4 permits only exact
identity, version and digest equality; unknown values and resolver failures are incompatible.
`latest` lookup and caller compatibility assertions are forbidden. Closed reason codes distinguish
`capability_identity|version|digest_mismatch`, `binding_identity|version|digest_mismatch`, and
`policy_identity|version|digest_mismatch`. A future non-equality rule requires a new checker version
and immutable compatibility record and cannot reinterpret an M4 approval.

Compatibility failure leaves the immutable lifecycle decision intact but projects
`executable=false` with the typed stale reason; a new proposal/approval is required. Current
`ExecutionAuthorizer` denial returns `execution_not_authorized` while an otherwise exact proposal
remains `approved` and non-stale. For an in-flight `executing` proposal, incompatibility still permits
provider outcome observation but forbids a new provider write retry.

## Typed application interface

`ReadToolCommand(ticket_reference)` returns an allowlisted `TicketLookupResult` containing only the
opaque ticket reference, title, status and summary. Provider IDs, external-scope identifiers, SDK
objects and persistence fields are never public.

`CapabilityResolver.resolve_for_proposal(workspace_id, capability_id)` is the narrow seam consumed by
#76. It returns a typed `ResolvedCapabilityContext` with exact capability identity/version/digest,
required resource kind and binding-reference requirements. A fake resolver is the #76 test adapter;
#76 must not import #75's concrete registry or provider adapter. Integration later injects the
accepted static registry without changing this interface.

`WriteProposalWorkflow.handle` accepts the following immutable commands plus separately supplied
`WorkspacePrincipal` and trusted `ActorContext`:

- `ProposeWriteAction(capability_id, target_reference, title, description)`; IDs, provenance,
  canonical digests, policy expiry and logical execution identity are server-derived.
- `ApproveProposal(proposal_id, expected_revision)`.
- `RejectProposal(proposal_id, expected_revision, reason_code)`, where reason is one of
  `not_approved`, `incorrect_target`, `incorrect_parameters` or `other`.
- `ExecuteApprovedProposal(proposal_id, expected_revision)`; execution owner and lease configuration
  come from trusted composition, not the request.
- `ReconcileExecution(proposal_id, expected_lease_generation)`; recovery owner is trusted context.

Request schemas forbid extra fields. In particular, caller, proposal actor, approval actor,
execution actor, authority snapshots, digests, provider IDs and logical execution IDs cannot be
supplied or overridden by an HTTP client. `HumanApprovalAuthorizer` derives the current human
`ApprovalActor`; model/system contexts receive `approval_forbidden`.

Closed results are:

- proposal: `ProposalCreated`, `ProposalApproved`, `ProposalRejected`, `AlreadyDecided`;
- execution: `ExecutionSucceeded`, `ExecutionFailed`, `ExecutionIndeterminate`,
  `ExecutionInProgress`, `ExecutionFenced`, `ProposalNotExecutable`;
- reconciliation: `ReconciledSucceeded`, `ReconciledFailed`, `ProviderOutcomeNotFound`,
  `ReconciliationIndeterminate`, `RetryAuthorizationDenied`, `ExecutionFenced`.

Every result carries the current sanitized `ToolProposalProjection`. The projection contains the
proposal ID, Workspace, lifecycle state/revision, action, opaque target reference, normalized
parameters, caller/proposal/decision actor provenance, exact capability/binding/policy identities and
digests, logical execution identity, created/expiry/decision timestamps, `executable` plus typed
non-executable reason, and a sanitized execution projection. The read projection includes ordered
append-only audit events but no raw provider resource ID, secret, MAC key, internal exception or SDK
object.

## HTTP interface and safe outcomes

The public routes are:

- `POST /v1/workspaces/{workspace_id}/tools/ticket-lookup` with `{ticket_reference}`;
- `POST /v1/workspaces/{workspace_id}/tool-proposals` with
  `{capability_id, target_reference, title, description}`;
- `GET /v1/workspaces/{workspace_id}/tool-proposals/{proposal_id}`;
- `POST .../{proposal_id}/approve|reject|execute|reconcile` with only the command fields above.

All routes authenticate first and require path Workspace equality before scoped lookup. Responses
use the existing `{"error":{"code":"..."}}` error envelope. Authentication is 401; Workspace,
actor, reference-integrity and current-authority denial are 403; an authorized absent proposal or
provider ticket is 404; malformed reference is 400 and schema validation is 422; already-decided,
stale, expired, revision/fingerprint conflict and current execution contention are 409; provider
contract violation or definitive provider request failure is 502. Indeterminate execution and
provider-outcome-not-found return a 202 non-terminal projection and never fabricate `failed`.

M4 closes the public error mapping. These exact uppercase codes are the sole `error.code` values for
the named outcome; unknown internal/provider codes never pass through:

| Boundary outcome | HTTP | Public `error.code` |
| --- | ---: | --- |
| missing/invalid authentication | 401 | `UNAUTHENTICATED` |
| path Workspace/current Workspace denial | 403 | `WORKSPACE_ACCESS_DENIED` |
| model/system or unauthorized human decision | 403 | `TOOL_APPROVAL_FORBIDDEN` |
| current execution-authority denial | 403 | `TOOL_EXECUTION_NOT_AUTHORIZED` |
| malformed `m4r1` syntax | 400 | `INVALID_TOOL_RESOURCE_REFERENCE` |
| reference integrity/scope denial or gateway `provider_scope_denied` | 403 | `TOOL_RESOURCE_ACCESS_DENIED` |
| authorized `provider_resource_not_found` | 404 | `TOOL_TICKET_NOT_FOUND` |
| authorized missing proposal | 404 | `TOOL_PROPOSAL_NOT_FOUND` |
| schema/extra field/invalid reject reason or parameter bound | 422 | `TOOL_REQUEST_INVALID` |
| `AlreadyDecided` | 409 | `TOOL_PROPOSAL_ALREADY_DECIDED` |
| material compatibility mismatch | 409 | `TOOL_PROPOSAL_STALE` |
| expiry before new execution | 409 | `TOOL_PROPOSAL_EXPIRED` |
| proposal revision CAS mismatch | 409 | `TOOL_PROPOSAL_REVISION_CONFLICT` |
| current execution lease/contention | 409 | `TOOL_EXECUTION_IN_PROGRESS` |
| stale/non-owner execution generation | 409 | `TOOL_EXECUTION_FENCED` |
| logical ID/fingerprint conflict | 409 | `TOOL_PROVIDER_IDEMPOTENCY_CONFLICT` |
| `ticket_lookup` provider unavailable/timeout | 502 | `TOOL_PROVIDER_UNAVAILABLE` |
| `ticket_lookup` unknown/malformed provider response | 502 | `TOOL_PROVIDER_CONTRACT_INVALID` |
| provider request rejected with proof no write could be received | 502 | `TOOL_PROVIDER_REQUEST_FAILED` |
| terminal `ProviderTerminalFailureCode` | 502 | `TOOL_PROVIDER_FAILURE` plus sanitized `failure_code` |

The ticket-lookup provider matrix is therefore exact:
`provider_scope_denied -> 403/TOOL_RESOURCE_ACCESS_DENIED`,
`provider_resource_not_found -> 404/TOOL_TICKET_NOT_FOUND`,
`provider_unavailable -> 502/TOOL_PROVIDER_UNAVAILABLE`, and
`provider_contract_invalid -> 502/TOOL_PROVIDER_CONTRACT_INVALID`. A successful lookup is 200 and
must contain the exact allowlisted `TicketLookupResult`. FastAPI's default validation body is not the
M4 public contract; M4 routes normalize validation failures to the envelope above.

Write and reconciliation phases deliberately do not inherit the ticket-lookup 502 rows. A direct
`create_ticket` timeout, acknowledgement loss, unavailable transport or unknown/malformed response
when external receipt is possible returns `ExecutionIndeterminate` as HTTP 202 with lifecycle still
`executing`, immutable logical ID/fingerprint and observation
`indeterminate_external_outcome`. Even the deterministic `before_provider_receive` fault returns the
same non-terminal public shape; its proof of no receipt authorizes only the later provider-first safe
recovery decision, not a definitive failure.

`ReconcileExecution` maps `provider_observation_unavailable`, observation timeout and every
unknown/malformed observed provider outcome to `ReconciliationIndeterminate` HTTP 202. Provider
outcome not-found is the distinct `ProviderOutcomeNotFound` HTTP 202 projection. Neither changes the
lifecycle to `failed`, and neither grants a write retry. Only `found(failed(closed_code))` may finalize
`failed` and use `502/TOOL_PROVIDER_FAILURE`; only `found(succeeded(...))` may finalize `succeeded`.

## Workflow and lifecycle

The workflow therefore exposes the typed commands:

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
decision wins. The linearization point is the first database transaction to commit
`state=proposed AND revision=expected_revision`; tests assert one durable winner without assuming
approve or reject precedence. Every loser reads and returns the persisted winning decision/revision
as `AlreadyDecided`. Material edits are forbidden and must create a new proposal identity.

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

`request_fingerprint` is the `canonical-json-v1` digest of the complete provider intent:
`operation=create_ticket`, exact capability identity/version/digest, exact external-scope binding
identity/version/digest, target `reference_id`/resource kind/resource-identity digest/claims digest,
and normalized `{title, description}`. It excludes lease owner/generation and the logical execution
ID itself. The server computes and stores it with the proposal; acquisition, every retry and every
reconciliation request must load the same stored logical ID and fingerprint and may not recompute
them from client input.

`ReconcileExecution` handles both known indeterminate attempts and orphaned `executing` records
with no durable observation. It first reads provider outcome using the same logical identity. A
stale lease can be taken over atomically; stale owners cannot finalize after generation changes.
Provider `not found` is non-terminal and permits safe retry with the same key. If a write retry is
needed, the current `ExecutionAuthorizer`, exact capability/scope/policy compatibility and current
Workspace/resource authorization all run again. Observation authority alone never grants write
authority.

All lease comparisons use PostgreSQL `transaction_timestamp()` captured once per transaction; host
clocks cannot decide staleness. `lease_duration` is a bounded server configuration value. The typed
store transitions are:

- `acquire_execution(proposal_id, expected_revision, owner_id, lease_duration,
  authorized_binding_snapshot) -> AcquireApplied(lease) | ExecutionInProgress(current_lease) |
  ProposalNotExecutable(reason) | RevisionConflict(current_revision) | ProposalNotFound`. The CAS
  requires `state=approved AND revision=expected_revision`, database time before proposal expiry,
  exact stored logical ID/fingerprint and no existing execution. Applied changes state to `executing`,
  increments revision, creates generation `1`, owner and lease deadline, persists the binding snapshot
  and appends audit atomically.
- `takeover_stale_execution(proposal_id, expected_generation, recovery_owner, lease_duration) ->
  TakeoverApplied(new_lease) | ExecutionNotStale(current_lease) | ExecutionFenced(current_lease) |
  AlreadyFinalized(outcome) | ProposalNotFound`. The CAS requires `state=executing`, exact expected
  generation and `lease_expires_at < transaction_timestamp()`; Applied increments generation by
  exactly one and replaces owner/deadline atomically. A generation mismatch is fenced, not retried as
  the stale owner.
- `record_execution_observation(proposal_id, expected_generation, owner_id, observation) ->
  ObservationApplied(sequence) | ExecutionFenced(current_lease) | AlreadyFinalized(outcome) |
  ProposalNotFound`. Applied requires the current owner/generation and an unexpired lease and appends
  the sanitized observation/audit without changing lifecycle.
- `finalize_execution(proposal_id, expected_generation, owner_id, terminal_outcome) ->
  FinalizeApplied(projection) | ExecutionFenced(current_lease) | AlreadyFinalized(outcome) |
  ProposalNotFound`. Applied requires `state=executing`, current owner/generation and an unexpired
  lease, then persists exactly one `succeeded` or `failed` outcome plus audit atomically. Expired,
  superseded or non-owner callers are fenced and cannot win a conflicting finalization.

Reconciliation observes provider truth before deciding whether takeover is needed. A terminal
observation with a current foreign lease returns `ExecutionInProgress`; with a stale lease it takes
over using the observed generation, records the observation and finalizes. Provider not-found with a
stale lease may take over, but a write retry still reruns full side-effect reference verification,
current Workspace/resource authorization, `ExecutionAuthorizer` and exact compatibility. Reference
expiry/revocation or material mismatch permits only observation and forbids that retry.

The reference provider owns the authoritative external resource and idempotency ledger separately
from `ToolActionStore`. Provider success/rejection is reconciled into the Knora lifecycle; unknown
outcomes remain explicit and cannot be fabricated as success or failure.

## Provider interface and reference ledger

`SupportToolGateway` accepts only authorized provider-scope/resource values:

- `lookup_ticket(LookupTicketRequest(scope, resource)) -> TicketLookupResult`;
- `create_ticket(CreateTicketRequest(scope, target, title, description,
  logical_execution_id, request_fingerprint)) -> ProviderWriteOutcome`;
- `get_execution_outcome(ProviderOutcomeRequest(scope, logical_execution_id)) ->
  ProviderOutcomeObservation`.

`ProviderWriteOutcome` is terminal `succeeded(provider_ticket_reference)` or
`failed(ProviderTerminalFailureCode)`, where the closed failure enum is `target_not_found`,
`validation_rejected` or `policy_rejected`. `ProviderOutcomeObservation` is `found(outcome)`,
`provider_outcome_not_found`, or `provider_observation_unavailable`. Closed provider errors are
`provider_scope_denied`, `provider_resource_not_found`, `provider_idempotency_conflict`,
`provider_unavailable`, `provider_request_rejected`, `provider_outcome_indeterminate` and
`provider_contract_invalid`.
The terminal failure enum is stored in the provider ledger and projected into sanitized Knora audit;
the public execution envelope uses `provider_failure` plus that enum and HTTP 502. An unknown or
malformed provider failure maps to `provider_contract_invalid` for a direct response, or
`provider_observation_unavailable` while observing; it is never stored or projected as definitive
failure/success. Timeout/ack loss is indeterminate, never definitive failure.

The SQLite reference provider owns `provider_idempotency` keyed uniquely by logical execution ID and
containing request fingerprint plus immutable terminal outcome, and `provider_tickets` with a unique
logical execution ID. `create_ticket` uses one `BEGIN IMMEDIATE` transaction: an existing same-key,
same-fingerprint record replays its stored terminal outcome; a different fingerprint returns typed
conflict; a new record atomically commits terminal outcome and ticket (or terminal rejection). The
outcome is authoritative immediately after commit even if Knora never receives the acknowledgement.
Recreating the gateway with the same SQLite path proves provider state survives a Knora restart and
is independent of `ToolActionStore`.

Deterministic test-only fault modes live in the adapter/harness, never request input:

- `before_provider_receive`: no provider row is written, proving safe same-key retry after Knora
  persisted `executing`;
- `after_provider_commit_before_ack`: terminal provider rows commit, then the adapter returns typed
  indeterminate, proving reconciliation without duplicate effect;
- `definitive_failure`: a terminal failure outcome commits without a ticket;
- `observation_unavailable`: observation is indeterminate and distinct from authoritative not-found.

`get_execution_outcome` returning not-found means no ledger record currently exists; it does not
change Knora lifecycle to failed. A later authorized retry must reuse the exact logical ID and
fingerprint.

## PostgreSQL action store

#76 introduces `tool_proposals`, one unique `tool_proposal_decisions` row per decided proposal, and
append-only `tool_action_audit_events`. Proposal material columns include every canonical intent and
provenance field named above, with unique logical execution ID and state/revision constraints. A
database immutability guard rejects updates to material columns. Decision CAS updates only lifecycle
state/revision and inserts the decision plus next ordered audit event in one transaction. Audit rows
have unique `(proposal_id, sequence)` and reject update/delete.

The #76 `ToolActionStore` interface is `create_proposal`, `read_proposal`,
`decide_proposal(expected_revision)` and `project_proposal`; it returns only typed applied,
already-decided, conflict or not-found outcomes. #77 adds the typed acquisition, observation and
finalization contracts above. #78 adds typed stale-lease takeover plus the observation-only binding
resolver. PostgreSQL holds only Knora workflow/audit state and the immutable authorized binding
snapshot; authoritative provider tickets and idempotency outcomes remain solely in SQLite, and no
provider adapter may write Knora tables directly.

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
