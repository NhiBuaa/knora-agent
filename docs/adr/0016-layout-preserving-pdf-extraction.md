# Preserve PDF lines with a new immutable extraction profile

Status: accepted for implementation through Issue #169; user acceptance pending.

The report in Issue #169 uses independently positioned/scaled PDF text objects.
Pinned pypdf 6.14.2 plain extraction joins its list into a single line before
normalization or chunking. Layout extraction retains the source's positioned lines.
The UI cannot recover those lines from an already flattened excerpt without
inventing source structure.

New HTTP PDF submissions use parser configuration
`pdf-parser-pypdf-6-14-2-layout-lines-v2`, parser version
`pypdf-6.14.2-layout-v2`, extraction options `pypdf-layout-lines-v2`, and
Chunking Configuration `chunking-m2-pdf-pypdf-6-14-2-layout-v2`.
The options select layout mode, disable synthetic vertical blank-line spacing,
and retain rotated text. Normalization, page-bounded chunking, source identity,
limits, child-process isolation and authorization remain unchanged.
These options follow [pypdf's extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html);
including rotated text can degrade layout, so no universal layout fidelity is claimed.

Workers resolve the new profile from the claimed Job's immutable parser
configuration. Legacy Jobs retain the existing plain extraction profile, including
`same_as_job` reprocessing. Historical Chunks, offsets and citations are immutable.
Submitting the same PDF and source key under the new deployed upload path reuses
the Document Version and creates a new derivation; old citation targets remain valid.
Existing `current` and `deployed` reprocess semantics retain their captured parser
configuration and are not silently upgraded.

Source Excerpt renders the server's bounded text projection as literal text with
preserved newlines. It never inserts list breaks or interprets source Markdown.
Chat renders Markdown and resolves Evidence Alias markers to the existing citation
selection. Missing/malformed/duplicate marker projections remain visible contract
errors; server generation validation remains authoritative.

The Cloudflare generation prompt moves to
`cloudflare-gpt-oss-cited-answer-v3` to request Markdown paragraphs/headings/lists
without changing grounding, citation mapping or refusal rules. The renderer adds
no executable HTML, images or external links. Complex PDF layout fidelity and
generation quality are not acceptance claims of this change.
