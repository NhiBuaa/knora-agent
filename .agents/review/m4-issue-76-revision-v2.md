## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the immutable write-proposal and human-decision path for `create_ticket` without performing
an external write. A caller can create a typed proposal whose human-readable action, target and
parameters are bound to the exact capability version, Workspace-to-external-scope binding, policy
provenance and integrity-protected resource reference that a human reviews. An authorized human can
approve or reject that exact proposal; model and system actors cannot approve.

The slice exposes typed proposal workflow transitions, Workspace-scoped proposal HTTP surfaces and
durable PostgreSQL projection/audit needed by later execution, while preserving the distinction
between authenticated Workspace principal, proposal actor, approval actor and execution authority.
It consumes the narrow typed `CapabilityResolver.resolve_for_proposal` seam and a fake resolver in
tests; it does not import #75's concrete registry or provider adapter and remains an independent
frontier slice.

## Acceptance criteria

- [ ] `create_ticket` is registered as a static, typed, versioned write capability.
- [ ] The typed proposal input contains only `capability_id`, opaque `target_reference`, `title` and
  `description`; title/description validation, normalization and `canonical-json-v1` digest semantics
  match the approved M4 design.
- [ ] Proposal creation records authenticated caller provenance and a typed proposal actor derived
  from trusted application `actor_context`, without conflating either with approval authority.
  Request schemas forbid client actor, authority, digest, provider ID and logical-execution-ID fields.
- [ ] Proposal and approval bind capability identity/version/digest, Workspace external-scope binding
  identity/version/digest, policy provenance bundle, verified integrity-protected resource reference,
  canonical parameters digest and one immutable server-generated logical execution identity.
- [ ] Material proposal fields are immutable; a material change creates a new proposal identity
  rather than editing an existing proposal. PostgreSQL guards material columns against update.
- [ ] Typed transitions exist for `ProposeWriteAction`, `ApproveProposal` and `RejectProposal`;
  proposal state is `proposed` then exactly one of `approved` or `rejected`.
- [ ] Only a current authorized human approval actor derived from trusted context can approve or
  reject. Model/system contexts and request-body actor spoofing cannot produce a human decision.
  Separation-of-duties is enforced only when the action policy explicitly requires it.
- [ ] Concurrent approve/reject attempts have one atomic compare-and-swap winner: the first
  transaction to commit against the expected proposed revision wins, and every loser returns the
  persisted winning decision/revision without assuming approve or reject precedence.
- [ ] `ToolActionStore` owns PostgreSQL proposal/decision persistence and ordered append-only audit.
  Audit reconstructs caller, proposal and decision actors plus exact capability, binding, policy,
  reference, parameter and logical-ID provenance. Decision and audit persist atomically.
- [ ] Persistence tests prove immutable material snapshots, exactly-one decision, append-only audit,
  read-back reconstruction, stale/expired projections and absence of provider persistence coupling.
- [ ] `CapabilityResolver.resolve_for_proposal` returns exact capability identity/version/digest and
  binding/reference requirements. #76 tests use a fake resolver and have no dependency on #75's
  concrete implementation; integration injects the accepted registry only before final acceptance.
- [ ] Workspace-scoped HTTP surfaces exist for proposal create/read/approve/reject under
  `/v1/workspaces/{workspace_id}/tool-proposals`; authentication and path-Workspace authorization
  precede proposal lookup.
- [ ] HTTP tests cover schema validation, trusted actor derivation, cross-Workspace denial, absent
  proposal, atomic decision conflict and safe 401/403/404/409/422 envelopes, with no provider write.
- [ ] Temporary execution-authority revocation can leave an otherwise valid proposal approved,
  while exact capability, binding or policy incompatibility produces a stale/non-executable
  projection requiring a new proposal and approval.
- [ ] Proposal expiry blocks starting a new execution but does not invalidate reconciliation of an
  execution that has already begun.
- [ ] No external provider write occurs in this slice.
- [ ] Existing M1–M3 authorization, provenance and regression behavior remains green.

## Blocked by

None — can start immediately and remains parallel with #75 through the typed resolver seam.
