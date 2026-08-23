# Manual Test Guide: M4.2 write proposal v1

## Metadata

- Feature: Milestone 4 — Tools and human approval
- Slice: Issue #76 — immutable write proposal and human approval boundary
- Authoritative specification: GitHub Issue #76 and
  `docs/design/milestone-4-tools-human-approval.md` reviewed at
  `01d329e1e9aa8c0f2f667ab9df318c62ba47d047`
- Guide revision: `m4-76-write-proposal-v1`
- External review evidence: `.agents/review/m4-issue-76-guide-external-review-v1.json`
- Human approval evidence: `.agents/review/m4-issue-76-guide-approval-v1.json`
- Lock rule: this exact guide digest becomes immutable only when both evidence records approve it;
  absence of either record means implementation remains blocked

## Prerequisites

- Execute only on the exact candidate commit recorded in the Evaluation; the worktree is clean.
- Docker Compose dependencies are healthy and the Knora PostgreSQL database is freshly recreated and
  migrated to Alembic head before persistence/concurrency or full verification.
- Use deterministic trusted fixtures for Workspace principals, human/model/system actor contexts,
  approval policy, clock, verified resource and the narrow fake `CapabilityResolver`. Fixtures contain
  no secrets and request bodies never supply actor/authority provenance.
- Use a counting provider gateway sentinel that fails the case if any external write is attempted.
- The implementation supplies dedicated tests under `backend/test/tools`,
  `backend/test/adapters/postgres` and `backend/test/adapters/http`.
- Record commands, exit codes, sanitized responses, database row/audit projections, exact subject SHA
  and clean status. Never record reference keys/MACs, raw provider IDs or credentials.

## Locked Test Cases

### M4-76-TC-01: Canonical immutable proposal derives trusted provenance

- Purpose: prove the server, not the request body, owns identity, provenance and approved intent.
- Steps:
  1. Create a proposal with an authorized Workspace principal, trusted proposal actor context, exact
     resource reference and valid title/description.
  2. Read it through the application and HTTP projections after a database reload.
  3. Inspect the fake resolver request/result and provider-write sentinel.
- Expected results:
  - Caller and proposal actor provenance come from trusted context and remain distinct.
  - The server stores normalized parameters, exact capability/binding/policy/reference provenance,
    one generated proposal ID/logical execution ID, canonical digest and policy expiry.
  - Projection/read-back matches the durable record and provider-write count is zero.
- Evidence to capture: sanitized create/read projections, provenance/digest comparison, resolver trace
  and zero-write assertion.

### M4-76-TC-02: Closed request schema and canonical parameter bounds

- Purpose: prevent spoofed authority and ambiguous material intent.
- Steps:
  1. Exercise absent, non-string, empty, over-limit, NUL and leading/trailing-whitespace title and
     description values plus canonical Unicode/LF equivalents.
  2. Add each forbidden caller/proposal/approval/execution actor, authority, digest, provider ID and
     logical execution ID field independently.
  3. Inspect HTTP result and proposal/store counts after each case.
- Expected results:
  - Invalid or extra fields return 422 before persistence.
  - Canonical-equivalent valid input yields the declared server-computed digest.
  - No client field overrides provenance, fingerprint or identity; gateway writes remain zero.
- Evidence to capture: complete validation matrix, canonical digest bytes/value and zero-store/write
  counts for rejected cases.

### M4-76-TC-03: Workspace authorization precedes proposal lookup

- Purpose: prevent cross-Workspace proposal existence leakage or mutation.
- Steps:
  1. Exercise proposal create/read/approve/reject without authentication and with wrong path Workspace
     or unauthorized principal.
  2. As an authorized principal, read and decide an absent proposal.
  3. Inspect store invocation ordering, decision/audit rows and public errors.
- Expected results:
  - Missing auth is 401 and Workspace/actor denial is non-leaking 403 before scoped lookup.
  - Authorized absence is 404.
  - Denied requests create no decision/audit row and never call a provider write.
- Evidence to capture: route/status matrix, store ordering/counters and database row counts.

### M4-76-TC-04: Only an authorized human can decide

- Purpose: separate proposal actor, approval actor and execution authority without inventing blanket
  separation of duties.
- Steps:
  1. Attempt approve and reject from model and system contexts.
  2. Approve as a current authorized human under a policy without separation of duties, including an
     otherwise-same proposal actor identity.
  3. Repeat same-actor approval under an explicit separation-of-duties policy.
- Expected results:
  - Model/system decisions are forbidden and create no decision row.
  - The authorized human wins when policy permits; approval still grants no execution authority.
  - Same-actor denial occurs only under the explicit policy and uses its typed reason.
- Evidence to capture: actor/policy outcome matrix, decision/audit rows and zero-write assertion.

### M4-76-TC-05: Concurrent approve/reject has one durable CAS winner

- Purpose: prove deterministic atomic decision semantics without scheduler precedence.
- Steps:
  1. Start approve and reject concurrently against the same proposed revision.
  2. Capture both typed results, then reload proposal, decision and audit state.
  3. Repeat so the evidence does not assume approve or reject must always win.
- Expected results:
  - Exactly one expected-revision CAS commits and increments revision once.
  - Every loser returns `AlreadyDecided` with the persisted winner and revision.
  - One immutable decision row and one ordered decision audit event exist; provider writes remain zero.
- Evidence to capture: concurrent results, committed revision, decision/audit row counts and sequence.

### M4-76-TC-06: Material fields and audit are immutable

- Purpose: ensure the human decision stays bound to exact reviewed intent and provenance.
- Steps:
  1. Reload a decided proposal and reconstruct all caller/actor/capability/binding/policy/reference/
     parameter/logical-ID provenance from projection plus audit.
  2. Attempt update of every material proposal field and update/delete of audit rows.
  3. Submit a materially changed title, target or policy snapshot as a replacement proposal.
- Expected results:
  - Read-back reconstruction matches the original canonical digest and decision.
  - Database guards reject every material/audit mutation.
  - Replacement has new proposal/logical IDs and no inherited approval.
- Evidence to capture: reconstruction table, database rejection reasons, ordered audit and replacement
  identities.

### M4-76-TC-07: Temporary denial, stale mismatch and expiry stay distinct

- Purpose: prevent silent reuse of approval under new authority/binding/policy semantics.
- Steps:
  1. Temporarily revoke execution authority for an approved proposal.
  2. Independently change current capability, external binding and policy identity/version/digest.
  3. Advance the deterministic clock beyond proposal expiry and inspect lifecycle/projection each time.
- Expected results:
  - Temporary authority denial leaves lifecycle `approved`, non-stale and non-executable for now.
  - Each material mismatch projects its exact stale reason and requires a new proposal/approval.
  - Expiry blocks a new execution; none of these observations mutates material fields or writes to the
    provider.
- Evidence to capture: lifecycle/executable/reason matrix, unchanged material digest and zero-write
  assertion.

### M4-76-TC-08: Narrow resolver, no provider write and full regression

- Purpose: prove #76 remains independent from #75 and introduces proposal/decision behavior only.
- Steps:
  1. Run all dedicated M4.2 tests, then the full repository pytest suite.
  2. Run Ruff, `docker compose config --quiet` and `alembic upgrade head` on a freshly recreated
     database.
  3. Inspect imports/dependencies, exact candidate diff and final worktree status.
- Expected results:
  - All commands are green and the worktree is clean.
  - Production code consumes only the `CapabilityResolver` protocol; tests use its fake and do not
    import #75 concrete registry/provider code.
  - No `SupportToolGateway.create_ticket` or other external write occurs; M1–M3 behavior remains green.
- Evidence to capture: command/exit summaries, migration head, dependency/diff inventory, provider
  write sentinel and clean status.

Observations append to
`.agents/manual-tests/milestone-4/76-write-proposal-v1.evaluations.jsonl`. The guide content becomes
immutable when the exact digest is externally reviewed and explicitly approved by the human.
