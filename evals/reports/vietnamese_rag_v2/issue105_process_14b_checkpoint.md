# Issue 105: process supervision and Qwen3 14B feasibility

Status: code verified and independently reviewed for a bounded probe; no real 14B score yet.

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
