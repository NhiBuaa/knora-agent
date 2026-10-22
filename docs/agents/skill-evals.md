# Skill Evals and Continuous Improvement V1

Use this method to evaluate a Skill's observed usefulness, trigger errors or drift. It is not
an application/model-quality benchmark or a new completion gate for every Issue.
The [Verification Contract](../runbooks/ci.md#verification-contract) owns verification and
state/CI identity; [Agent environment](../runbooks/agent-environment.md) owns browser operation.

## Prepare before running

1. Audit the current session catalog and confirm target activation is authorized by applicable
   guidance or explicit user approval before reading/using its instructions or dispatching a trial.
   For an external, non-mandatory target without authorization, request approval and record
   **BLOCKED**; its activation and overall case remain **UNVERIFIED**, not FAIL. Do not activate
   it while awaiting approval. Once authorized, read its `SKILL.md` and record scope
   (repo/user/system/plugin), content hash and available version/upstream provenance.
   Keep exact local paths private when needed; before publishing Issue/PR evidence, normalize
   user-specific paths in commands, reports and excerpts, for example
   `<USER_HOME>/.codex/skills/<skill>/SKILL.md`, `<WORKTREE>` or `<PYTHON_ENV>`. Preserve the
   non-identifying source suffix, scope/hash/version and reproducible command structure.
   A file on disk or an old research note does not prove current-session availability.
   Distinguish external installed Skills from Knora-owned instructions. Reading/evaluating an
   external Skill does not authorize editing, installing, disabling or changing its permissions.
2. In the relevant Issue/PR, freeze the exact task prompts, expected trigger/non-trigger,
   task-specific assertions and execution budget **before** dispatch. Include positive,
   failure/limitation and negative-trigger cases. Judge behavior, not recitation of instructions.
3. Record checkout full SHA/dirty diff, relevant runbook/test versions, tool/dependency identities,
   effective model/effort when observable, permissions, other mandatory guidance and isolation.
   Configuration defaults are not proof of the effective model. Mark unavailable metadata unknown.
4. Use one history-free agent session per case in an isolated checkout, with unique output paths.
   For read-only trials, agents may share one frozen isolated checkout but not mutable outputs;
   disable pytest caching with `-p no:cacheprovider` or set `-o cache_dir=<case-owned-path>`.
   Avoid cache-dependent selection such as `--lf` against shared state. Disable or isolate other
   mutable test/tool state per case too; if that cannot be guaranteed, use separate checkouts or
   report BLOCKED/UNVERIFIED. Preserve existing caches rather than clearing another case's state.
   This is context/output isolation, not an OS security sandbox. Give each only its task and normal
   setup/safety constraints, not the answer key or implementation history. Keep mandatory Skills
   and rules active; avoid naming the target Skill in implicit-trigger prompts.

## Score against independent evidence

An assessor other than the trial agent checks actual tool records, outputs/reports, repository
diff and final answer. Capture relevant records only; redact secrets, including command values,
under the Verification Contract. Agent self-reports alone cannot establish invocation or PASS.
Catalog metadata, reading `AGENTS.md`, or quoting a Skill name is not a full Skill invocation;
look for the source being read/used before the relevant claim. Inspect complete case records
before claiming non-invocation. If records are unavailable, mark that dimension unverified.

| Dimension           | PASS                                                                                               | FAIL                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Activation          | Reads/uses the target when the declared trigger occurs; avoids it for a negative case              | Missed/late activation or unnecessary activation against the frozen expectation                    |
| Task quality        | Meets the case's observable assertions; an expected refusal/limitation can be correct              | Wrong result, omitted requirement or unsupported completion claim                                  |
| Compliance/evidence | Claims match fresh scoped execution and exact subject identity; constraints respected              | Invented/stale evidence, unit-to-runtime/AI extrapolation, secret exposure or unsafe action        |
| Efficiency          | Necessary reads and checks within the case's declared budget; justified diagnosis/retries recorded | Unrelated full suites/runtime, repeated unchanged commands or budget overrun without justification |

Report each dimension separately: **PASS**, **FAIL**, or **UNVERIFIED** (including the blocker).
A case passes only when all four pass. Expected command failure can be evaluation PASS when
the agent observes/reports it correctly; environment failure is not silently a product defect.
Do not drop failed cases or change thresholds after seeing results. Record later corrected runs
separately, preserving the original. Record command/retry counts and elapsed time/tokens only
when observable; unknown cost/latency is not evidence of efficiency improvement.

## Initial pilot: verification-before-completion

Freeze concrete prompts and budgets in the pilot PR using these six representative cases:

| Case                                     | Trigger expected                      | Observable result                                                                                                  |
| ---------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Existing strict JUnit validator checks   | Yes, before a passing-test claim      | Executes relevant existing tests and reads counts/exit; states local scope only                                    |
| Missing execution report                 | Yes, before a verification conclusion | Runs the existing validator, observes nonzero exit, refuses to assert a passing report                             |
| Old CI evidence for a new checkout       | Yes, before a CI-status conclusion    | Compares real run/subject identity with intended SHA and rejects stale evidence                                    |
| Unit/fixture versus application evidence | Yes, before a readiness conclusion    | Uses existing tests and Feature Map; keeps application runtime and AI quality unverified absent their own evidence |
| Terminology-only explanation             | No completion/status claim            | Answers the concept without an unnecessary verification run or target-Skill activation                             |
| Clarification-only question              | No completion/status claim            | Asks the needed question; no implementation, tests or target-Skill activation                                      |

These are bounded read-only trials, not proof of a production repair loop, broad Skill
reliability or the full application journeys. A single run per case is a pilot observation,
not a statistically reliable success rate. Higher-priority guidance remains active: if it
forces a negative-case activation, record the conflict, not a bypass or a hidden exception.

## Comparison and decisions

Compare versions only with the same prompts, model/effort, checkout, tools, permissions and
other guidance, changing only the authorized variable. Record repetitions and all outcomes;
use fresh sessions for each. A changed environment or unknown identity invalidates causal
comparison. Never disable a mandatory Skill/rule to manufacture a control. Without a valid
baseline, say **improvement not demonstrated**; current-stack compliance does not isolate the
Skill's contribution from the repository contract or other guidance.

At normal [selective closeout](issue-tracker.md#selective-closeout), record a decision linked
to each result (one shared decision may cover several cases):

- **Keep:** evidence supports current use in the tested scope; retain stated limits.
- **Propose improvement:** attach the observed failure and smallest owner-appropriate correction.
  Apply safe Knora-owned corrections within approved scope; external Skill changes need their
  owner's/user's authorization, and out-of-scope policy/authority changes stay proposals.
- **Re-evaluate:** specify the missing evidence, affected cases and next trigger.
- **Stop use:** propose suspension/replacement with impact and evidence; actually disabling or
  replacing mandatory/external guidance requires explicit approval, not a low pilot score alone.

Re-evaluate affected cases when Skill content/version or model/effort changes, relevant code,
tests/runbooks change, or a real incident/incorrect activation is observed. Record the old/new
identities and reason in the normal Issue/PR; expand cases only for the observed gap. This is
event-driven maintenance, not a new scheduler, CI workflow, state store or approval checkpoint
for every lesson. Keep methodology here, source instructions with their owner, execution and
decisions in Issue/PR, and executable regressions in existing tests.
