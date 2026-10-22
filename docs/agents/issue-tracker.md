# Issue tracker: GitHub

GitHub Issues track requests and work status. Use the `gh` CLI for issue and PR operations.
Specifications and plans use the repository locations below.

## Conventions

- Infer the repository from `git remote -v` when running inside this checkout.
- Create one issue per vertical slice with `gh issue create --title "..." --body "..."`.
- Read an issue and its discussion with `gh issue view <number> --comments`.
- Apply or remove labels with `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Do not close or modify a parent issue while publishing child tickets.
- Use the `ready-for-agent` label only after its triage meaning has been approved.

## Issue and document ownership

Keep each fact with its existing owner and link to it from the work item:

| Source        | Owns                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------ |
| Issue         | Problem, goal, scope, acceptance criteria, dependencies and links needed to act                  |
| Plan          | Implementation steps and checks for complex work, under `docs/plans/`                            |
| Specification | Product behavior and requirements, under `docs/specs/`                                           |
| Design / ADR  | Lasting design under `docs/design/` where appropriate; architectural decisions under `docs/adr/` |
| PR            | Implementation diff, verification/CI evidence, review and remaining risks                        |

Keep the Issue body short enough to identify the task and its completion criteria. A small,
clear task can keep a short plan in the Issue. For complex work or work spanning sessions,
link an existing suitable plan or create one under `docs/plans/`; name it for its purpose,
with an Issue number only as an optional suffix. Link existing designs and ADRs instead of
restating their decisions. Keep progress and next steps in the Issue/PR, outside architecture
documents or a separate status ledger.

Read linked sources as needed for the task. Start with the Issue summary and relevant plan,
then inspect discussion/history when needed to resolve approval, conflicts or decision rationale.
Summarize and link; do not copy entire plans, decisions or verification logs between surfaces.

### Approved plan revision and resumption

For a repository plan approved by the user, record its path, full commit SHA and a link or
unambiguous reference to the user's approval in the Issue/PR. The reference must identify
which revision and scope were approved; a newer file or commit does not inherit approval.
For a short plan in an Issue, identify the approved text and approval comment/reference there.
If approval exists only in a conversation, identify that conversation and the approved version
honestly; do not invent a GitHub approval URL or retroactive commit SHA.

- Before implementation or after interruption, identify the task and approved revision, compare
  it with the current plan, and verify the assigned branch/worktree and unfinished steps from
  current Git and Issue/PR evidence. Follow the applicable worktree/ownership rules before editing.
- Changes to scope, acceptance criteria, architecture or safety boundaries need user approval
  for that delta. Continue independent work already authorized; the latest draft is not authority.
- Typo, link or presentation corrections that preserve meaning need no renewed approval.
  Retain the approved-revision reference and describe the harmless delta in the normal diff/report.
  Small, safe corrections within approved scope follow [selective closeout](#selective-closeout).
- If approval or its target revision cannot be established, inspect read-only and ask for the
  specific missing approval/reference before dependent edits. A handoff or agent claim alone
  cannot supply missing user authorization.

Apply this prospectively. Preserve existing approvals, commit-pinned links and historical evidence;
do not rewrite old approvals or bulk-migrate active Issues/plans to satisfy this guidance.

## Blocking edges

Use GitHub native issue dependencies when the repository supports them. Add a blocking edge with:

```text
gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by \
  -F issue_id=<blocker-database-id>
```

The database id comes from `gh api repos/<owner>/<repo>/issues/<number> --jq .id`. If native
dependencies are unavailable, put `Blocked by: #<number>` in the child issue body.

An issue is on the **frontier** when it is open, unassigned, and all blockers are closed.

## Pull requests

Pull requests are implementation and review artifacts. Keep requests and concise completion
criteria in Issues, with complex plans linked as above. Use the existing
[PR template](../../.github/pull_request_template.md) and
[Verification Contract](../runbooks/ci.md#verification-contract) for evidence and status claims.

## Selective closeout

At normal Issue/PR closeout, consider only verified, reusable findings; none is a valid outcome.

- Check code/tests or an accepted decision and link the source Issue/PR/comment or commit.
  Keep proposed, implemented, accepted, merged and deployed states distinct.
- Reuse the existing owner: `CONTEXT.md` for vocabulary, `docs/adr/` for accepted decisions,
  `docs/standards/` for invariants, the relevant runbook for operational pitfalls, and
  `AGENTS.md` for agent routing. Prefer a regression test for executable behavior.
  Link existing knowledge instead of copying it; no new skill, hook or knowledge store is needed.
- Apply small, safe corrections within the already approved scope without asking again.
  Include them in the normal diff and completion report.
- Propose out-of-scope policy, architecture or knowledge-authority changes for approval before
  applying them; do not block unrelated approved completion. This does not authorize publishing,
  infrastructure/provider activation, paid calls, deployment or permission changes.
- Keep progress in the Issue/PR. Preserve historical evidence and untracked files.
  Memory and old notes aid retrieval; verify them before relying on them.

Report briefly: no reusable finding, updated owner + evidence, or an out-of-scope proposal.

## Publishing contract

When a workflow says to publish to the issue tracker, create a GitHub issue and read it back before
reporting success. Partial publication must return the created issue references and must not retry
in a way that creates duplicates.
