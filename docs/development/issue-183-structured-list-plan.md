# Issue #183 implementation plan

Owner approved natural paraphrases with source references (Q1), independently proven
totals with explicit missing-member disclosure (Q2), source order when defined
(Q3), and complete citations after contiguous supported groups (Q4), on 2026-10-14.
Continue PR #184 as Draft; Project remains In Progress.

## Bounded design

Q9 approved on 2026-10-14: Cloudflare alone returns private paragraph/list blocks.
Every paragraph or item has a nonempty `support` array of supplied Evidence Aliases.
The adapter checks shape and Evidence Set membership, preserves the received item
order, then composes the existing Markdown `GenerationResult`. The owner approved
removing Q6's literal-quote matching and quote-position order gate; no source-unit
catalog or replacement semantic gate is introduced. Other providers and the
public API remain unchanged. No additional dependency, repair retry, model change,
historical rewrite, source-excerpt change or renderer change.

An optional paragraph `bold` field selects one literal phrase occurring exactly
once in its text. The composer escapes it and adds emphasis; no count parser or
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
