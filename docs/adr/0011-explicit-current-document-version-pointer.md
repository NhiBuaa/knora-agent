# Explicit current Document Version separate from served Embedding Set

Status: accepted

Knora adds an explicit `Document.current_document_version_id` pointer and sequential
`version_number`; current source identity is not inferred from timestamps or IDs. Once the
Original Source Object and checksums are confirmed, the version record and pointer commit
atomically before chunking/embedding, while `active_embedding_set_id` remains the independent
retrieval pointer. This permits a new or failed source version to coexist with an older served
derivation, protects activation with lease/fencing plus current-pointer CAS, and makes reprocess
of only the current version unambiguous.
