# Separate PDF source identity from extraction and vector derivations

Status: accepted

Milestone 2 identifies a PDF Document Version by `(document_id, raw_sha256)` and its immutable
Original Source Object. Parser, normalizer, chunker and embedding versions belong to the derivation
target, not the source revision, so the same bytes under new configurations reuse the Document
Version while creating new Chunk/Embedding Sets. Milestone 1 text keeps its normalized-content
identity. This separation lets durable upload commit the source version before PDF extraction and
keeps reprocessing from manufacturing source history.

The Cloudflare retained-corpus re-index follows the same identity rule: reuse the
current Document Version and Chunk Set, create or verify the distinct immutable
Cloudflare Embedding Set, and switch active pointers only after complete coverage
of the selected quiesced population. A reviewed terminal no-text PDF with its
original source retained has no Chunk Set to embed and may be explicitly excluded.
The later, separately confirmed cleanup removes obsolete vector rows without
deleting source history or derivation metadata.
