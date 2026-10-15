# Issue #183: generation contract research

Date: 2026-10-14 (Asia/Ho_Chi_Minh).

Status: design research. The owner authorized a design round after the v8
observations and selected natural paraphrases with supporting source references.
The owner subsequently approved Q2–Q4, Q6 and Q9 contract simplification. PR #184
remains Draft. The v8 observations below precede that structured-contract change.

## Confirmed contract and capability

- Knora's Generation Provider receives only opaque evidence aliases and content.
  It currently returns answer text, not identified collection members. Retrieval
  Candidates have source identity, ordinal, page and offset metadata, but no list
  identity, membership or completeness declaration. Source: [provider interface](../../backend/src/knora/providers/generation.py),
  [retrieval values](../../backend/src/knora/answering/stores.py).
- Application validation checks decision/refusal shape, aliases in the selected
  evidence, uniqueness and marker order. It proves neither semantic support nor
  source order. Invalid output stays `GENERATION_OUTPUT_INVALID`; it is not a
  refusal and there is no repair retry. Source: [architecture standard](../standards/architecture.md#generation-and-citation-validation),
  [validator](../../backend/src/knora/answering/generation_validation.py).
- Citation source identities and locators are server-resolved. The bounded excerpt
  is at most 500 characters, not the full evidence. The accepted #169 design keeps
  source excerpts literal and historical derivations immutable. Source:
  [projection](../../backend/src/knora/answering/module.py), [excerpt](../../backend/src/knora/answering/excerpt.py),
  [ADR 0016](../adr/0016-layout-preserving-pdf-extraction.md),
  [owner acceptance](https://github.com/NhiBuaa/knora-agent/issues/169).
- Cloudflare documents GPT-OSS Chat Completions support since 2026-02-17:
  `/v1/chat/completions` accepts messages; `/ai/run` detects supported input forms.
  This gives no evidence that changing Knora's transport would solve #183.
  Source: [Cloudflare changelog](https://developers.cloudflare.com/workers-ai/changelog/#2026-02-17).
- The GPT-OSS model page exposes `response_format`. The JSON Mode page, updated
  2026-09-14, does not include GPT-OSS in its supported-model list and explicitly
  warns that a schema request can fail. Consequently documentation alone cannot
  establish enforcement of a proposed schema by this deployed model. Source:
  [model parameters](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/),
  [JSON Mode](https://developers.cloudflare.com/workers-ai/features/json-mode/).
- Even a correctly shaped `items` array cannot, by itself, establish that item
  text is supported by its alias, retains qualifications, or includes all members.
  This is an inference from the current data contract, not a provider guarantee.
  Knora already assigns semantic faithfulness to evaluation of the final public
  answer/citations. Source: [evaluation standard](../standards/architecture.md#evaluation).

Context7 was resolved and queried for Workers AI, then the cited official pages
were read directly. No new provider generation, model/settings change or paid
verification call was made in this research round.

## What the existing observations establish

The v8 count, general-list and short-answer turns establish selected successful
layouts. Earlier v8 turns failed and remain failed observations. These are not
evidence of universal model compliance. Source: [verification record](issue-183-list-formatting-verification.md).

Read-only inspection of trace `43b573c6-95f6-4f05-b1ce-ecb0246707d0` compared
the complete selected Chunk contents, not only Inspector previews. The generated
general list cites E1 alone. Some named parts are supported by E3 instead. The
answer also omits a source condition governing when separate tables of contents
for figures/tables/symbols should be created. This is a citation-support and
qualification problem, not merely a clipped preview or layout problem.

Evidence alias order is retrieval selection order. It is not document order.
An order check must use source positions within the same source collection;
ordering unrelated prose passages by Chunk offset does not establish a meaningful
collection. Neither the selected evidence nor its subset length proves a whole
collection is complete.

For the successful count trace `4eb09fb6-05e7-44ce-a532-c97d0924bf7e`, E2
contains seven consecutive chapter entries. The count is derived from the outline;
there is no literal source sentence saying seven chapters. Neighboring source
clauses allow merging chapters for a smaller project and splitting one chapter
when needed. A count answer must retain the suggested-outline context. Literal
member output would also preserve a source spelling variation in the last title.
An exact-span policy must therefore be approved as a UX choice, not treated as
a transparent formatting change.

Private trace projections and source contents remain in ignored local evidence;
this note does not publish raw PDF, source text, provider payload or credentials.

## Existing exploratory code

Evaluation-only code already checks selected quotes against evidence, rejects
invented quotes and composes answer text before existing marker validation.
The source-clause variant also rejects paraphrased facts. These are research
patterns, not an approved production list contract. They group by alias and
merge/deduplicate spans; they do not identify complete lists or establish all
required ordering/qualification semantics. Source:
[evidence-first probe](../../evals/runners/ollama_evidence_first_probe.py),
[source-clause projection](../../evals/runners/source_clause_projection.py).

## Alternatives for the next owner decision

Both alternatives below would require a newly approved, versioned internal
generation contract. The public answer can remain Markdown, preserving the
existing frontend, historical answers and server citation mapping. Proposed
additional checks must complement the existing validator, not weaken it.

### Structured items with supporting source references

The provider selects prose/list blocks and supplies item text plus source
references. Application code can compose one bullet per item and a bold count
phrase within paragraph text, and check reference existence and explicit source positions. It can keep
natural paraphrases and question-language prose. References are not proof of
entailment: changed meaning, omitted conditions, wrong selection or incomplete
collections still need semantic evaluation. The model can also misclassify an
enumeration as prose. These limits must not be disguised as deterministic gates.

### Source-selected items with literal output

List members are exact spans selected from supplied evidence; application code
uses those spans as the bullet text. This permits deterministic checks of text
presence, source identity and within-source position without reconstructing a
comma-separated answer. It changes UX: member text retains source language and
can be verbose or unsuitable as a standalone bullet. Exact spans can still omit
neighboring qualifications, select irrelevant text or miss members. Span
existence is not semantic relevance or collection completeness.

## Owner decision ledger

- Confirmed in this session: list item text may be naturally paraphrased and must
  carry supporting source references. Literal-only list members were not selected.
- Q2 approved: independently supported totals may be answered with incomplete
  members, with explicit disclosure of the missing portion. Unproven totals must
  not be asserted; selected-member count alone is not total-count proof.
- Q3 approved: preserve clear source order. Across sources without a common order,
  arrange sensibly without changing meaning.
- Q4 approved: prefer citation chips after the final block of contiguous content
  sharing sources, and fully cite differing sources. Citation accuracy takes
  precedence over avoiding duplicate-looking chips.
- Q6 used a bounded private Cloudflare contract: exact quotes anchored natural
  items; compose into the accepted public Markdown/unique-alias contract. No new
  dependency, model, transport, retry or historical/source-excerpt rewrite.
  [Implementation plan](issue-183-structured-list-plan.md).
- Semantic support, retained conditions and collection completeness still require
  evaluation; an existing quote or a valid schema is not proof of these properties.
- Q5's exactly six real requests completed; neither 20B nor 120B met all three
  cases. See [runtime checkpoint](issue-183-structured-runtime-status.md).
- Q6 approved paragraph/list + text + source anchors, one optional literal bold
  phrase, and removal of count/basis/witness fields. Keep Q2–Q4, GPT-OSS 20B and
  production configuration. Code/tests are authorized; further inference is not.
- Q7/Q8 completed seven physical requests: recovery ingestion succeeded with 23
  chunks; count refused with an incomplete selected outline, general list used a
  paragraph and changed a quote's capitalization, short prose changed a quote's
  capitalization. None was truncated. The general list also omitted a source
  qualification and changed its modality. [Full result](https://github.com/NhiBuaa/knora-agent/issues/183#issuecomment-6172692531).
- Q9 approved replacing quote pairs with nonempty arrays of supplied Evidence
  Aliases per paragraph/item, removing literal-quote and quote-position gates.
  Keep backend bullets/emphasis/citation grouping and public validation/mapping.
  Alias membership does not prove list classification, semantic support, count
  proof, completeness, conditions or source order. Do not introduce line catalogs
  already tried unsuccessfully, retrieval changes or semantic systems. Code/tests
  only; keep 20B/1024 and present any new runtime allowance separately.
