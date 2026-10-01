# Issue 105: process supervision and Qwen3 14B feasibility

Status: code verified; real 14B seed 105 failed the independently reviewed preliminary gate.

The owner approved process supervision and a bounded 14B trial after the 8B extraction
experiment failed semantic acceptance and one cooperative-timeout call took 451.9 seconds.
All implementation remains evaluation-only. Production provider/defaults, shared schema,
source-quote validator, extraction prompt, renderer and scoring are unchanged.

## Process ownership and deadlines

Each measured call creates one owned Windows spawn worker. The parent receives only safe
request metadata and a normalized GenerationResult or error through an in-memory pipe.
The parent polls a bounded queue; pipe reads occur in a separate owned reader thread, so a
partial/stalled receive cannot block the parent's deadline loop. It terminates and reaps
only its own worker, closes IPC and waits a bounded time for its reader. Repeated async
cancellation waits for this cleanup before returning. No user-owned Ollama process is stopped.

The monotonic timer starts before process startup. Its configured deadline is 240 seconds;
the explicit child/reader cleanup wait budget is 0.65 seconds. Blocking OS process startup
has no proven elapsed bound, and server-side cancellation is not proven by client cleanup.
No strict kernel scheduling guarantee is claimed. Any observed deadline expiry fails the
runtime gate and stops the entire profile; remaining cases are reported as unmeasured.
Cleanup failures similarly halt the profile after attempting every owned resource close.
The parent and child verify the actual imported Ollama adapter, GenerationResult and
generation validator paths and content against this worktree's committed backend files.
Their runtime byte hashes and normalized committed hashes are report metadata; a mismatch
fails closed before measurement or stops the profile without launching another child.

TDD initially reproduced missing-supervisor/composition and unsupported model/context
failures. Review then identified a blocking receive and early return on repeated cancellation.
Both were reproduced as failing tests and repaired before any real 14B call. Actual spawn
tests prove silent-worker termination, successful reaping and async cancellation cleanup;
a local HTTP integration exercises the actual adapter, extraction and memory projection.
Startup-exception cleanup and secret-safe errors are also covered.
The follow-up cleanup failure and wrong-checkout findings were reproduced as failing tests
and repaired. Independent read-only review found no remaining P0/P1/P2 blocker for probe
readiness; this is not a production or release clearance. Focused tests: 51 passed, one
live opt-in skip. Ruff, Compose config, OpenAPI and diff checks passed. The isolated full
suite retry passed: 1404 passed, 16 skipped, 28 dependency deprecation warnings in 183.62
seconds. No frontend files changed.

The first full run had 1403 passes, 16 skips and one failure in the existing PostgreSQL
test `test_postgres_delete_revalidation_honors_other_active_diagnostic_retention`:
`no_work` instead of `not_eligible`. This delta does not modify that test or lifecycle
implementation. The complete lifecycle test file then passed 21/21 without code changes.
The test sets eligibility from the host clock, whereas claim compares the database clock;
a read-only sample bracketed their offset at -7.486 to +2.061 ms, which does not prove
the failure cause. The complete retry passed without implementation changes; the failed
run is retained here and the intermittent lifecycle result is not claimed repaired.

## Predeclared model trial

- Model: `qwen3:14b`, local digest
  `sha256:bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8`.
- The [Ollama model entry](https://ollama.com/library/qwen3:14b) lists a 9.3 GB Q4_K_M
  artifact; the local tag inventory reports 9,276,198,565 bytes. The authorized download
  is complete; the existing 8B, 4B and embedding tags remain.
- Machine snapshot: 31.31 GiB physical memory, about 10.45–10.86 GiB available, and no
  model loaded before the trial. This snapshot is not a permanent memory guarantee.
- First profile: thinking disabled, temperature 0.7, top-p 0.8, top-k 20, min-p zero,
  output 2048 and context 4096. This lower context is specific to the short synthetic
  fixtures and is separately request-policy bound. The adapter's returned prompt count
  must fit the reserved input budget, output count must fit 2048, model must match and
  finish reason must be `stop`. These checks do not independently prove every server-side
  tokenizer/template behavior. A PDF trial requires its own context/budget assessment.
- Fixture and semantic rubric remain unchanged. Seeds 105/106/107 are predeclared: first
  failed 11-case profile stops before later seeds; runtime/supervisor failure stops the
  active collection immediately. First success requires independent review and both
  remaining seeds before PDF. No inference-mode reroll or successful-sample selection is planned.
- This changes both model and context relative to the earlier 8B runs. It is a feasibility
  check, not an isolated estimate of model capacity or an improvement/generalization claim.

No original36/revised36, durable Conversation, Keycloak/BFF/browser or release PASS is
established by this provider probe. Keep #105 open, PR #135 draft and #116 as the final gate.
No main merge, local codex/test integration or worktree removal.

## Real Qwen3 14B seed 105 outcome

The run used clean commit `0c14a5f17c11bf0098ae0f71d017913d08034909`, tree
`2f9c08895fdf60a58f7bcf7e6a5d1772bd7ffc6c`, the predeclared non-thinking profile and
context 4096. Both reviewer and coordinator verified the report/private byte hashes,
fixture, prompt, extraction schema, three parent runtime sources, all eleven child source
bindings, request options and normalized answer/response bindings. The reviewer independently
verified all request message hashes as well. The coordinator reproduced every response binding.

| Observation | Result |
| --- | --- |
| Actual chat requests / case observations | 11 / 11 |
| Structurally valid results | 11/11 |
| Literal checks | 8/11 |
| Independent semantic review | 8/11 |
| Per-case latency | 13.13–41.60 seconds; median 24.98 seconds |
| Total observed case latency | 303.37 seconds |
| Prompt / completion tokens | 470–539 / 41–194 |
| Finish reason | `stop` for all eleven results |
| Deadline exceedances / supervisor failures | 0 / 0 in these eleven observations |

The following semantic failures remain:

- `metadata_year`: infers the requested event attribute from document metadata; evidence
  does not establish that attribute, so refusal is required.
- `metadata_count`: substitutes program structure for an absent required item count.
- `prohibited_requirement`: weakens an explicit prohibition into a statement that the
  action is not mandatory.

Both conditional-exception cases preserve the ordinary rule, eligibility and required
approval in this run. This does not establish an isolated improvement: model and context
both changed, and the development fixtures were already exposed. Exact quote membership
and valid citation aliases do not independently establish semantic support for summaries.
Intermediate extraction and raw thinking were not retained; normalized final responses
do not prove which extraction field caused an error.

The first profile failed. Seeds 106/107, PDF, original36/revised36, durable Conversation,
Keycloak/BFF/browser and release gates were not run. There was no model reroll, validator
relaxation or score repair. No deadline failure was observed in this run; controlled tests
cover an uncooperative child, stalled receive, cancellation and cleanup failure. The
unproven OS startup/kernel scheduling/server cancellation limits above still apply.

Reports:

- `../vietnamese_rag/issue105_process_14b_seed105_literal.json` — SHA256
  `42cc50fc8c436be2cd96838980eb032a1b5e6c656c362291e833ed7a09fceaa8`.
- `../vietnamese_rag/issue105_process_14b_seed105_semantic_review.json` — SHA256
  `aa38b33d632bb01cfc1989bbc1753e56f964107742fb768b221cb70aee728e3c`.
- Private normalized response artifact SHA256
  `49cb6b371c89080136bb10d7744e8968396db77e842438f3f5af8fc449dabcb3`;
  independent private verdict SHA256
  `a596cca7266e1a22045a62c1dbb5f04f6ce789ed84c9a91444c8cac76d6a0fa2`.

The observed Ollama runtime reported the same pinned 14B digest, context 4096 and zero
VRAM bytes (CPU); model runtime size was 10,095,029,124 bytes and host available memory
was about 4.69 GiB at the sampled time. These snapshots are not permanent guarantees.

PR #135 remains draft and #105 remains open. Local `codex/test` was verified clean at
`8ccddc4ce41ff5e5baa10a47cc5ab175351c4d31`; this experiment was not integrated there.
The required Prettier status passed on the measured code commit; the report publication
must retain its own current status. Keep #116 as the final release gate.
