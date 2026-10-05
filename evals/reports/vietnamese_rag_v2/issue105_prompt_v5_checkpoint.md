# Issue 105: prompt v5 evaluation checkpoint

Status: **acceptance failed**. No deployment selector or release seal was activated.

## Measured runtime

- Original36 ran sequentially in a new durable Conversation in the isolated corpus snapshot.
- Runtime commit: `7e1a8ca8061159a01c03059bf2f56f5bf569a8e6`.
- Provider: pinned Qwen3 8B, prompt `ollama-qwen3-cited-answer-v5`, one bounded call,
  thinking disabled. The embedding profile, corpus and calibrated candidate are pinned in
  `original36_qwen8b_prompt_v5.json`.
- Dataset v1 is unchanged. These are development-exposed regressions, not a held-out benchmark.
- Independent review recomputed all 36 public response hashes and all 28 cited source locators
  against the original PDF. Hidden selected evidence was not used for citation scoring.

## Original36 results

| Check | Result |
| --- | --- |
| Decision and structural validity | 36/36 |
| Positive citation gold hit | 25/28 |
| Positive semantic review | 20/28 |
| Expected refusals | 8/8: six model-backed, two before generation |
| Complete regression cases | 28/36 |

Failed cases are 01, 04, 08, 10, 13, 14, 24 and 27. They include incorrect count,
missing qualifications or explanation, and unsupported cited locators. A correct JSON shape,
selected gold chunk, or allowed alias does not establish semantic support.

Original case 16 asks about HTTP methods. Its URL requirement is an inaccurate original label;
the original file remains unchanged and this mismatch is disclosed separately in the report.

## Generation-only fallback probe

The plan-approved Qwen3 4B probe used the same prompt and eleven unrelated synthetic cases.
Independent review passed 9/11. One case returned an invalid answer/refusal combination;
another weakened an explicit prohibition into an optional requirement. The smaller model is
not an accepted replacement. See the v5 4B literal and semantic reports in `../vietnamese_rag/`.
No PDF regression score is claimed for 4B.

## Code verification

The #142 acceptance composition and bounded model selector were integrated at
`bb5acad8c8ea10915d204d50ed7bbd29de88b65b`. Fresh checks on that integrated code:

- Isolated PostgreSQL pytest: 1376 passed, 16 skipped. The live opt-in checks remain separate.
- Ruff, Compose config, OpenAPI check and diff check passed.
- Frontend: 148 tests, typecheck, lint, build, format and format check passed.
- Independent scoped review cleared the acceptance server and fallback selector after fixes.

Compose emitted warnings for unset optional object-store/test credential variables; pytest
emitted dependency deprecation warnings. These checks do not establish semantic acceptance.

## Remaining work

A later owner-approved Qwen3 8B thinking spike passed only 9/11 independently reviewed
synthetic cases. Its preliminary gate failed, so no full question-set rerun or thinking-mode
Conversation acceptance is claimed. See `issue105_thinking_v1_checkpoint.md` for the bound
observations and outcome; the v5 result above remains unchanged.

A new inference design needs a bounded probe after repeated prompt failures. Any successful
candidate must repeat original36 and revised36 with separate observations and response-bound
semantic review, then pass the actual Keycloak/BFF/browser journey and exact server trace gate.
The direct durable run is not the HTTP/browser gate. No latest browser PASS is claimed.

The user's original Conversation and production corpus were not changed. Keep #105 open,
PR #135 draft, and #116 as the final release gate. This unaccepted candidate was not integrated
into local `codex/test`; branches and worktrees are retained.
