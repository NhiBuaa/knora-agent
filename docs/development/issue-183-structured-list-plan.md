# Issue #183 implementation plan

Owner approved natural paraphrases with source anchors (Q1), independently proven
totals with explicit missing-member disclosure (Q2), source order when defined
(Q3), and complete citations after contiguous supported groups (Q4), on 2026-10-14.
Continue PR #184 as Draft; Project remains In Progress.

## Bounded design

Q6 approved on 2026-10-14: Cloudflare alone returns private paragraph/list blocks. Every statement
or item has an alias and a supporting quote from the supplied evidence, permitting
only whitespace variation in matching (the source text itself stays immutable).
The adapter checks shape, quote presence and declared within-alias list order,
then composes the existing Markdown `GenerationResult`. Other providers and the
public API remain unchanged. No additional dependency, repair retry, model change,
historical rewrite, source-excerpt change or renderer change.

An optional paragraph `bold` field selects one literal phrase occurring exactly
once in its text. The composer escapes it and adds emphasis; no count parser or
count/basis/witness fields remain. Proven totals, missing-member disclosure and
important conditions remain prompt and source-review obligations. Quote presence
and shape checks do not prove semantic support or completeness.

Each alias remains unique in the public answer, as required by the accepted
validator. Place markers after the smallest contiguous group of blocks that
contains all uses of its aliases. Lists supported by several sources receive all
those sources. If an alias recurs across separated blocks, the enclosing group
receives a collective citation cluster; do not drop a source to avoid repetition.
This preserves item anchors internally and the existing public citation mapping.

## Execution

1. Add failing behavioral tests for list/prose/emphasis composition, incomplete count
   disclosure, missing/unknown anchors, reversed ordered members and citation
   groups with mixed/repeated sources. Run the provider test file (RED).
2. Add the private Cloudflare schema/composer and adapt request/decoding (GREEN).
   Update the Cloudflare transport fixture to exercise the new payload. Preserve
   generic OpenAI-compatible behavior and error normalization without retries.
3. After owner approval of a new bounded runtime allowance, verify actual
   Cloudflare requests, payloads, generated Markdown, stored Turn
   and trace. Submit count, general-list and short questions through real Edge;
   inspect desktop/mobile DOM and open each citation. Recheck source conditions
   and the E3 support defect. Preserve failed observations.
4. Run Ruff format/check/lint, full pytest, Compose validation and applicable repo
   checks; request code review. Commit/push, verify required CI on the exact head,
   update PR #184 and Issue #183 with results and limits. No merge/close/Done.

Semantic verification must explicitly check suggested-outline context, chapter
merge/split qualifications, conditional figures/tables/symbols sections, member
selection and source order. Fixture/prompt tests are not runtime acceptance.
Q6 authorizes code/tests only. Keep GPT-OSS 20B and production cap 1024; no further
model calls until the owner approves the concrete verification proposal.
