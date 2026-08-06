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

The completed product slice is
[Milestone 1 — Cited RAG](docs/specs/done/milestone-1-cited-rag.md). The active Milestone 2
specification and design ledger is [GitHub Issue #14](https://github.com/NhiBuaa/knora-agent/issues/14).

## Governed workflows

The following workflows are active for governed delivery: `feature-delivery`, `grill-with-docs`,
`grilling`, `domain-modeling`, `handoff`, `codebase-design`, `to-tickets`,
`manual-acceptance`, `implement`, `code-review`, and `session-continuity`.

Do not install, activate, trust, or grant permissions to additional skills without explicit user
authorization.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check .
docker compose config --quiet
```
