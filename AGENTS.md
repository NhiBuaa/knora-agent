# Knora repository guidance

Before changing the repository, read:

- [Current World Model](CONTEXT.md) for canonical concepts and relationships.
- [Domain documentation guide](docs/agents/domain.md) for domain-document routing.
- [GitHub issue tracker guide](docs/agents/issue-tracker.md) before reading or publishing work items.
- [Architecture Standard](docs/standards/architecture.md) for normative system boundaries and safety rules.
- If modifying module boundaries, directory ownership, or ingestion interfaces, read
  [Milestone 1 Module Seams](docs/design/milestone-1-module-seams.md) and
  [Milestone 2 Module Seams](docs/design/milestone-2-module-seams.md).

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

Use the current session's skill catalog to discover availability and the exact `SKILL.md`
location, including user, system and installed-plugin skills. Read that source before use;
do not restrict discovery to one directory or assume an old document proves installation.
Select any available, authorized skill that matches the task, following its applicability rules
and mandatory instructions; this repository does not maintain a fixed skill allowlist.
Repository-owned document paths and authority rules take precedence over generic skill
output-path defaults; do not create a parallel glossary, plan ledger or knowledge store.

Repository domain, issue-tracker, acceptance and Git rules apply throughout these workflows.
Record confirmed domain vocabulary in `CONTEXT.md` and architectural decisions in relevant ADRs.
Keep progress and next steps in the relevant Issue/PR, not a competing session-state document.
At closeout, follow [selective learning](docs/agents/issue-tracker.md#selective-closeout).
These tasks do not require a separate skill. For Milestone 5, also follow
[the M5 runbook](.agents/workflows/production-projections-user-operator-surfaces-verification-runbook.md).

Using an available, authorized skill does not require separate approval for each invocation.
Installing or trusting a new skill, enabling an unauthorized skill, or changing permissions requires
explicit user authorization. Skill selection does not authorize publishing, merging or deployment.

For skill evaluation, suspected stale/ineffective guidance, or a changed skill/model/runbook,
follow [Skill Evals](docs/agents/skill-evals.md); keep run evidence and decisions in the Issue/PR.

## Specification and plan locations

Store specification documents in `docs/specs/` and implementation plans in `docs/plans/`;
completed specifications remain in `docs/specs/done/`. These repository paths override
Skill output-path defaults, including those of `brainstorming` and `writing-plans`.
Keep technical decisions in their existing ADR/design owners and progress in the Issue/PR.
For Issue summaries, linked plans, approved revisions and resuming work, follow
[Issue and document ownership](docs/agents/issue-tracker.md#issue-and-document-ownership).
When relocating documents, update current links while preserving commit-pinned URLs,
frozen patches and approval records as historical evidence.

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

## Code formatting and generation

- For maintained files, run the formatter and then its check before completing changes:
  - Frontend: `npm --prefix frontend run format` then `npm --prefix frontend run format:check`.
  - Python: `python -m ruff format .` then `python -m ruff format --check .` and `python -m ruff check .`.
  - Shared files: `npm --prefix frontend run format:shared` then `npm --prefix frontend run format:shared:check`.
  - Detailed scopes, exclusions, and Java Spotless commands are in [Formatting scope](docs/runbooks/ci.md#formatting-scope).
- Do not hand-compress JSX, TypeScript, or object literals to save lines. Keep code readable under the checked-in Prettier configuration.
- Do not edit `frontend/generated/knora-openapi.ts` manually; regenerate with the repository exporter and verify with `python scripts/export_openapi.py --check`.
- Formatting runs inside component jobs in the unified `CI` workflow. `CI required` is mandatory for every update to `main`; do not bypass a failing or missing result.

## Docker Compose policy

The repository maintains at most two operational Compose sources: `docker-compose.yml` and
`docker-compose.dev.yml`. Each entry point is independent (no base-plus-override composition).
This rule applies across the repository, including nested fixtures, generated files, and Compose
`include` or `extends` directives; introducing any third operational Compose source requires an
explicit approved exception. Test topologies use capability profiles (`retrieval-test`,
`retrieval-http-test`, `password-reset-test`) and launchers must target explicit services rather
than starting unselected graphs. Daily development databases and volumes must never be used as
automated test or QA fixtures. Route launcher, runtime environment, and cleanup procedures to
[Agent environment](docs/runbooks/agent-environment.md) and verify limits using the Compose
inventory test (`backend/test/config/test_compose_inventory.py`).

## Verification

For every code change and before a completion claim, follow the
[Verification Contract](docs/runbooks/ci.md#verification-contract): select checks for the changed
behavior, run and inspect them, and report evidence and unverified scope in the Issue/PR.
Use `verification-before-completion` when available in the current catalog; if unavailable,
report that limitation and follow the repository contract directly.

For browser startup, health/ownership checks, UI control, runtime evidence or cleanup, read
[Agent environment](docs/runbooks/agent-environment.md) and its Feature Map before acting.
