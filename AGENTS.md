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

Completed product slices are [Milestone 1 — Cited RAG](docs/specs/done/milestone-1-cited-rag.md),
[Milestone 2 — Production-shaped ingestion](docs/specs/done/milestone-2-production-ingestion.md),
Milestone 3 (accepted through [Issue #48](https://github.com/NhiBuaa/knora-agent/issues/48) and
[PR #73](https://github.com/NhiBuaa/knora-agent/pull/73)), and Milestone 4 (accepted through
[Issue #74](https://github.com/NhiBuaa/knora-agent/issues/74) and
[PR #84](https://github.com/NhiBuaa/knora-agent/pull/84)). Milestone 2's closed specification
and design ledger is [GitHub Issue #14](https://github.com/NhiBuaa/knora-agent/issues/14); its
accepted release gate is [GitHub Issue #21](https://github.com/NhiBuaa/knora-agent/issues/21).

The behavior-preserving `PostgresIngestionJobStore` decomposition is complete through
[Issue #85](https://github.com/NhiBuaa/knora-agent/issues/85) and
[PR #86](https://github.com/NhiBuaa/knora-agent/pull/86). Its compatible public facade remains at
`knora.adapters.postgres.ingestion_job_store`; private collaborators are implementation details.

## Skill policy

The canonical skill source is `C:/Users/NhiBuaa/.codex/skills`.
Select skills from the current session's catalog and read their `SKILL.md` before use.
Verify that the selected skill exists under this source; discover the current inventory rather
than assuming a skill is installed because an older document mentions it.

Use the installed skills according to their actual scope:

- `using-superpowers` for selecting the workflow at the start of work.
- `brainstorming` for requirements, design, architecture and unresolved domain decisions.
- `writing-plans` for approved implementation plans; `executing-plans` for executing them.
- `test-driven-development` for behavior changes; `systematic-debugging` for diagnosis.
- `using-git-worktrees` for isolated work under the repository's worktree policy.
- `subagent-driven-development` and `dispatching-parallel-agents` for delegated work when
  authorized and appropriate to their scope.
- `requesting-code-review` and `receiving-code-review` for review and handling findings.
- `verification-before-completion` for evidence before completion claims;
  `finishing-a-development-branch` for the user's integration choice.
- `research` for primary-source investigation saved as cited Markdown.
- `diagram-design` for standalone diagrams; `writing-skills` for authorized skill authoring.

Repository domain, issue-tracker, acceptance and Git rules apply throughout these workflows.
Record confirmed domain decisions in `CONTEXT.md` and relevant ADRs. Record session progress and
next steps in repository documents when continuity is needed. These tasks do not require a
separate skill. For Milestone 5, also follow
[the M5 runbook](.agents/workflows/m5-codex-skills-workflow.md).

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

## Frontend formatting

- For every change to maintained files under `frontend/`, run `npm --prefix frontend run format`
  before completing the change, then run `npm --prefix frontend run format:check`.
- Do not hand-compress JSX, TypeScript, or object literals to save lines. Keep markup, props,
  chained expressions, and nested braces readable under the checked-in Prettier configuration.
- Do not edit `frontend/generated/knora-openapi.ts` manually. Regenerate it with the repository
  exporter and verify it with `python scripts/export_openapi.py --check`.
- The GitHub Actions `Prettier format check` status from the `Frontend formatting` workflow is
  required for every update to `main`; do not bypass a failing or missing result.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check .
docker compose config --quiet
```
