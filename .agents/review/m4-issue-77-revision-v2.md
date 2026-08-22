## Parent

#74 — Milestone 4 — Tools and human approval

## What to build

Deliver the approved `create_ticket` execution path end to end. Execution requires current Workspace,
resource, capability and execution authorization independently of human approval. PostgreSQL owns a
typed atomic execution lease and immutable authorized binding snapshot; the SQLite provider boundary
owns the authoritative idempotency outcome.

## Acceptance criteria

- [ ] `ExecuteApprovedProposal` starts only from an approved, exact-compatible and non-expired
  proposal after current Workspace/resource authorization and `ExecutionAuthorizer` approval.
- [ ] `ExternalResourceReferenceVerifier.verify_for_side_effect` fully verifies the exact approved
  `m4r1` reference/key/expiry/binding before acquisition. Denial produces zero provider calls.
- [ ] `request_fingerprint` is the server-computed `canonical-json-v1` digest of operation, exact
  capability, exact external-scope binding, target reference/resource claims and normalized
  `{title, description}`. It and the logical execution ID are immutable stored values, never client
  input.
- [ ] `ToolActionStore.acquire_execution` uses PostgreSQL transaction time and the approved typed CAS
  contract to atomically create generation 1, owner/deadline, `executing` state, audit and an
  immutable `AuthorizedExecutionBindingSnapshot` containing no raw provider ID.
- [ ] Concurrent acquisition returns exactly one `AcquireApplied`; every loser receives the typed
  current `ExecutionInProgress`, conflict or non-executable projection without a provider call.
- [ ] `record_execution_observation` and `finalize_execution` require current owner, generation and
  unexpired lease. Superseded, expired or non-owner callers receive `ExecutionFenced` and cannot
  finalize.
- [ ] The provider sees one immutable logical execution identity and the exact stored fingerprint.
  Same-key/same-fingerprint repeats replay; same-key/different-fingerprint returns idempotency
  conflict; concurrent calls create at most one logical side effect.
- [ ] Direct provider success finalizes `succeeded`. Closed terminal failures are only
  `target_not_found`, `validation_rejected` or `policy_rejected` and finalize `failed` with sanitized
  audit/HTTP 502 projection.
- [ ] Unknown/malformed provider failures are `provider_contract_invalid` or indeterminate and never
  become false definitive success/failure.
- [ ] Observation/reconciliation authority alone does not grant write retry authority.
- [ ] Execution actor, current authority evidence, lease generation, provider identity, immutable
  binding/fingerprint/logical ID, observation and outcome are reconstructable from append-only audit.
- [ ] Existing M1–M3 authorization, provenance and regression behavior remains green.

## Blocked by

- #75 — M4.1 — Read-only ticket lookup with pre-gateway authorization
- #76 — M4.2 — Immutable write proposal and human approval boundary
