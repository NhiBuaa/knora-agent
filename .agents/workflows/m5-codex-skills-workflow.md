# M5 Codex-Skills Workflow

Purpose: a local runbook for coordinating Milestone 5 with agents. This workflow uses only skills under C:/Users/NhiBuaa/.codex/skills and never uses feature-delivery.

## M5 scope

M5 is split into four independently testable slices:

1. M5.1 Backend projections and public contracts: document, ingestion, serving, chat, citation, refusal, and M4 tool lifecycle projections.
2. M5.2 User surface: document management, chat, loading/error/refusal states, and citation inspection.
3. M5.3 Operator surface: retrieval trace, evaluation, latency, token/cost, and failure views.
4. M5.4 Contract and end-to-end verification: authorization, backend ownership, missing-data semantics, and M1-M4 regression.

M5.1 locks public contracts first. M5.2 and M5.3 may run in parallel only after that checkpoint. M5.4 runs last.

## Allowed skills

Use only:

- using-superpowers
- brainstorming
- writing-plans
- using-git-worktrees
- subagent-driven-development
- test-driven-development
- dispatching-parallel-agents
- requesting-code-review
- receiving-code-review
- systematic-debugging
- verification-before-completion
- finishing-a-development-branch
- executing-plans

Do not use feature-delivery, or any skill outside the .codex/skills directory.

## Non-negotiable rules

- Do not implement before the design is explicitly approved.
- Backend remains the source of truth for domain state, evidence, decisions, authorization, and observations.
- The frontend must not decide retrieval, citation, refusal, authorization, approval, or execution outcomes.
- Missing data must be shown as unavailable or an observation failure; never fabricate it.
- Authorization is checked before resource lookup and side effects.
- Every behavior change follows test-driven RED -> GREEN -> REFACTOR.
- Every agent uses a separate worktree directly under C:/Developer/Projects/knora-agent-worktree.
- Do not merge, push, delete a branch, or remove a worktree without the user's explicit integration choice.

## State machine

DISCOVERY -> DESIGN_PROPOSED -> DESIGN_APPROVED -> PLAN_WRITTEN -> PLAN_APPROVED -> WORKTREES_READY -> SLICE_IMPLEMENTATION -> SLICE_REVIEWED -> INTEGRATION_VERIFIED -> FINAL_REVIEWED -> READY_TO_FINISH

A failed gate keeps the current state. Record the blocker and do not advance.

## Phase 0: discovery

Skill: using-superpowers.

The lead agent reads CONTEXT.md, AGENTS.md, docs/agents/domain.md, docs/agents/issue-tracker.md, docs/standards/architecture.md, both milestone seam documents, and docs/PROJECT_OVERVIEW.md.

Record:

- current main/HEAD and working-tree status;
- whether a frontend already exists;
- current API and projection seams;
- existing test seams;
- file ownership for each M5 slice.

Do not edit code.

## Phase 1: design

Skill: brainstorming.

Use the architectural path:

1. Ask clarifying questions one at a time.
2. Decide whether M5 needs further decomposition.
3. Present two or three approaches and trade-offs.
4. Define architecture, components, data flow, error handling, and testing.
5. Stop for explicit user approval.

The design must lock backend projections, public contracts, UI state semantics, operator authorization, M4 lifecycle exposure, and ownership boundaries.

Do not invoke implementation skills before approval.

## Phase 2: plans

Skill: writing-plans.

After design approval:

1. Write the design/spec artifact.
2. Self-review for placeholders, contradictions, scope creep, and ambiguity.
3. Write one plan per independent slice.

Suggested locations:

- docs/superpowers/plans/YYYY-MM-DD-m5-backend-projections.md
- docs/superpowers/plans/YYYY-MM-DD-m5-user-surface.md
- docs/superpowers/plans/YYYY-MM-DD-m5-operator-surface.md
- docs/superpowers/plans/YYYY-MM-DD-m5-e2e-verification.md

Every plan contains exact files, interfaces, dependencies, tests, RED/GREEN steps, acceptance criteria, commands, stop conditions, and commit boundaries.

Wait for explicit plan approval before worktree creation or implementation.

## Phase 3: worktrees

Skill: using-git-worktrees.

Verify C:/Developer/Projects/knora-agent-worktree exists and each proposed child path is unused.

Use one branch/worktree per slice:

- codex/m5-backend-projections
- codex/m5-user-surface
- codex/m5-operator-surface
- codex/m5-e2e-verification

Implement M5.1 first. Create or dispatch M5.2 and M5.3 only after its contract checkpoint passes.

## Phase 4: implementation

Skill: subagent-driven-development.

The lead is the controller. Each implementer receives one bounded task with:

- plan and task number;
- exact allowed files;
- completed dependencies;
- required test command;
- required RED, GREEN, self-review, and commit evidence;
- explicit stop conditions for ambiguity or scope conflict.

Each implementer must use test-driven-development, commit one coherent task, and report files, commands, outputs, review notes, commit SHA, and open questions.

The lead verifies the commit and diff independently; never trust a completion claim without VCS and test evidence.

## Phase 5: parallel agents

Skill: dispatching-parallel-agents.

Parallelize only when file ownership is disjoint, the public contract is locked, and each task has its own tests.

Allowed parallel work: M5.2 user surface and M5.3 operator surface.

Do not parallelize shared API schema, authorization boundaries, or contract definition.

## Phase 6: slice review

Skills: requesting-code-review and receiving-code-review.

Review each slice against its design and plan. Check:

- M5 exit criteria and M1-M4 invariants;
- authorization-before-lookup;
- backend ownership and no duplicated domain logic;
- citation/refusal and partial/final semantics;
- missing-data visibility;
- negative-case coverage;
- scope creep.

For findings, analyze before changing, classify the finding, fix only in the owning worktree, rerun scoped tests, and request a focused re-review.

## Phase 7: integration verification

Skills: systematic-debugging and verification-before-completion.

For any failure, reproduce it, identify the root cause, form one hypothesis, apply one minimal fix, and rerun the relevant test.

Run from the repository root:

    ./.venv/Scripts/python -m pytest
    ./.venv/Scripts/ruff check .
    docker compose config --quiet
    git diff --check

Also verify document/ingestion/serving projections, answer/refusal/citation behavior, partial/failure states, operator visibility, unauthorized and cross-Workspace cases, UI ownership, M4 projections, and M1-M4 regression.

No completion claim is allowed while a command or load-bearing review finding remains unresolved.

## Phase 8: final review and integration choice

Skills: requesting-code-review, verification-before-completion, and finishing-a-development-branch.

The final review receives the design, all plans, merge base, commit range, verification output, deferred decisions, and documentation changes.

After the final verification gate, present the exact integration choices:

1. Merge back to main locally
2. Push and create a Pull Request
3. Keep the branch as-is

Wait for the user's choice. Do not merge, push, or clean up automatically.

## Implementer prompt

You are implementing one bounded task from the approved M5 plan. Read repository guidance and the plan. Use test-driven-development: write the failing test, run it, implement the smallest change, run scoped tests, self-review, and commit. Modify only owned files. Do not redefine public contracts, authorization, ownership, citation/refusal semantics, or M4 approval authority. Stop on ambiguity. Report files, RED/GREEN output, review notes, commit SHA, and questions.

## Reviewer prompt

Review this M5 slice against the approved design and plan. Check M1-M4 invariants, authorization-before-lookup, backend ownership, missing-data semantics, citation/refusal correctness, test boundaries, and scope creep. Return severity, file/line evidence, required action, and verdict. Do not implement fixes.

## Completion record

When M5 is complete, save a local record containing slice and plan IDs, design and plan approvals, branch/worktree, implementation commits, review verdicts, verification outputs, deferred items, final PR/merge reference, and updated documentation paths.
