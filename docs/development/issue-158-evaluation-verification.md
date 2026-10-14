# Issue 158 evaluation integration evidence

Branch: `feature/issue-158-evaluation-pilot`. Base: `7697615395e469863279b9f5286b4ebed2396144`.
Worktree: `C:/Developer/Projects/knora-agent-worktree/issue-158-evaluation-pilot`.

## Authority and activation

Knora datasets, gold, manifests, runs, reports and gates remain authoritative. DeepEval consumes
captured answers; Ragas drafts require owner review; Langfuse export stays off. Guardrails shadow
implementation belongs to #188. No merge, runtime deployment, model download or quality acceptance
is implied by these tests. See [ADR 0017](../adr/0017-knora-evaluation-tool-authority.md).

The read-only Cloudflare subscriptions request returned HTTP 403 / code 10000. This does not prove
Free or Paid. Workers Free and current quota were not verified, so the conditional DeepEval pilot
was **not run**: inference attempts **0**, paid inference cost **USD 0**. No Ragas live call or
Langfuse credential/export was used.

## Compatibility and test isolation

Python 3.12.15 and optional packages were installed in the worktree's `.venv`. The local interpreter
lives under ignored `.python` because the shared interpreter links were broken. Existing primary
Python, Ollama processes, GPU and running services were not changed.

DeepEval 4.2.8, Ragas 0.4.3 and Langfuse 4.17.0 installed together. Import and actual API tests are
required in addition to dependency resolution; Ragas exposed a LangChain compatibility conflict
during this work. DeepEval and Ragas are Apache 2.0; Langfuse's Python SDK is MIT. Optional extras
keep these tools out of normal runtime installation. CI installs them for offline contract tests
with discovery/telemetry disabled. Ragas 0.4.3 failed to import with LangChain Community 0.4.2;
the optional extra pins Community 0.3.31, resolving LangChain 0.3.30, Core 0.3.86 and OpenAI 0.3.35.
The resulting 149-package environment passes `uv pip check`.

Test shells normalize the machine's malformed IPv6 `NO_PROXY` entry to `127.0.0.1,localhost`;
this is process-local. The database gate uses a temporary, labeled `knora158-evaluation-tests`
container at `127.0.0.1:55458`, CPU 1 / RAM 256 MiB, from the already installed pgvector image.
Existing databases at ports 55432, 55453 and 15483 are not used. Tests use deterministic providers.

## Evidence ledger

| Check | Result | Scope |
| --- | --- | --- |
| DeepEval initial focused contracts | 80 passed | Real metrics with mocked HTTP; no Cloudflare |
| Publication binding regression | 12 failures on prior code, then 92 focused tests passed | Stale question/answer/reference/evidence and missing identities rejected |
| Ragas and adjacent focused contracts | 57 passed | Actual PydanticPrompt API, explicit mock provider, selected export approval and pending review |
| Ragas provenance regression | 6 failed on prior code, then 17 focused tests passed | Imported candidates remain caller-declared; actual Ragas generation is identified separately; blank provenance rejected |
| Langfuse focused contracts | 11 passed | Actual typed SDK/MockTransport, safe serialization, exact payload review and default OFF |
| Backend CI partition | 1,316 passed / 621 deselected | Before later integration changes; preliminary |
| Windows CI partition | 242 passed / 1,700 deselected | Before later integration changes; preliminary |
| Database CI partition | 363 passed / 12 skipped | Separate test DB; skips require the CI database name |
| Database concurrency follow-up | 12 passed | CI database name and DSN without query suffix, still port 55458 |
| Ruff format/check/lint | Passed after DeepEval fix | Final checks follow all adapters |
| Shared Prettier format/check | Passed | Existing CI dependency install and opt-out environment changes |
| Compose configurations / OpenAPI | Passed | Configuration only; no application started |

The database partition emitted 26 existing Alembic `path_separator` deprecation warnings. The
12 skipped concurrency tests require the literal database name `knora_issue110_task2`; that name
was created and migrated inside the owned test container. Their fixture also requires the DSN to
end with that name, so a `connect_timeout` query suffix caused an initial follow-up to skip. The
corrected DSN ran all 12 tests successfully and is used for the final full gate. No safety check
was lowered. Final branch verification and review results are recorded below when complete.

## Decisions made during execution

- Keep Guardrails implementation in #188 as requested. If the split is wrong, security integration
  needs coordinated follow-up; existing security behavior stays authoritative.
- Treat the latest USD 0 instruction as superseding the historical USD 2 reserve. An unverified
  account blocks inference; the cost of this conservative choice is pending live judge evidence.
- Install Python inside this worktree rather than repairing shared links. The tradeoff is local
  disk usage and a separately maintained test environment, with no change to other sessions.

## Remaining acceptance

Human comparison of judge results, owner review of generated multi-hop questions, a separately
approved Ragas call inventory, and approved Langfuse access/serialized payload/deletion readback
remain required. Mock success and package installation do not establish evaluation quality,
seven-day Cloud retention or Guardrails detection/false-positive performance.
