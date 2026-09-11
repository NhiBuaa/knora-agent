# Knora repository guidance

Before changing the repository, read:

- [Current World Model](CONTEXT.md) for canonical concepts and relationships.
- [Domain documentation guide](docs/agents/domain.md) for domain-document routing.
- [GitHub issue tracker guide](docs/agents/issue-tracker.md) before reading or publishing work items.
- [Architecture Standard](docs/standards/architecture.md) for normative system boundaries and safety rules.
- [Milestone 1 Module Seams](docs/design/milestone-1-module-seams.md) for approved interfaces and
  legacy directory ownership.
- [Milestone 2 Module Seams](docs/design/milestone-2-module-seams.md) for production-ingestion
  interfaces and target directory ownership.

Completed product slices are [Milestone 1 — Cited RAG](docs/specs/done/milestone-1-cited-rag.md)
and [Milestone 2 — Production-shaped ingestion](docs/specs/done/milestone-2-production-ingestion.md).
Milestone 2's closed specification and design ledger is
[GitHub Issue #14](https://github.com/NhiBuaa/knora-agent/issues/14); its accepted release gate is
[GitHub Issue #21](https://github.com/NhiBuaa/knora-agent/issues/21).

## Governed workflows

The following workflows are active for governed delivery: `feature-delivery`, `grill-with-docs`,
`grilling`, `domain-modeling`, `handoff`, `codebase-design`, `to-tickets`,
`manual-acceptance`, `implement`, `code-review`, and `session-continuity`.

Do not install, activate, trust, or grant permissions to additional skills without explicit user
authorization.

## Worktree location policy

The sole container for every future non-primary Git worktree is
`C:\Developer\Projects\knora-agent-worktree`.

- Create each worktree as a direct child of that container, for example
  `C:\Developer\Projects\knora-agent-worktree\issue-<number>-<slug>`.
- Before creating one, verify that the container exists and that the proposed child path is unused.
- A branch is a Git ref, not a directory; use one unique branch per isolated worktree, and bind it
  to a path inside the canonical container.
- Do not create sibling worktree paths such as
  `C:\Developer\Projects\knora-agent-worktree-issue-<number>-<slug>`, nor use any other
  directory unless the user explicitly changes this policy.
- Before removing a worktree, verify it is clean and obtain an explicit disposition for its branch;
  never delete or prune a branch merely because its worktree is being removed.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check .
docker compose config --quiet
```
