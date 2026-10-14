# Compose generated lists from supported blocks

Status: owner-approved behavior through Issue #183 (2026-10-14); implementation
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

Cloudflare's private payload uses paragraph/list blocks with supporting
alias/quote pairs. Only whitespace variation is allowed when matching quotes to
evidence; words, case and punctuation are not rewritten. The adapter validates
shape, reference presence and declared within-alias ordering, escapes model text
as literal Markdown content, and composes server-owned bullets and emphasis of
one optional literal phrase in a paragraph.
The public Generation Result and application validator stay unchanged. Short
single facts remain prose; a single counted member also remains prose.

Q6 removes the dedicated count block and its basis/witness/member-length checks.
Count evidence, completeness, missing-member disclosure and retained conditions
remain prompt obligations and source-review acceptance criteria. Quote presence
cannot prove a count, complete collection or paraphrase entailment. This bounded
change does not implement semantic verification belonging to #153/#158.

Every required alias is retained exactly once under the existing public contract.
Repeated uses within/across blocks receive one citation cluster after the
smallest enclosing contiguous group. This may give collective attribution for
interleaved sources; internal per-item anchors remain separate. Do not fabricate
aliases or discard a needed source to reduce chips.

Other providers, retrieval, access/refusal handling, source excerpts, historical
answers and the renderer remain unchanged. Invalid private output returns the
existing `GENERATION_OUTPUT_INVALID` without repair retry. No dependency or model
change is introduced. Reference presence does not establish semantic support,
complete member selection, retained conditions or correct count proof.

Research and evidence: [contract research](../development/issue-183-provider-output-research.md),
[plan](../development/issue-183-structured-list-plan.md),
[verification](../development/issue-183-list-formatting-verification.md).
