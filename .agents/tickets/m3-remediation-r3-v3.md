## R3 revision v3 — public citation and observation-failure coverage

This append-only ticket revision is governed by `docs/design/m3-remediation-v4.md` and
supersedes R3 v2. Guide v8 is the active locked guide. It explicitly checks the public `answer`,
citation marker/order, alias mapping and same-request binding; semantic scoring receives only
public answer and public citation excerpts/source locators, never hidden trace chunks. Missing
trace, Workspace mismatch and incomplete provenance are observation failures, not zero scores.
`ANSWER` requires semantic citation output; `REFUSAL` is inapplicable. The guide also proves the
public `HttpEvaluationExecutor` seam and no evaluation-only retrieval path.
