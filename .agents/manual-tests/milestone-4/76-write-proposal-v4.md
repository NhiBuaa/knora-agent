# Manual Test Guide: M4.2 write proposal v4

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #76 — immutable write proposal and human approval boundary
- Authoritative specification: GitHub Issue #76 and
  `docs/design/milestone-4-tools-human-approval.md` reviewed at
  `5ffb59d2bbc4175a40cda12e714851d6c1e83cb0`
- Guide revision: `m4-76-write-proposal-v4`
- Supersedes: locked v3 after child review v3 invalidated its accepted Evaluation
- Test-case source: `.agents/review/m4-issue-76-test-cases-v4.json`
- External review evidence: pending `.agents/review/m4-issue-76-guide-external-review-v4.json`
- Human approval evidence: pending `.agents/review/m4-issue-76-guide-approval-v4.json`
- Lock rule: this exact guide digest becomes immutable only after external `APPROVE` and explicit
  human approval; implementation remains blocked until then

## Prerequisites

- Execute only on the exact candidate commit recorded in the Evaluation and from a clean worktree.
- Run the exact PowerShell assignment
  `$env:KNORA_DATABASE_URL = "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora"`.
- Resolve Python as `D:\Developer\Projects\knora-agent\.venv\Scripts\python.exe`; Docker project
  `m4-integration` supplies PostgreSQL.
- Recreate database `knora` with the exact command from guide v3 before migration/full-suite runs;
  PostgreSQL suites run serially.
- Use deterministic trusted fixtures for two Workspace principals, human/model/system contexts,
  nested approval/execution policy semantics, a non-default proposal lifetime, clock,
  active/retiring/revoked ephemeral keys and trusted reference store. Never retain or record raw
  credentials, MAC/key bytes or provider IDs.
- Install an explicit counting `SupportToolGateway`/provider-write sentinel whose
  `create_ticket` operation increments a counter and fails the case. A reported zero is valid only
  when that exact sentinel is present in the executed composition.
- Core #76 workflow and unit tests depend only on `CapabilityResolver` and
  `ProposalTargetVerifier` protocols/fakes. The integration adapter and integration tests may and
  must consume the accepted #75 concrete `CapabilityRegistry` and `ReferenceVerifier`; no provider
  write, #77 execution or #78 reconciliation behavior enters this guide.
- Record exact commands/exit codes, sanitized responses, field-by-field PostgreSQL projections,
  audit/decision counts, sentinel identity/count, subject SHA and clean status.
- The candidate Evaluation must contain a unique run ID, this guide revision/digest, exact subject
  SHA, environment revision, every case observation/evidence reference, overall verdict and
  `human_approval` status. Append through `record_evaluation.py`; never rewrite v3 history.

## Locked Test Cases

### M4-76-TC-01: Policy provenance is deeply immutable and digest-consistent

- Purpose: close the authority gap where nested policy values can diverge from their approved
  digest.
- Steps:
  1. Construct policy provenance from caller-owned nested mappings/sequences containing approval,
     execution, separation-of-duties and proposal-lifetime semantics.
  2. Mutate the original containers and attempt top-level and nested mutation through every retained
     policy view before and after proposal creation.
  3. Reload the proposal and recompute canonical policy semantics/digest.
- Expected results:
  - Construction takes one deep immutable canonical snapshot and retains no caller-owned mutable
    container; direct and nested mutation is rejected or cannot affect the value.
  - Snapshot, digest and persisted semantics remain exactly consistent under every attempt.
  - Policy-selected proposal lifetime is present in the attested snapshot; proposal creation reads
    one internally consistent policy value.
- Evidence to capture: mutation matrix, canonical snapshot/digest comparison, persisted policy and
  expiry fields, zero-write sentinel.

### M4-76-TC-02: Input and m4r1 target-reference matrices fail before persistence

- Purpose: prevent spoofed authority, ambiguous parameters and unverified targets from becoming a
  proposal.
- Steps:
  1. Exercise absent/non-string/empty/over-limit/NUL/leading-trailing-whitespace title/description,
     canonical Unicode/LF equivalents and every forbidden actor/authority/digest/provider/logical-ID
     extra field.
  2. Exercise malformed syntax, tampered MAC, expired reference, unknown/revoked key,
     Workspace/capability/binding/resource mismatch and missing/mismatched trusted-store record.
  3. Inspect safe responses, proposal/decision/audit rows, resolver calls and write sentinel.
- Expected results:
  - Schema/parameter/extra-field/invalid reject-reason input is
    `422/TOOL_REQUEST_INVALID`; malformed syntax is
    `400/INVALID_TOOL_RESOURCE_REFERENCE`; authenticated integrity/scope/store mismatch is
    `403/TOOL_RESOURCE_ACCESS_DENIED` without existence leakage.
  - Every rejected target has zero proposal/decision/audit rows and sentinel count zero.
  - No raw provider/key/MAC/internal reference data appears in a response or evidence artifact.
- Evidence to capture: complete named matrix, safe envelopes, digest recomputation, zero row/write
  counters.

### M4-76-TC-03: Workspace authorization precedes proposal lookup

- Purpose: prevent cross-Workspace existence leakage or mutation.
- Steps:
  1. Exercise create/read/approve/reject without authentication and under the wrong Workspace.
  2. As an authorized principal, read and decide an absent proposal.
- Expected results:
  - Missing auth is `401/UNAUTHENTICATED`; Workspace denial is
    `403/WORKSPACE_ACCESS_DENIED` before scoped lookup.
  - Authorized absence is `404/TOOL_PROPOSAL_NOT_FOUND`.
  - Denied calls add no decision/audit row and leave the write sentinel at zero.
- Evidence to capture: route/status/error matrix, store ordering and row/write counters.

### M4-76-TC-04: Only authorized humans decide and reject reasons are closed

- Purpose: keep Workspace principal, proposal actor, approval actor and execution authority
  separate without inventing blanket separation of duties.
- Steps:
  1. Attempt approve/reject from model/system and an unauthorized human.
  2. Approve as an authorized human under no-SoD policy, including the same proposal actor identity;
     repeat under explicit SoD policy.
  3. Reject fresh proposals once per valid reason and submit one unknown reason.
- Expected results:
  - Forbidden actors receive `403/TOOL_APPROVAL_FORBIDDEN` with no decision row.
  - Authorized human succeeds when policy permits; explicit SoD denies only its configured case;
    approval never grants execution authority.
  - The four closed reasons persist exactly; an unknown reason fails 422 before persistence.
- Evidence to capture: actor/policy/reason matrix, decision/audit rows and sentinel count zero.

### M4-76-TC-05: Concurrent approve/reject has one durable CAS winner

- Purpose: prove atomic decision semantics without scheduler precedence.
- Steps:
  1. Release concurrent approve/reject commands against the same proposed revision and reload.
  2. Repeat without assuming which action wins, then retry both commands through HTTP.
- Expected results:
  - Exactly one CAS commits, revision increments once and one decision/audit row exists.
  - Every loser/repeat returns `409/TOOL_PROPOSAL_ALREADY_DECIDED` with the persisted winner.
  - No provider write occurs.
- Evidence to capture: concurrent results, HTTP envelopes, revision, row counts, audit order and
  sentinel count.

### M4-76-TC-06: PostgreSQL reconstructs immutable provenance and replacements

- Purpose: prove the durable store preserves the complete reviewed intent and never inherits a
  decision across material changes.
- Steps:
  1. Persist and decide a proposal, recreate the store/application, then compare every caller,
     proposal actor, approval actor, authority, capability, binding, policy snapshot/digest,
     reference, parameter, proposal/logical-ID, timestamp, revision and audit field.
  2. Attempt update of every material column and update/delete of decision/audit rows.
  3. Through trusted composition, independently change policy semantics, title and target reference
     and create replacement proposals using only public request fields.
- Expected results:
  - Field-by-field read-back and ordered audit exactly reconstruct the original proposal/decision.
  - Database guards reject every forbidden mutation.
  - Each material change creates new proposal and logical execution identities with no inherited
    approval; provider sentinel remains zero.
- Evidence to capture: reconstruction table, database rejection reasons, replacement identity table,
  audit sequence and sentinel count.

### M4-76-TC-07: Production policy expiry and durable executable projections

- Purpose: prove expiry is selected by attested policy through real production composition and
  distinguish temporary denial, material staleness and expiry without #77/#78 behavior.
- Steps:
  1. Use accepted #75 registry/reference composition with a trusted non-default lifetime and clock;
     create and approve a proposal, persist it, recreate the store/application and calculate expiry.
  2. Temporarily deny current execution authority and read the application/HTTP projection.
  3. Restore authority; independently change current capability, binding and policy provenance,
     restoring exact compatibility between observations; finally advance beyond expiry and reload.
- Expected results:
  - `expires_at` equals trusted creation time plus the policy-selected non-default lifetime; the
    lifetime is inside the exact policy snapshot/digest and there is no independent one-hour fallback.
  - Temporary denial leaves `approved`, `stale=false`, `executable=false` with
    `execution_not_authorized`; material mismatch keeps the decision but is stale/non-executable
    with the exact typed reason; expiry is non-executable with the typed expired reason.
  - Every projection is proven after PostgreSQL read-back; execution, reconciliation and provider
    write counters remain zero.
- Evidence to capture: composition dependency trace, policy snapshot/digest/expiry calculation,
  durable projection matrix, unchanged decision/audit values and zero counters.

### M4-76-TC-08: One canonical JSON authority, reconciled #75 seam and governed verification

- Purpose: eliminate duplicate canonical semantics and prove the accepted integration boundary
  with an observable no-write oracle.
- Steps:
  1. Inspect imports/diff and run canonical-json-v1 conformance tests for all capability, reference,
     policy, parameter and request-fingerprint values.
  2. Prove core #76 workflow/tests use narrow protocols/fakes while integration composition/tests
     use accepted #75 `CapabilityRegistry` and `ReferenceVerifier` without changing those protocols.
  3. With the explicit counting write sentinel installed, recreate/migrate the database, run focused
     M4.2 tests, full pytest, Ruff, Compose config, then recreate/migrate once more and inspect clean
     status.
- Expected results:
  - `knora.tools.contracts` is the single canonical-json-v1 implementation; no duplicate
    `proposal_contracts` authority remains and conformance output is identical across all consumers.
  - The reconciled #75 integration is exercised; #76 adds no provider write, #77 execution or #78
    reconciliation behavior.
  - All commands exit 0, M1–M3 regression stays green, worktree is clean and the recorded sentinel
    identity reports `create_ticket_write_count=0`.
- Evidence to capture: import/dependency inventory, canonical conformance results, exact
  invocations/exits/test totals/migration head, sentinel identity/count, diff and clean status.

Observations belong to
`.agents/manual-tests/milestone-4/76-write-proposal-v4.evaluations.jsonl`. Append a candidate record
with `human_approval: pending`; after explicit approval, append a separate approved record. This
guide becomes immutable only after its reviewed digest receives explicit human lock approval.
