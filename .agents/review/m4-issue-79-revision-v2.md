# Issue #79 contract revision 2 — external-review corrections

This revision supersedes `.agents/review/m4-issue-79-revision-v1.md`. All v1 obligations remain
normative except where the following stricter rules replace them.

## Frontier and source authority

The authoritative frontier evidence is `.agents/review/m4-issue-79-frontier-baseline-v2.json`.
It binds accepted runs and integrated commits for #75–#78, merged PRs #80–#83, closed blocker
state, integration reconciliation commit `536107394eee73e28b8d8df22e31c64500974787`, shared governance
checkpoint `5af5c5c914ea904fe1e14de1acff859113d53244`, and unchanged `main` at
`6312c4c4230032aa92ca5915803fcfaf564354fa`. The exact #79 source base is `5af5c5c`.

## Ticket-review phase is not guide approval

This revision and its packet are ticket-review artifacts only. No manual guide exists yet. Their
pre-guide sentinel cannot satisfy external guide review, human guide approval, guide lock, manual
execution, or acceptance. Those gates require a later guide with its own revision and digest.

## Closed executable matrices

The worker must load independent immutable fixtures—not production enums/serializers—for every M4
public outcome. Each row specifies HTTP status, exact recursive response key set/value domain,
forbidden fields, durable before/after state, and provider lookup/admission/write/effect counts.
Coverage includes all lookup success and provider errors; proposal create/read/approve/reject,
already-decided, stale/revision/expiry/not-found/validation outcomes; execution success, each
closed rejection, indeterminate/in-progress/fenced/idempotency conflict and every authorization or
compatibility denial; reconciliation success, `target_not_found`, `validation_rejected`,
`policy_rejected`, unavailable, timeout, malformed, not-found, in-progress and fenced outcomes.
Each closed provider rejection is a distinct restart-stable SQLite row, creates no provider ticket
or effect, and finalizes field-for-field to the approved Knora 502 projection.

## Exact-SHA and append-only sequence

1. Commit implementation and harness changes; call that immutable commit `tested_subject_sha`.
2. Verify unchanged tracked content at `tested_subject_sha` and generate deterministic evidence
   that embeds that SHA, locked guide digest, environment/command identities and node inventory.
3. Commit only evidence as `evidence_publication_commit`, proving its diff from tested subject is
   evidence-only. Append the candidate Evaluation in a later evidence-only commit.
4. Human approval appends a separate PASSED record; it never rewrites the candidate record.
5. Every evidence-only descendant is classified through selective invalidation. Any production,
   test, fixture, command, dependency, configuration, roadmap or release-ledger change invalidates
   the affected acceptance and requires rerun on a new tested subject.

The locked guide must include a dedicated lifecycle case proving pre-execution guide digest
approval, immutable guide bytes, Evaluation-history before/after digests, append-only candidate and
approval records, unchanged prior records, exact subject/evidence heads, technical verdict and
explicit human approval state.

## Complete regression accounting

Use `KNORA_DATABASE_URL` consistently. Every PostgreSQL/Alembic record includes sanitized effective
host `127.0.0.1`, database `knora`, invocation CWD, pinned interpreter and exit. Final pytest
evidence inventories collected, passed, failed, skipped and xfailed node identities. The three
pre-existing locked PDF baseline skips are explicitly classified; no new skip/xfail is allowed and
every required M1–M3 node must execute successfully. The root-CWD Alembic regression must pass.

## Final-review boundary

#79 may produce only a non-binding final-review readiness checklist/template. It must not create,
pin, validate or invoke the actual fixed-point descriptor. Only the leader may do that after #79 is
accepted, integrated and closed and after freshly proving `main` and the final integration head.
The roadmap/release-ledger completion projection must be present before #79 guide execution;
changing it afterward selectively invalidates #79 acceptance.
