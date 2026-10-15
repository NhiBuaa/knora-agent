# Compose generated lists from supported blocks

Status: owner-approved behavior and Q9 simplification through Issue #183 (2026-10-14); implementation
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

Cloudflare's private payload uses paragraph/list blocks with a nonempty array of
supporting Evidence Aliases for every paragraph or item. The adapter validates
shape and membership in the supplied Evidence Set, escapes model text as literal
Markdown content, and composes server-owned bullets and emphasis of one optional
literal phrase in a paragraph. It preserves the provider's item order.
The public Generation Result and application validator stay unchanged. Short
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

Research and evidence: [contract research](../development/issue-183-provider-output-research.md),
[plan](../development/issue-183-structured-list-plan.md),
[verification](../development/issue-183-list-formatting-verification.md).
