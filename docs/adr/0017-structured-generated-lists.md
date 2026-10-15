# Compose generated lists from supported blocks

Status: owner-approved behavior, Q9 simplification, Q12 presentation selection and Q17 fixed slots through Issue #183 (2026-10-15); implementation
and runtime acceptance pending in PR #184.

The v4 provider payload lacked list structure before storage or display. Prompt
v8 produced selected successful layouts, but a general-list observation omitted
a needed evidence alias and source qualifications. Changing the renderer cannot
establish those missing generation semantics.

The owner selected natural paraphrases with source anchors. A proven total may
be stated even when member evidence is incomplete, with explicit disclosure.
An unproven total must not be asserted. Clear source-list order and important
conditions must be retained. With no common order across sources, natural
arrangement is allowed without changing meaning. Citations prefer the end of
contiguous content sharing evidence; accuracy takes precedence over avoiding
duplicate-looking chips.

Cloudflare's private payload uses fixed `before`, `items`, `after` arrays: introductory
paragraphs, one main list, and concluding paragraphs, with a nonempty array of
supporting Evidence Aliases for every paragraph or item. The adapter validates
shape and membership in the supplied Evidence Set, escapes model text as literal
Markdown content, and composes server-owned bullets and emphasis of one optional
literal phrase in a paragraph. It preserves the provider's item order.
The public answer contract and application validator stay unchanged. Short
single facts remain prose; a single counted member also remains prose.

Q6 removes the dedicated count block and its basis/witness/member-length checks.
Count evidence, completeness, missing-member disclosure, source order and retained
conditions remain prompt obligations and source-review acceptance criteria.
Alias presence cannot prove a count, complete collection or paraphrase entailment. This bounded
change does not implement semantic verification belonging to #153/#158.

Every required alias is retained exactly once under the existing public contract.
Repeated uses within/across blocks receive one citation cluster after the
smallest enclosing contiguous group. This may give collective attribution for
interleaved sources; internal per-item aliases remain separate. Do not fabricate
aliases or discard a needed source to reduce chips.

Other providers, retrieval, access/refusal handling, source excerpts, historical
answers and the renderer remain unchanged. Invalid private output returns the
existing `GENERATION_OUTPUT_INVALID` without repair retry. No dependency or model
change is introduced. Reference presence does not establish semantic support,
complete member selection, retained conditions or correct count proof.

Q9 supersedes the Q6 literal-quote and quote-position gates after the real v13
observations: capitalization differences rejected a supported short paraphrase,
while quote presence still did not establish list classification or retained
conditions. The owner approved alias-only support; the implementation removes
the now-unused `ordered` field. No quote catalog, casefold repair or list
reconstruction is introduced. This removes checks of literal span existence and within-chunk order;
the public validator does not replace them. Source-order and semantic acceptance
requirements remain unchanged. Only code/tests are authorized in Q9; further
inference requires a separately approved bounded allowance.

Q10 supplied the complete outline to v14, but the model returned only a count
paragraph and literal Markdown stars. The composer, stored Turn and browser
agreed; this was not lost renderer structure or a truncated response. The owner
approved Q12 recommendation B: a small Cloudflare-only presentation selection
request before generation. It returns only `prose`, `list`, `count_prose` or
`count_list`, without a total or answer/member content. The same question and
Evidence Set feed both requests. Zero/one evidenced member permits count prose;
the selection does not establish a proven total or complete membership.

At Q12, the selected generation schema and local gates required a list for list modes,
exclude lists for prose modes, and require an initial paragraph with an explicit
literal `bold` field for count modes. Null is allowed for an unproven total; no
count parser/proof system is added. Every mode permits the existing structured
refusal. Invalid selection stops before generation; invalid generation is an
error without another call or repair. The existing composer and source grouping
remain responsible for bullets, emphasis and citation markers.

Q12 prompt identities were `cloudflare-presentation-v1` and
`cloudflare-gpt-oss-cited-answer-v15`. Internal Generation Result/Question Trace
metadata retains safe identities, finish reasons, request IDs and reported usage
for both stages, with the selected presentation. Aggregate token fields are sums
only when both stages reported that field. Missing usage remains unknown, with no
invented zero cost. No prompt, evidence or model reasoning is added to metadata.

This adds a request and latency/quota use, retaining the existing model and
per-request cap (1024 for the configured Cloudflare runtime, not a combined turn
cap). A mistaken selector can still choose prose, and structural compliance does
not prove semantics or prevent an enumeration hidden inside an item. Q2–Q4 still
require source-based runtime review. Q12 authorizes code/tests only. It introduces
no shared Prompt Policy/Builder/Versioning architecture from separate Issue #191,
no retrieval/configuration change, provider retry, dependency or semantic judge.

## Q17: fixed slots, one main list (2026-10-15)

Q14/Q15 repeatedly returned HTTP400 before decoding. Q16 changed only the answer
schema back to v14: HTTP200, but `finish_reason=length`, 1024 completion tokens and
null answer content. This supports a problem involving the added schema
constraints without identifying an unsupported keyword; truncation is a separate
observed blocker. Neither response establishes successful generation or rendering.

The owner approved Q17 A for code/tests first: retain selection, replace the
heterogeneous block payload with fixed slots, and accept one main list per answer.
No list groups can be interleaved. The wire schema has no per-block kind, block
union, root answer/refusal `oneOf`, `contains` or `prefixItems`. Arrays remain
required in every mode so refusal can return them all empty. Cross-field local
gates enforce nonempty answer content/null refusal reason, empty refusal content,
at least two items for list modes, no items for prose, and a first `before`
paragraph with an explicit nullable literal `bold` field for count modes.

Validated slots map directly to the existing ordered paragraph/list composer;
escaping, aliases, item order and citation grouping remain unchanged. This is
structural mapping, not parsing prose into members or reconstructing lists.
Legacy block payloads are not accepted by the new private decoder; stored public
answers/traces are never re-decoded or rewritten. Prompt identities are now
`cloudflare-presentation-v1` and `cloudflare-gpt-oss-cited-answer-v16`.

This reduces contract choices; it does not establish that GPT-OSS20B/1024 finishes
or preserves evidence, conditions, totals or order. Q2–Q4 remain source-based
acceptance obligations. No new inference allowance, model/cap/config change,
retry, dependency, semantic judge or module move is authorized. #191 refactors
separately from baseline `67a149f`; #183 owns behavior/prompt/schema and runtime
acceptance. Coordinate intersecting changes through Issues before edits.

Research and evidence: [contract research](../development/issue-183-provider-output-research.md),
[plan](../development/issue-183-structured-list-plan.md),
[verification](../development/issue-183-list-formatting-verification.md).


## Q19: align wire schema and local paragraph contract (2026-10-15)

Q18 returned HTTP200/finish stop and seven items, but omitted paragraph `bold`
and embedded Markdown stars in its lead text. The v16 schema allowed omission;
the local count gate rejected it. This is a wire/local mismatch, not a renderer
finding. The owner approved requiring `bold` on every paragraph as a literal
string or null, with the existing composer and validation unchanged. Null means
no emphasis; raw Markdown remains escaped literal text, never parsed or repaired.
The answer contract identity becomes v17; selection remains presentation-v1.

This does not resolve Q18's separate omission of evidence-supplied chapter
merge/split conditions. Schema validity, alias membership and correct item shape
do not prove source fidelity. Q2–Q4 and real-provider/browser acceptance still
apply. No additional inference or rollout is authorized. #191 was notified
before shared edits and retains separate module-refactoring ownership.
