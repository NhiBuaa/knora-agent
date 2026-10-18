# Compose generated lists from supported blocks

Status: owner-approved behavior through Issue #183, including Q9 simplification,
Q12 presentation selection, Q17 fixed slots, Master section 4.4 selected-condition
retention and section 4.7 count-intent simplification (2026-10-18). Section 4.4's
offline gates passed at1477838; section 4.7 is now implemented with technical
verification in progress. Runtime acceptance remains pending in PR #184.

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

## Q20/P2: explicit condition placement policy (2026-10-16)

Offline replay of Q18 and Q20 proved that the supplied Evidence Set contained
the chapter merge/split qualifications, while the v17 answer payload omitted
them before composition. Q20 finished `stop` with 548 completion tokens and its
payload matched the v17 schema; this is a generation-fidelity omission, not a
renderer or observed truncation failure. The owner approved one bounded v18
policy clarification: for lists, keep relevant conditions on an individual
member in that item; put relevant shared conditions not already stated in
`before` or `items` into `after` with supporting aliases; conditions governing
the total, member inclusion or applicability remain within question scope.

This is a generation instruction, not a semantic validator or guarantee. The
schema, selector, composer, citation/refusal validation, model, token cap and
retrieval remain unchanged. A runtime candidate must still compare all claims
with the supplied source; a passing shape/alias check does not prove meaning.

## Master section 4.4: retain selected shared conditions (2026-10-17)

P4 on v18 again omitted both supplied merge/split qualifications before composition,
despite a valid answer shape, `finish_reason=stop` and 922 completion tokens. The
payload, composer, Turn and trace agreed; this is not evidence of renderer loss
or observed truncation. The model's internal reason for omission remains unknown.

The owner approved the exact three-file behavior diff in the sole
[Master section 4.4](../superpowers/plans/2026-10-16-issue-183-master-plan.md#44-proposed-retention-of-selected-shared-conditions--approved-for-offline-implementation).
A new [replacement technical overlap ACK from #191](https://github.com/NhiBuaa/knora-agent/issues/191#issuecomment-6233675217)
permits offline implementation without waiting for the separate extraction.
The selector now requires `conditions`, containing shared list qualifications as
literal `text` and supporting aliases. It cannot generate the total/member collection;
conditions only applying to one member remain that item's responsibility.
Prose/count prose must return an empty conditions array.

Before request two, reuse the paragraph, one-line text and alias checks. The
second user-message JSON retains the original question/evidence and adds
`retained_conditions` as generated data, never as system instructions or new
evidence. The answer wire schema stays unchanged. Existing ANSWER/REFUSAL/list/count
gates run before the composer appends selected paragraphs after model `after`
paragraphs, retaining text, order and citations. Valid REFUSAL returns no answer or
citations without appending notes. Invalid output remains an error without repair.

The identities become `cloudflare-presentation-conditions-v2` and
`cloudflare-gpt-oss-cited-answer-v19`. This retains two generation calls, the
existing model/per-request cap and safe stage metadata; no module moves, shared
serializer change, dependency or semantic judge is introduced. Other providers,
public citation/refusal/access and storage contracts, source excerpts and historical
answer content stay unchanged. Newly generated Turn/trace answer content includes
selected conditions after composition. #191 must later adapt extracted policy/builder/parity to the accepted
actual upstream candidate, after #183 acceptance and PR184 merge.

This only guarantees transfer of conditions already selected and structurally
validated. The selector can still omit or misstate a condition or cite an alias
that does not support its meaning. Notes always appear at the end; duplicates or
conflicts are not automatically removed and remain acceptance failures. More
selector output/answer input may increase tokens and latency; provider schema
compatibility and semantic correctness are unverified. Offline tests/CI cannot
establish AC2 or authorize inference, OAuth, production changes or merge.

## Master section 4.7: separate count intent from answer format (2026-10-18)

The v19 recovery selected count prose despite supplied evidence identifying seven
members. The section 4.6 diagnostic did not reproduce the unavailable historical
answer error, but again returned prose without the members or shared qualifications.
The observed list/prose restriction couples an incorrect first-stage choice to both
empty items and empty conditions; the model's internal reason remains unknown.

The owner approved the exact three-module section 4.7 diff after renewed #191
overlap ACK. This supersedes the four-way presentation choice and mode/items
agreement gate described above. The selector returns strict `count_question` and
relevant shared conditions independently of eventual answer format, without totals
or member collections. Stage two decides whether to return items; a nonempty list
still requires at least two items, and a count answer requires an initial paragraph.
Every paragraph still declares nullable literal `bold`; aliases, escaping, refusal,
answer wire schema and public validation remain unchanged.

Selected notes now append after any valid ANSWER's concluding paragraphs, including
prose. Valid REFUSAL still returns before notes are appended. Conditions are checked
before request two and remain generated user data, never new evidence or system
instructions. No legacy enum fallback/conversion or semantic repair is introduced.
Identities become `cloudflare-count-conditions-v3` and
`cloudflare-gpt-oss-cited-answer-v20`, retaining two calls and the same model/cap.

This removes the observed routing coupling, not the semantic acceptance obligation.
A wrong prose answer or unnecessary list may now pass structure; count intent,
conditions and members can still be wrong, incomplete, duplicated or contradictory.
Only selected-note transfer is guaranteed. No provider compatibility, token/latency
or source-fidelity claim follows from offline mocks. A changed candidate needs
separate runtime approval and fresh guard fingerprints; historical grants stay closed.
