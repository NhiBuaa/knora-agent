# Issue 105: bounded thinking feasibility outcome

Status: **preliminary acceptance failed**. The owner-approved spike is complete;
the remaining Issue #105 remediation is not complete.

## What was measured

- Eleven unrelated synthetic development cases; one generation call per case.
- Pinned Qwen3 8B digest, the same v5 system prompt and fixture as the disclosed
  non-thinking trials. The request changes were `think=true` and `num_predict=2048`;
  `num_ctx=8192` and temperature zero stayed fixed.
- Runtime commit `243cdcf7a01c2a71f2451fa160f79744812032ff`, tree
  `7c6c58db10438e76ac07f85eb6ddc119cda9c447`.
- A 240-second wall deadline covers each provider invocation, including digest lookup.
  All eleven requests completed within the deadline and output-token bound.
- The isolated probe reuses the actual adapter's digest checks, parsing and existing
  mechanical validator. It does not change production bootstrap or daily dev defaults.
  Its transport is an experimental evaluation artifact, not a production selection.
- Only normalized final results were captured privately. No raw reasoning, prompts,
  evidence or final answer text is in these reports. Whether the returned thinking
  field was non-empty was not recorded; only the requested inference mode is verified.

## Results

| Check | Result |
| --- | --- |
| Requests and provenance bindings | 11/11 verified |
| Decision, JSON shape and citation aliases | 11/11 |
| Literal checks | 9/11 |
| Independent semantic review | 9/11 |
| Latency: minimum / median / maximum | 21.81 / 41.97 / 72.00 seconds |

The independent reviewer checked every final result against the fixture and reproduced
the fixture, prompt, request-message and answer hashes. The coordinator independently
reproduced all eleven full response bindings. Verdicts are bound to fixture, prompt,
request policy, case, repetition and canonical normalized result, not just answer text.

Failures:

- `prohibited_requirement`: an explicit prohibition becomes an optional requirement.
- `rule_with_exception`: the conditional exception and required approval are omitted.

The terse numeric answer in `support_after_related_rule` passes because the question
supplies the unit and the cited alias directly supports the requested value. This is
an independent semantic verdict, not an adjustment to the literal scorer.

See `../vietnamese_rag/issue105_thinking_v1_literal.json` and
`../vietnamese_rag/issue105_thinking_v1_semantic_review.json` for exact bindings.
No repeated sampling or held-out generalization claim is made.

## Code verification

Fresh full verification of code commit `243cdcf` against the migrated isolated
`knora_issue105_test` database: 1378 passed, 16 skipped, 28 dependency warnings.
Ruff, Compose config, OpenAPI export check and diff check passed. Compose warned
about unset optional object-store/test credential variables.

The initial test invocation failed collection because it set only one provider
selector. Removing the partial selector from that child test process restored the
intended deterministic test bootstrap; no repository or user environment change
was needed. The subsequent complete run is the count above.

The probe's request/privacy and cancellation behavior passed TDD and independent
code review before the real run. No frontend file changed in this spike; the last
frontend gate remains the 148-test integrated-code check described in the v5
checkpoint. These code gates do not establish model semantic acceptance.

## Consequence for acceptance

The owner's condition for rerunning the full question set was a successful preliminary
probe. That condition was not met. Original36, revised36 and the real Keycloak/BFF/browser
Conversation gate were not run with this experimental mode. The earlier v5 result remains
28/36; scores do not transfer to the thinking experiment.

Repeated prompt/model-mode failures now require a discussed inference-design change under
`systematic-debugging`, rather than another blind prompt revision. `brainstorming` requires
approval of that new design before implementation. The currently approved shared result
schema, public GenerationProvider contract, citation authority and no-repair-retry policy
remain the constraints for proposing that change. Mechanical validation alone cannot
establish semantic support or complete qualifications.

Keep #105 open, PR #135 draft and #116 as the final release gate. No deployment activation,
local `codex/test` integration, main merge or worktree removal was performed for this spike.
