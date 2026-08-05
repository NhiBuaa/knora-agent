# Page-bounded block-aware PDF chunking

Status: accepted

Milestone 2 keeps each PDF Chunk within one physical page to make citation provenance and
reproducibility stable. Normalized page text is split into deterministic blocks and packed toward
500 tokens with at most 75-token overlap; only an oversized block is hard-split with deterministic
windows capped at 650 tokens. Tokenizer identity, normalized-text counts, half-open character
offsets, page number, ordinal and content hash are persisted in versioned configuration/Chunk
metadata. Cross-page merging is deferred to Milestone 3 evaluation of page-break failure cases.
