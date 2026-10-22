# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- Infer the repository from `git remote -v` when running inside this checkout.
- Create one issue per vertical slice with `gh issue create --title "..." --body "..."`.
- Read an issue and its discussion with `gh issue view <number> --comments`.
- Apply or remove labels with `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Do not close or modify a parent issue while publishing child tickets.
- Use the `ready-for-agent` label only after its triage meaning has been approved.

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

Pull requests are not treated as incoming feature requests. Issues are the request and planning
surface; pull requests are implementation and review artifacts.

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

