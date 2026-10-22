# Issue 158 evaluation integration evidence

Branch: `feature/issue-158-evaluation-pilot`. Base: `7697615395e469863279b9f5286b4ebed2396144`.
Worktree: `C:/Developer/Projects/knora-agent-worktree/issue-158-evaluation-pilot`.

## Authority and activation

Knora datasets, gold, manifests, runs, reports and gates remain authoritative. DeepEval consumes
captured answers; Ragas drafts require owner review; Langfuse export stays off. Guardrails shadow
implementation belongs to #188. No merge, runtime deployment, model download or quality acceptance
is implied by these tests. See [ADR 0018](../adr/0018-knora-evaluation-tool-authority.md).

Issue #153 owns the 16-PDF/60-question gold and Retrieval V3 baseline. Ragas is reserved for
proposing later needed additions, with owner review; it does not regenerate those 60 questions.
Code may merge after CI/review pass without live quality results. Issue #158 remains In Progress
until owner quality acceptance. No model call is authorized by plan/quota verification alone.

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
the optional extra pins Community 0.3.31. That pin permits multiple compatible LangChain versions;
it does not pin the entire family. Actual installed package metadata and CI logs give:

| Distribution | Local Python 3.12.15 | Ubuntu CI run 38598587672 |
| --- | --- | --- |
| langchain-community | 0.3.31 | 0.3.31 |
| langchain | 0.3.30 | 1.4.5 |
| langchain-core | 0.3.86 | 1.6.10 |
| langchain-openai | 0.3.35 | 1.1.9 |
| openai | 2.54.0 | 1.109.1 |

Community 0.3.31 declares `langchain>=0.3.27,<2` and `langchain-core>=0.3.78,<2`.
Local langchain 0.3.30 and langchain-openai 0.3.35 additionally require Core below 1; local
langchain-openai permits OpenAI `>=1.104.2,<3`. Both tested resolutions satisfy their own
installed constraints. The 149-package local environment passes `uv pip check`, and a dry-run
of all optional extras resolves successfully. The Ubuntu run passed all 17 actual-package Ragas
contracts; its sole failure was the independent Free-preflight timestamp fixture below.
No additional pin or dependency upgrade is needed for that test fix.

Current [LangChain installation guidance](https://docs.langchain.com/oss/python/langchain/install)
separates provider integration packages; it does not promise one family version from the
Community pin. These are observed compatibility results, not a blanket claim for every future
resolution. The optional integration continues to use an explicit Knora provider and opt-outs.

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
| Langfuse M3 failure status regression | 12 passed | Known observation failure preserved; arbitrary text remains unknown |
| Backend CI partition | 1,316 passed / 621 deselected | Before later integration changes; preliminary |
| Windows CI partition | 242 passed / 1,700 deselected | Before later integration changes; preliminary |
| Database CI partition | 363 passed / 12 skipped | Separate test DB; skips require the CI database name |
| Database concurrency follow-up | 12 passed | CI database name and DSN without query suffix, still port 55458 |
| Ruff format/check/lint | Passed after DeepEval fix | Final checks follow all adapters |
| Shared Prettier format/check | Passed | Existing CI dependency install and opt-out environment changes |
| Compose configurations / OpenAPI | Passed | Configuration only; no application started |
| Full pytest | 1,973 passed / 4 skipped / 26 existing warnings, 565.16 s | Owned test database; isolated deterministic providers |
| Final Langfuse focused run | 12 passed, 1.34 s | Full-suite collection preceded the additional status test; this run covers it on the final adapter |
| DeepEval ambient provider-mode regression | 2 failed before fix; 2 passed after fix; full scorer file 25 passed | Installed 4.2.8 cannot construct TypeSafe under ambient hybrid/system_one; all metrics use mocked Cloudflare |
| Final root/CI startup collection | Passed for developer root and backend/windows/database CI prefixes | Root pytest.ini selected; DeepEval plugin absent; root collected 1,979 tests |
| Final fix formatting/lint | Passed | Ruff format/check/lint and shared Prettier format/check after provider/startup changes |

The database partition emitted 26 existing Alembic `path_separator` deprecation warnings. The
12 skipped concurrency tests require the literal database name `knora_issue110_task2`; that name
was created and migrated inside the owned test container. Their fixture also requires the DSN to
end with that name, so a `connect_timeout` query suffix caused an initial follow-up to skip. The
corrected DSN ran all 12 tests successfully and was used for the full gate. No safety check
was lowered.

The full command was `.venv/Scripts/python -m pytest --junitxml=<local-ledger>/full-report.xml -q`,
with `KNORA_DATABASE_URL` selecting only port 55458 and explicit telemetry opt-outs in the test
process. The four skips are three manually enabled locked PDF acceptance fixtures and the pinned
real Ollama test; neither activation is authorized here. The temporary test container was stopped
and removed after checking its recorded ID and ownership label. Other services remain untouched.

Final review identified two gaps: ambient DeepEval modes can select TypeSafe instead of the
explicit judge, and root-target pytest does not select the nested backend configuration. Docker
also does not inherit the host job's opt-out environment automatically. The final fix pins LLM
execution to the approved judge and suppresses plugin loading before pytest starts, with the
same opt-outs passed into the disposable database process. Commit `22a81e2` addresses both.
The full local test run had the opt-outs set before process startup; it made no live judge call.
The startup follow-up only collected tests; it did not run the database container or repeat the
full suite. Docker environment propagation was checked in the workflow. Review and focused
regressions cover this final change; the full-suite result belongs to the earlier tree.
Each integration received task review and regression re-review. The whole-branch review found
the two issues above; the single consolidated fix wave received a scoped re-review with both
findings addressed, zero open findings and no new breakage. Live quality remains unaccepted.

## PR 190 review follow-up — 15 October 2026

[Ubuntu CI run 38598587672](https://github.com/NhiBuaa/knora-agent/actions/runs/38598587672)
failed only `test_free_preflight_requires_fresh_bound_approval`: 1 failed, 1,359 passed,
621 deselected. The valid fixture sampled observation time before trial start in separate clock
reads. Linux preserved that microsecond difference, correctly violating `started <= observed`.
The earlier Windows pass did not reproduce this finer-clock failure.

The fixture now derives its timestamps from one UTC instant. A start one microsecond after
observation must still fail, and the expired-trial case restores a valid quota reset first so
it tests the trial boundary independently. Production validation is unchanged.

- DeepEval capture, Ragas review and Langfuse bridge tests: **54 passed, 5.69 s**. Actual optional
  package APIs use mocked HTTP; no model or Cloud export call was made.
- Ruff format: 385 files unchanged; format check: 385 files formatted; lint: all checks passed.
- `uv pip check`: 149 packages compatible. All optional extras resolve in a dry-run; no new
  dependency pin or install was required for this follow-up.
- Git whitespace check passed. The earlier full-suite result above belongs to the earlier tree;
  hosted CI must verify the pushed follow-up on Linux and the other required partitions.
- Compose configuration validation passed with synthetic credentials and no service startup.
- Scoped review found one unconditional future-Ragas acceptance statement; it is now conditional
  on an approved expansion. Re-review confirmed the finding addressed with no open findings.
- The evaluation ADR moves from 0017 to **0018**, including all maintained references. PR #184
  retains `0017-structured-generated-lists.md`. The compatibility table above records the actual
  local and Ubuntu resolutions rather than inferring a fixed LangChain family from Community.

This follow-up documents the owner's #153/#158 boundary and separates code review/CI readiness
from quality acceptance. It does not run Ragas generation, enlarge gold, authorize a live model
call, enable Cloud export or enforcement, or merge the PR.

## Decisions made during execution

- Keep Guardrails implementation in #188 as requested. If the split is wrong, security integration
  needs coordinated follow-up; existing security behavior stays authoritative.
- Treat the latest USD 0 instruction as superseding the historical USD 2 reserve. An unverified
  account blocks inference; the cost of this conservative choice is pending live judge evidence.
- Install Python inside this worktree rather than repairing shared links. The tradeoff is local
  disk usage and a separately maintained test environment, with no change to other sessions.

## Remaining acceptance

Human comparison of judge results remains pending for actual quality acceptance. A later,
separately approved Ragas expansion requires an approved call inventory and owner review of
generated multi-hop questions before gold promotion. Before Langfuse Cloud activation, approve
access and the serialized payload and verify deletion/readback. These activation checks do not
block review/CI acceptance of the offline integration. Mock success and package installation do
not establish evaluation quality, seven-day Cloud retention or Guardrails detection/false-positive
performance.

## Workbench takeover — 17 October 2026

PR #190 has merged; Issue #158 quality remains unaccepted. Workbench PR #202 at `7ee019d` has
successful CI and a saved deterministic UI execution, but its expected ANSWER case returned
REFUSAL with zero candidates. No ANSWER capture in that run can be supplied to DeepEval. The
Workbench scoring/proposal services still deny live profiles, and fresh same-account Workers
Free/quota proof plus an exact USD 0 execution envelope remain prerequisites, not approvals.
At takeover the owner used external Edge. The later instruction selects the integrated Codex
browser; no credentials should be sent in chat.

The [current Workbench checkpoint](issue-192-workbench-verification.md) records acceptance gaps,
retained runtime availability and the separate PostgreSQL contention tests. Earlier test results
in this document retain their original SHAs and scope. Gold, thresholds and historical runs are
unchanged; Langfuse export and Guardrails enforcement remain OFF.

### Corpus authority implementation follow-up — 18 October 2026

The owner subsequently approved trusted-host Live Admission code and selected A: a separate
`corpus_prepare` authority to materialize and activate exactly two reviewed READY PDF versions.
The [Workbench checkpoint](issue-192-workbench-verification.md) records its offline/mock tests,
review and shared-coordinator ACKs. This supersedes the historical unconditional live-profile
denial above: an explicitly injected profile now needs exact host authority and a guarded actual
provider boundary; default registrations remain empty. The new corpus adapter does not start a
runtime or authorize real calls. Gold v1, thresholds and historical runs remain unchanged.

Actual corpus/binding verification and a compatible saved ANSWER are still needed before an
approved judge/calibration trial. Ragas proposals, human review/freeze and R3 retain their separate
gate. No offline result establishes real model compatibility, semantic quality or owner acceptance.
