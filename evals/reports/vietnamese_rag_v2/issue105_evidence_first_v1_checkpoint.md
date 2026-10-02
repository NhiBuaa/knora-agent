# Issue 105: evidence extraction experiment, first outcome

Status: **preliminary acceptance failed**. This experiment is not a deployment selection.

The owner approved a single-call evidence extraction experiment on 2026-10-01 after the
failed thinking trial. Only evaluation code changed; the production provider, shared public
schema, core validation, API/auth contracts and daily dev defaults were not changed.

## Inference design and measured run

- Qwen3 8B receives a private schema separating summarized facts, verbatim source rules
  and verbatim conditional exceptions. Each item names an evidence alias and source quote.
- Every quote must be an exact contiguous substring of its referenced supplied evidence.
  Rules and exceptions render verbatim. Facts still use model-generated summaries, so
  quote membership does not establish entailment or completeness.
- The declared mapping renders the existing GenerationResult with each alias once.
  Invalid extractions fail safely; they are never repaired, retried or converted to refusal.
- The real existing adapter still verifies the digest and parses the mapped public shape.
  Each call has a 240-second wall deadline, 8192-token context and 2048-token output limit.
- The first run used thinking disabled and temperature zero. Runtime commit
  `b94a278c26e3a50d7dc383f4d4b55f7568dc743c`, tree
  `98aed5c2953c2547dcdfd98812ffde9b21f35469`, pinned 8B digest, fixture and prompt/schema hashes
  are bound in the literal report. A concurrent Ollama runtime snapshot observed CPU
  execution (`size_vram=0`) and context 8192; it is not a substitute for request bindings.

## First-run results

| Check | Result |
| --- | --- |
| Actual chat requests | 11 |
| Valid normalized results | 10/11 |
| Literal checks | 6/11 |
| Independent semantic review | 6/11 |

The reviewer verified the fixture, schema, prompt, all request-message hashes, ten final
answer hashes and the error record. The coordinator reproduced all eleven result/error
bindings. Cases are development-exposed; no held-out or generalization claim is made.

Failures:

- `metadata_year`: publication metadata substitutes for an absent event fact.
- `metadata_count`: structural sections substitute for the requested item count.
- `explicit_prohibition`: extraction is invalid, so no valid final response exists.
- `prohibited_requirement`: prohibition is still weakened into an optional requirement.
- `caveat_after_distractor`: a conditional alternative becomes universal; the ordinary
  rule and conditions are omitted.

`rule_with_exception` improves relative to the thinking trial, but prohibition does not;
four previously passing cases regress. Overall acceptance is worse in this single run.
The earlier 9/11 thinking score and 28/36 PDF score do not transfer to this experiment.

Reports: `../vietnamese_rag/issue105_evidence_first_v1_literal.json` and
`../vietnamese_rag/issue105_evidence_first_v1_semantic_review.json`.

## Boundary diagnosis and next controlled measurement

A separate one-case diagnostic repeated `explicit_prohibition` without changing its
inference payload. Only declared extraction fields were captured privately; raw thinking
was not read or persisted. It again failed: the quote changed capitalization relative to
the source, violating exact substring membership. The private artifact hash is in the
semantic report. This diagnostic does not revise the original score or prove that every
possible rejection has the same cause. The quote validator and scoring rubric remain intact.

The final summaries also show that the model still places rules into facts and paraphrases
their force. Adding fields does not force correct classification. It is not yet established
that a larger model or a different sampling profile will fix these failures.

Before changing models, a controlled parameter check stays within the owner-approved
8B extraction experiment: preserve prompt, schema, fixture, renderer and scoring; use
Qwen's recommended non-thinking sampling profile (temperature 0.7, top-p 0.8, top-k 20,
min-p zero). See the official [Qwen3 8B model card](https://huggingface.co/Qwen/Qwen3-8B#best-practices).
This is a hypothesis, not an acceptance claim. Predeclare seeds 105, 106 and 107: a failed
first 11-case run stops the probe; a passing first run requires independent review and
passing runs at the other two seeds before any full PDF rerun. No successful sample is
selected while hiding failed samples.

## Code gates and acceptance limits

The first implementation passed RED-to-GREEN TDD, independent code review and a fresh
isolated PostgreSQL full gate: 1390 passed, 16 skipped, 28 dependency warnings. Ruff,
Compose config, OpenAPI and diff checks passed. No frontend file changed in this spike.
The last frontend gate remains the previously recorded 148-test integrated-code check.

The sampling-profile follow-up reproduced a failing wire-parameter test before the change,
then passed 38 focused tests with one live opt-in skip. Independent code review verified
all three predeclared seeds, distinct request-policy identities and unchanged extraction
behavior. A fresh full gate passed 1391 tests with 16 skips and 28 dependency warnings;
Ruff, Compose config, OpenAPI and diff checks passed. Real sampling outcomes are recorded
separately after this clean code checkpoint.

No original36,
revised36 or actual Keycloak/BFF/browser Conversation PASS is claimed for extraction.
Keep #105 open, PR #135 draft and #116 as the final release gate. No main merge,
deployment activation, local codex/test integration or worktree removal was performed.
