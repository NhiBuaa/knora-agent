# Manual Test Guide: Bounded Worker-Coordination Verification Baseline

## Metadata

- Status: Approved and locked
- Feature: Issue #17 — PostgreSQL worker coordination lifecycle
- Slice: GitHub issue #25 — Bounded worker-coordination verification baseline
- Authoritative specification: https://github.com/NhiBuaa/knora-agent/issues/17
- Guide revision: `issue-25-v1`
- Approved by: Nhi (explicit human approval in Codex task)
- Approved at: 2026-08-09T09:58:33+07:00

## Prerequisites

- Environment: local checkout with the repository virtual environment available and Docker Compose
  installed; PostgreSQL-dependent tests may use the repository's documented test-service setup.
- Data and state: the pre-Issue-#17 production-code baseline. Existing approved documentation
  changes do not count as worker-coordination implementation.
- Repository identity: capture the exact commit SHA, branch and concise dirty-state summary. TC-02
  and TC-03 must use the same code state. Any difference must be identified and justified; a
  difference that could affect results invalidates the repeatability proof.
- Runtime identity: capture the Python and pytest versions and the non-secret identity of any
  PostgreSQL/test-service setup used by the gate.
- Configuration: every diagnostic or regression command has an explicit wall-time bound and emits
  enough progress or timeout evidence to distinguish completion, failure and timeout.
- Investigation bound: before TC-01 starts, declare a ticket-level wall-time budget, maximum number
  of diagnostic iterations or equivalent fixed bound. Do not extend it ad hoc after a timeout.
- Service bound: if PostgreSQL is required, document its exact startup/readiness prerequisite and
  apply an explicit wall-time bound to readiness as well as to pytest. Reuse the same prerequisite
  in TC-03.
- Observability: retain command, elapsed time, exit status, last reported test or phase, and relevant
  timeout diagnostics. Classify each command as `PASS`, `FAIL`, `TIMEOUT` or, for service setup,
  `SERVICE_UNAVAILABLE`; only a zero-failure successful test exit is `PASS`. Do not record secrets,
  connection credentials or raw sensitive input.

## Locked Test Cases

### TC-01: Bound and diagnose the repository full-suite command

- Purpose: establish reproducible evidence for the pre-existing full-`pytest` hang without allowing
  the investigation itself to block Issue #17 indefinitely.
- Steps:
  1. Record the fixed ticket-level investigation budget before the first diagnostic run.
  2. Run the repository's canonical full `pytest` command under a declared external timeout.
  3. Enable bounded progress and diagnostics sufficient to expose the last test, collection phase,
     hook, plugin or external-service wait when feasible.
  4. Stop root-cause investigation when the ticket-level budget is exhausted. Record
     `bounded inconclusive` and proceed to the TC-02 fallback gate.
  5. Apply a fix only if reproducible evidence proves a narrowly scoped verification or
     test-infrastructure defect that does not change production behavior or worker semantics. If a
     product/runtime change is required, document the cause and use the fallback gate where
     possible or create a separate follow-up.
  6. Record every command, timeout limit, elapsed time, exit status and diagnostic endpoint.
- Expected results:
  - The command completes or is forcibly terminated at the declared bound; it never waits without a
    limit.
  - Evidence identifies the hanging component when feasible, or records the narrowest reproducible
    boundary and remaining uncertainty.
  - A diagnosed cause is fixed only inside the narrow test-infrastructure boundary above. Otherwise
    it is documented without opportunistic production changes.
  - When the fixed investigation budget is exhausted without proof, investigation stops and the
    result is `bounded inconclusive`; Ticket #25 continues through TC-02.
- Evidence to capture:
  - Declared ticket-level budget, exact commands and per-command timeouts, baseline repository and
    runtime identity, elapsed times, classifications, last progress output, diagnostic traces and
    root-cause conclusion or bounded inconclusive result.

### TC-02: Establish an accepted Issue #17 pytest regression gate

- Purpose: satisfy Ticket #25's bounded exit criterion even if the full-suite root cause cannot be
  resolved within the investigation budget.
- Steps:
  1. If TC-01 produces a verified fix, rerun the bounded canonical suite and record the result.
  2. Otherwise, select the smallest known-good pytest commands that cover the application and
     PostgreSQL surfaces Issue #17 will change.
  3. If PostgreSQL is required, start it and prove readiness using the documented bounded service
     prerequisite before pytest begins.
  4. Run every selected command under an explicit timeout and document what each subset actually
     covers and omits. Record planned Issue #17 seams with no existing coverage as gaps; do not infer
     coverage from adjacent passing tests and do not add future coordination tests merely to fill a
     Ticket #25 gap.
- Expected results:
  - One accepted exit path is present: either a reproducibly bounded full suite after a verified
    fix, or bounded known-good application and PostgreSQL subsets.
  - Every command admitted to the accepted gate is `PASS`: it exits successfully with zero test
    failures. `FAIL`, `TIMEOUT` and `SERVICE_UNAVAILABLE` are non-passing diagnostic evidence and are
    never described as known-good gate commands.
  - The fallback gate covers the existing application and PostgreSQL surfaces relevant to Issue #17
    and reports exclusions and coverage gaps honestly.
  - Service setup failure, pytest assertion failure and pytest timeout are distinct outcomes; no
    setup or test command can hang indefinitely.
- Evidence to capture:
  - Gate command inventory, baseline identity, bounded service prerequisite, per-command timeout,
    actual coverage rationale, gaps and omissions, elapsed time and classification.

### TC-03: Prove the selected regression gate is repeatable and bounded

- Purpose: ensure later Issue #17 slices have a stable comparison signal rather than a one-off
  diagnostic success.
- Steps:
  1. Verify the commit, branch and dirty-state summary still match the TC-02 code state.
  2. Recreate or reuse the same bounded PostgreSQL/service prerequisite when applicable.
  3. Run the exact accepted gate command inventory from TC-02 again.
  4. Compare timeout behavior, classifications and collected/passed test totals with the first run.
- Expected results:
  - Both runs terminate within their declared bounds.
  - Both runs are `PASS` and use the same code state and gate command inventory.
  - Collected and passed test totals match exactly when deterministic. Different but compatible
    totals are accepted only when the legitimate source of variability is documented and shown not
    to weaken coverage.
  - Any service prerequisite is explicit, bounded and reused; service failures remain
    distinguishable from pytest failures and timeouts.
- Evidence to capture:
  - Both run records, repository identity comparison, command-inventory comparison, exact test
    totals, any justified variability and bounded service prerequisite/result.

### TC-04: Preserve repository static and Compose validation

- Purpose: retain the repository's non-pytest planning and implementation checks alongside the new
  bounded regression gate.
- Steps:
  1. Run `.\.venv\Scripts\ruff check .` from the repository root.
  2. Run `docker compose config --quiet` from the repository root.
- Expected results:
  - Ruff exits successfully with no findings.
  - Docker Compose configuration validation exits successfully.
  - These checks are recorded as complementary validation, not substitutes for TC-02 and TC-03.
- Evidence to capture:
  - Exact commands, exit statuses and concise output.

## Canonical Exit Conditions

Ticket #25 passes only through one of these paths:

- Path A: the canonical full `pytest` command is bounded, green and repeatable.
- Path B: the full-suite hang or root cause has bounded documented evidence; accepted application
  and PostgreSQL subsets are each bounded and green; and the complete fallback gate passes again
  for repeatability.

Both paths also require `ruff check .` and `docker compose config --quiet` to pass. Every JSONL
Evaluation record must include `guide_revision=issue-25-v1`, the baseline commit SHA, branch,
dirty-state summary, runtime identity and the selected path or current diagnostic status.

This guide becomes immutable after human approval. Create a new guide revision when the
specification or expected behavior changes. Store run observations separately as JSONL Evaluation
records.
