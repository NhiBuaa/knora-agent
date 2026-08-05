# Separate PDF source identity from extraction and vector derivations

Status: accepted

Milestone 2 identifies a PDF Document Version by `(document_id, raw_sha256)` and its immutable
Original Source Object. Parser, normalizer, chunker and embedding versions belong to the derivation
target, not the source revision, so the same bytes under new configurations reuse the Document
Version while creating new Chunk/Embedding Sets. Milestone 1 text keeps its normalized-content
identity. This separation lets durable upload commit the source version before PDF extraction and
keeps reprocessing from manufacturing source history.
