# Human-approved tool execution boundary

Status: accepted, 2026-08-22

Milestone 4 keeps authenticated Workspace authorization, proposal provenance, human approval and
current execution authority as separate concepts. A write proposal binds exact capability,
Workspace-to-external-scope and policy provenance; execution revalidates those bindings before
the side effect. External outcome truth and idempotency live at the typed provider boundary, so
crash recovery and reconciliation reuse one logical identity without trusting a possibly stale
Knora execution record or silently retargeting an approved action.

## Consequences

- An approval does not grant execution authority, and temporary authority revocation can block an
  approved proposal without mutating its immutable intent.
- Material capability, scope-binding or policy incompatibility makes a proposal non-executable and
  requires a new proposal and approval.
- A deterministic reference provider must own an independent external-state/idempotency ledger for
  release evidence; a fake adapter remains a unit-test adapter only.
