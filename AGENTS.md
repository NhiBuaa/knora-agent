# Knora repository guidance

Before changing the repository, read:

- [Current World Model](CONTEXT.md) for canonical concepts and relationships.
- [Domain documentation guide](docs/agents/domain.md) for domain-document routing.
- [GitHub issue tracker guide](docs/agents/issue-tracker.md) before reading or publishing work items.
- [Architecture Standard](docs/standards/architecture.md) for normative system boundaries and safety rules.
- [Milestone 1 Module Seams](docs/design/milestone-1-module-seams.md) for approved interfaces and
  target directory ownership.

The approved product slice is [Milestone 1 — Cited RAG](docs/specs/milestone-1-cited-rag.md).

## Governed workflows

The following workflows are Active for Milestone 1: `feature-delivery`, `grill-with-docs`,
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
