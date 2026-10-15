# Issue #183 implementation plan

Owner approved natural paraphrases with source references (Q1), independently proven
totals with explicit missing-member disclosure (Q2), source order when defined
(Q3), and complete citations after contiguous supported groups (Q4), on 2026-10-14.
Continue PR #184 as Draft; Project remains In Progress.

## Bounded design

Q17 supersedes the Q9/Q12 wire layout: Cloudflare alone returns fixed `before`,
`items`, `after` arrays, with one main list between introductory/concluding paragraphs.
Every paragraph or item has a nonempty `support` array of supplied Evidence Aliases.
The adapter checks shape and Evidence Set membership, preserves the received item
order, then composes the existing Markdown `GenerationResult`. The owner approved
removing Q6's literal-quote matching and quote-position order gate; no source-unit
catalog or replacement semantic gate is introduced. Other providers and the
public API remain unchanged. No additional dependency, repair retry, model change,
historical rewrite, source-excerpt change or renderer change.

Every paragraph must declare `bold`: a literal string selecting one phrase
occurring exactly once in its text, or null for no emphasis (Q19). The composer escapes it and adds emphasis; no count parser or
count/basis/witness fields remain. Proven totals, missing-member disclosure and
important conditions remain prompt and source-review obligations. Alias presence
and shape checks do not prove semantic support or completeness.

Each alias remains unique in the public answer, as required by the accepted
validator. Place markers after the smallest contiguous group of blocks that
contains all uses of its aliases. Lists supported by several sources receive all
those sources. If an alias recurs across separated blocks, the enclosing group
receives a collective citation cluster; do not drop a source to avoid repetition.
This preserves item anchors internally and the existing public citation mapping.

## Execution

1. Adapt behavioral tests for list/prose/emphasis composition, incomplete count
   disclosure, missing/unknown/malformed aliases and citation groups with
   mixed/repeated sources. Remove quote/order gate assertions. Run the provider
   tests before changing production code (RED).
2. Add the private Cloudflare schema/composer and adapt request/decoding (GREEN).
   Update the Cloudflare transport and Postgres HTTP fixtures to exercise the new payload. Preserve
   generic OpenAI-compatible behavior and error normalization without retries.
3. After owner approval of a new bounded runtime allowance, verify actual
   Cloudflare requests, payloads, generated Markdown, stored Turn
   and trace. Submit count, general-list and short questions through real Edge;
   inspect desktop/mobile DOM and open each citation. Recheck source conditions
   and the E3 support defect. Preserve failed observations. Q7/Q8 ended at seven
   physical requests with three nonpassing cases; Q9 provides no further inference allowance.
4. Run Ruff format/check/lint, full pytest, Compose validation and applicable repo
   checks; request code review. Commit/push, verify required CI on the exact head,
   update PR #184 and Issue #183 with results and limits. No merge/close/Done.

Semantic verification must explicitly check suggested-outline context, chapter
merge/split qualifications, conditional figures/tables/symbols sections, member
selection and source order. Fixture/prompt tests are not runtime acceptance.
Q9 authorizes code/tests only. Keep GPT-OSS 20B and production cap 1024; no further
model calls until the owner approves the concrete verification proposal.

## Q17: approved fixed slots (2026-10-15)

The owner approved A after Q16's schema-only comparison returned HTTP200 but
exhausted1024 completion tokens without answer content. Code/tests/docs only;
no further inference. One main list group per answer is an explicit approved
layout limitation. #191 may refactor separately from67a149f; #183 does not move
modules. Scope/approval were posted to both Issues before intersecting edits.

- [x] Observe RED for fixed-slot list/prose/refusal composition before code.
- [x] Replace the wire block union and selected-schema augmentation with required
  before/items/after arrays. Map validated slots to the existing composer.
  Retain empty refusal, list/prose/count gates, literal bold, aliases and escaping.
- [x] Update answer prompt/version to v16; retain presentation-v1, both-request
  metadata, model/cap/default settings and generic-provider behavior.
- [x] Adapt composer/provider/HTTP fixtures and test the one-list layout,
  before/after source validation, count lead, refusal content in every slot,
  legacy/nested payload rejection and existing no-retry/truncation gates.
- [x] Update CONTEXT, ADR0017 and runtime checkpoint.
- [ ] Finish focused/full tests, formatting/lint, OpenAPI/Compose checks and review;
  commit/push and verify exact-head required CI. Record all failures/limits.
- [ ] Publish exact new diff/results to #183/PR184/#191, keep Draft, and present a
  separately approved bounded runtime proposal. No model calls under Q17.

No promise that simplification fixes truncation or semantics. If runtime still
fails token/content checks, report and stop without adding contract complexity.

## Q12: approved presentation selection (2026-10-15)

The owner approved recommendation B after Q10 returned a paragraph-only count
answer. Implement code/tests first; no additional inference allowance. Issue #191
stays separate and unimplemented.

- [x] Add transport-level tests in `backend/test/providers/openai_compatible/`
  that first return a presentation choice, then exercise the selected output
  contract. Observe RED before changing production code.
- [x] Add private `presentation.py`: select only `prose`, `list`, `count_prose`
  or `count_list` from the same question and Evidence Set. It produces no answer,
  total or members. Count modes distinguish zero/one known member from two or
  more; they do not claim the total is proven.
- [x] Extend `answer_blocks.py` with selected schemas and matching local gates:
  prose excludes list blocks; list requires a list; count requires an initial
  paragraph with explicit literal `bold` (nullable when no proven total).
  Count-list also requires a list. Every mode allows the existing refusal.
  Reuse escaping, per-statement aliases, ordering and citation grouping.
- [x] Adapt Cloudflare in `generation.py` to two sequential requests, using the
  existing endpoint/model/per-request token setting. Invalid selection stops
  before generation; invalid generation stops after request two. No retry,
  heuristic repair, member reconstruction or semantic verifier. Generic
  OpenAI-compatible and other providers remain on their existing path.
- [x] Extend internal `GenerationResult` and `AnswerQuestion` trace metadata
  with safe stage identities/versions/finish/usage/request IDs and presentation.
  Aggregate usage only for fields reported by both requests; never invent cost
  for absent usage. Keep public answers/citations unchanged.
- [x] Update provider/Postgres fixtures. Cover list rejection of paragraph-only
  output, count lead/emphasis, incomplete proven counts, unknown totals,
  zero/one members, refusal in every mode, malformed/extra selection fields,
  unknown aliases, truncation, HTTP/timeout failures and no retries.
- [x] Update ADR0017, CONTEXT and runtime status; run focused and full pytest,
  Ruff formatting/lint, shared formatting and Compose checks; obtain review.
  Record the nonpassing full-run observations and PDF follow-up explicitly.

Publishing gate: push and verify CI required on the exact head, then publish
results/limits to #183/PR #184 Draft. The issue/PR checkpoint carries that
post-commit CI verdict; code/tests do not establish runtime acceptance.

The first selection can be wrong; structural acceptance cannot prove semantic
support, completeness, conditions or source order. Two calls increase latency and
quota use, and the 1024 cap is per request, not a combined turn cap. Keep GPT-OSS
20B, production settings and retrieval defaults. Before any real calls, present a
new bounded runtime proposal including both stages; wait for owner approval.


## Q19: required nullable paragraph emphasis (2026-10-15)

Owner approved code/tests/docs only after Q18. Remove the paragraph default so
both the wire schema and local decoder require `bold`, retaining string/null.
Composer and validation logic remain unchanged; no repair, Markdown parsing,
member inference, semantic judge or module move. Align the existing paragraph
instruction and identify the changed answer contract as v17; selection stays v1.
Coordinate through #191 before shared edits and publish the exact diff afterward.

- [x] Observe RED for schema-required bold and missing before/after paragraph fields.
- [x] Require nullable bold; adapt every provider/application/PostgreSQL fixture.
- [x] Regress the captured Q18 payload, null/literal emphasis, literal Markdown
  stars, ANSWER/refusal and no mutation/repair. Existing citation gates stay active.
- [ ] Complete fresh formatting/lint/full suite/review and exact-head CI; record limits.
- [ ] Report read-only Billing/usage observations separately from unproven actual cost.
- [ ] Propose a separately approved runtime only after fail-closed preflight and
  an isolated OAuth arrangement are reviewable. Never replace primary frontend.

Q18's source-supplied merge/split conditions were omitted. That semantic failure
remains unresolved by Q19. No inference, retry, model/token/default changes,
production rollout, merge, issue closure or Done transition is authorized.
