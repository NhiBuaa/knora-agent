# Issue #191 — prompt extraction audit and proposed plan

Status: file scope approved by the owner in chat; implementation in progress.
Date: 2026-10-15.

## Authority and baseline

- Approved direction: option A in Issue #191; one internal production-answer prompt
  module, with policy, pure building and definition identity responsibilities.
- Owner-selected extraction baseline: `67a149fb462f7acc5abc41a7a439a6bdae1d5fe7`
  from #183 / Draft PR #184. This is **not an accepted release**.
- Worktree: `C:/Developer/Projects/knora-agent-worktree/issue-191-prompt-policy`.
  Branch: `refactor/issue-191-prompt-policy`.
- Latest #183 discussion read: Q17 **approved**, comment `6186608013`, mirrored in
  #191 comment `6186607494`. Q16's schema-only diagnostic returned HTTP200 with
  `length`/null answer at 1024 tokens. Q17 approves a simpler before/items/after
  schema and prompt v16, but **no maintained commit exists yet**. Preserve the
  baseline v15 during this extraction; do not copy uncommitted Q17 code here.
  Before review/integration, port only the exact owner-approved Q17 commit/diff
  and rerun parity against that revised baseline. No particular schema keyword or
  token-limit cure is established.
  #183 retains ownership of behavior/schema and its acceptance.
- Project #191 is In Progress / Next. #153/#158 keep their priority and resources.

## Audit: profiles and ownership

| Profile | Existing definition | Preservation contract |
| --- | --- | --- |
| Generic OpenAI compatible | `structured_generation.py` | `m1-cited-answer-v1`; exact system text; four-field schema; user JSON keys `question`, `evidence` |
| Ollama Qwen 8b/4b | `ollama/generation.py` | `ollama-qwen3-cited-answer-v5`; grounding/few-shot text; JSON keys `evidence`, `current_question` |
| Ollama GPT-OSS 20b | `ollama/generation.py` | Exact model predicate, appended example and sorted schema text; composite `ollama-gpt-oss-low-schema-v3:ollama-qwen3-cited-answer-v5` |
| Cloudflare selector | `openai_compatible/presentation.py` | `cloudflare-presentation-v1`; same question/evidence serializer; four presentation choices |
| Cloudflare answer | `openai_compatible/generation.py` | `cloudflare-gpt-oss-cited-answer-v15`; exact selected-presentation suffix; each of four selected schemas |

All serializers retain Unicode handling, whitespace, key ordering and escaping.
Cloudflare retains two ordered calls and existing per-stage/aggregate metadata.
Deterministic generation has no model prompt and stays outside extraction.

Application owns Evidence Aliases, context selection/bounds, generation question
wrapping, public validation, citations and access. Inventory both context instruction
sites (`answering/module.py`, `conversations/context.py`); retain them in place and
test their exact input to the builder. Context policy remains `conversation-context-v2`.
Adapters retain auth, HTTP envelope, model controls, digest checks, usage/cost,
errors, decoding and Cloudflare composition. No transport or composer moves.

## Proposed file scope

Paths below are relative to this worktree.

**Create one internal package, without services, registry or dependencies:**

- `backend/src/knora/providers/prompts/__init__.py`: empty package marker.
- `backend/src/knora/providers/prompts/policy.py`: existing policy/version constants
  and the two unchanged serializer implementations; retain profile differences.
- `backend/src/knora/providers/prompts/builder.py`: pure profile/model/stage selection
  and message building, returning messages, selected schema and definition identity.
- `backend/src/knora/providers/prompts/versioning.py`: a small definition value and
  deterministic SHA-256 of canonical static policy/schema/serializer identity.
  No question, evidence, credentials, usage or model/token settings in that hash.

**Adapt existing owners/callers:**

- `backend/src/knora/providers/structured_generation.py`: keep generic schema and
  compatible exports; delegate prompt/serializer ownership to the internal module.
- `backend/src/knora/providers/ollama/generation.py`: consume builder results;
  preserve legacy constant exports and every transport/control/decoding path.
- `backend/src/knora/providers/openai_compatible/generation.py`: consume builder
  results for generic and both Cloudflare stages; retain orchestration and metadata.
- `backend/src/knora/providers/openai_compatible/presentation.py`: retain its type,
  Pydantic model and schema; reexport policy constants from their new owner.
- `evals/runners/ollama_refusal.py`, `evals/runners/vietnamese_conversation.py`:
  use canonical prompt/version ownership, preserving existing version/hash values.
- `evals/runners/ollama_process_probe.py`: extend its existing checkout/committed-source
  guard to cover extracted policy/builder/identity dependencies. Keep report schema.

**Tests/fixtures to create or adapt:**

- `backend/test/providers/fixtures/prompt-baseline-67a149f.json`: synthetic offline
  request/result fixture captured from the untouched baseline, before extraction.
- `backend/test/providers/test_prompt_parity.py`: complete adapter request parity
  through MockTransport; generic, Qwen 8b/4b, GPT-OSS and all Cloudflare presentations;
  context absent/present, Unicode/quotes/newlines, alias/evidence order.
- `backend/test/providers/test_prompt_definitions.py`: pinned static fingerprints,
  serializer contracts, drift detection and existing version/stage propagation.
- `backend/test/providers/ollama/test_generation.py`: move version monkeypatch to
  the canonical owner while retaining the existing derived-version assertion.
- `evals/test/test_ollama_process_probe.py`: assert the expanded real dependency
  set and its rejection of source/checkout drift; do not merely change a count.
- `evals/test/test_ollama_refusal.py`, `evals/test/test_vietnamese_conversation.py`:
  adjust only ownership-sensitive assertions if the import change requires it.

**Documentation:** this plan, `CONTEXT.md`, and
`docs/adr/0019-production-answer-prompt-ownership.md` (verify number still unused).
Record #191-only changes and each approved #183 synchronization separately here.

No planned edits to `GenerationResult`, trace/readers, bootstrap, configuration,
`answer_blocks.py`, context behavior, frontend, generated contracts or old evidence.
Run their relevant tests. Any additional maintained-file change needs a stated
reason and, if it expands the approved scope, owner approval before editing.

## Definition identity without changing runtime schemas

Keep all existing readable versions and metadata fields. Pin a static definition
fingerprint per profile/stage/presentation in tests; include the actual static
system suffix and selected schema. Pair explicit serializer identity with baseline
byte-parity fixtures and the evaluation source guard. Drift checks run in tests/CI,
not as a new production refusal/error path. Trace/evaluation continue carrying
their existing versions and hashes; verify their correspondence to the definitions.
Do not append hashes to historical versions, add metadata fields, rewrite reports,
or repair preexisting evaluator behavior in this refactor.

## Execution and verification after approval

1. Refresh #191/#183/PR #184 discussions and exact heads; record approved deltas.
   Capture synthetic baseline fixtures through mocked transports before any extraction.
2. Add parity/definition tests; demonstrate baseline characterization passes and the
   new definition interface is initially absent, then extract the smallest module.
   Keep schema models/helpers in their existing pure contract files to reduce #183
   overlap. Empty package initialization avoids circular legacy reexports.
3. Update the actual evaluation imports/source guard and focused tests. Verify full
   messages, schema, envelopes, versions, stages, outputs and failures against the
   independent baseline fixture; test drift detection without calling a model.
4. Run provider, answering, context, bootstrap and affected evaluation offline suites;
   run existing Cloudflare/Postgres application tests on an isolated test DB. Cover
   ANSWER/REFUSAL, empty-evidence no call, invalid output, citation order/mapping,
   workspace isolation, unknown usage, digest rejection and no retry.
5. Run `python -m ruff format .`, `python -m ruff format --check .`,
   `python -m ruff check .`, full pytest, `docker compose config --quiet` and
   `git diff --check`. Use an isolated worktree environment with imports verified
   against this checkout. Record skips/failures honestly. Required CI must pass on
   the eventual exact PR head before integration; no CI success is claimed now.

No model calls, HTTP400 diagnosis/fix, runtime allowance, framework, retries or
semantic compliance claim. Offline parity does not accept #183.

## Coordination and integration safeguard

- #183 keeps working. Refresh its discussion/head before editing shared files,
  before commit/PR and immediately before any integration. Q17 is approved but
  uncommitted; keep its behavior/schema/prompt changes separate until a commit is
  available. Port that exact diff into a separately recorded revised baseline,
  then rerun parity. Do not silently reinterpret or fix it here.
- Review #191 with `git diff <recorded-baseline>...HEAD` and
  `git log <recorded-baseline>..HEAD`. Never describe the full main-to-HEAD diff as #191.
- While #183 is unaccepted, keep work local or, after the owner's integration choice,
  use a Draft stacked PR targeting `fix/issue-183-answer-lists`. No merge to main.
  Before any retarget to main, establish that accepted #183 changes are present in
  main, reconcile current main, and verify the PR includes only #191 changes.
  If #183 is rejected/changes direction, re-port only #191 onto the accepted baseline.
- No push, merge, issue closure, Done transition or branch/worktree deletion in
  this audit turn. Keep this worktree for owner review and the next approved step.

## Evidence from this audit turn

- Worktree initially clean at the exact baseline; provider module import path checked.
- Existing focused offline run: **267 passed, 1 skipped**, 36.63 seconds.
  Covered generic/Cloudflare provider tests, presentation/composer, Ollama provider,
  answering, context, refusal/grounding/process/conversation evaluation tests.
  The skipped test requires `KNORA_RUN_LIVE_OLLAMA_GROUNDING=1`; no opt-in was set.
  Ran with `PYTHONPATH=<this-worktree>/backend/src;<this-worktree>` and the existing
  primary-checkout virtualenv interpreter, whose module import resolved here:

  ```powershell
  python -m pytest backend/test/providers/openai_compatible/test_generation.py backend/test/providers/openai_compatible/test_presentation_generation.py backend/test/providers/openai_compatible/test_answer_blocks.py backend/test/providers/ollama/test_generation.py backend/test/answering backend/test/conversations/test_context.py evals/test/test_ollama_refusal.py evals/test/test_ollama_grounding.py evals/test/test_ollama_process_probe.py evals/test/test_vietnamese_conversation.py -q
  ```

- Full suite, isolated DB regression, formatting gates and new parity/identity tests
  have not run; production/test code has not changed. Hindsight search/list failed
  with local connection refused; decisions were checked in live issues and code.
- Current #191-only diff is this uncommitted plan document.

## Approval requested

The owner approved this file scope, schema-preserving identity design and integration
safeguard in chat. There is no unresolved product-behavior decision from the audit.
Any new one is returned to the owner using grilling before implementation proceeds.

## Execution ledger

- Hindsight initiative recorded as `kp-12c5ba8715d44bde8d4c5eb1f7645bf0` before code.
- Independent synthetic fixture captured before extraction from baseline `67a149f`;
  real adapter requests compared via MockTransport: 8 pass, then 16 pass including
  application Conversation Context wrapping.
- Definition tests: RED 13 failures for absent module, then GREEN. Focused provider,
  definition and transport suite: 81 passed before the additional context cases.
- Extracted policy, builder and definition identity; retained the generic schema,
  presentation model/schema and Cloudflare composer in their original owners.
- Evaluation guard RED 13 expected failures, then 14 guard tests passed; 36 focused
  refusal/conversation tests passed. Guard now covers nine actual source dependencies.
- Dedicated disposable test DB: container `knora-issue191-postgres`, port 15491,
  database `knora191`, migrations at head. No other runtime/DB reused or modified.
- #183 Q17 is now committed at `c775a8355b13fde26cb3eb59619239d1536286ca`.
  Preserve the first #191 extraction commit against `67a149f`, then rebase only this
  refactor onto that approved #183 commit and capture a separate Q17 parity fixture.
  This keeps #183 changes upstream and the #191-only diff explicit. No main merge.
- Verification and independent review are still pending; no acceptance/CI claim.
- Pre-synchronization regression: 380 passed (2 dependency deprecation warnings),
  including provider/application/bootstrap/context/Cloudflare Postgres and focused
  evaluation callers. Ruff format/check/lint and diff check passed. Spawned process
  provenance checks and full pytest run after the source is committed.
