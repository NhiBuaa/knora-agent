# Separate request idempotency, derivation deduplication and processing generations

Status: accepted

Milestone 2 scopes `Idempotency-Key` by Workspace and operation, retains it for 24 hours, and binds
it to an immutable content/config fingerprint; a conflicting reuse returns
`IDEMPOTENCY_KEY_CONFLICT`. Database uniqueness protects concurrent requests. The fingerprint
uses canonical source identity, raw SHA-256 and immutable parser/normalizer/chunking/embedding
configuration version IDs. Document Version reuse is separate from request idempotency, and
manual reprocessing creates an immutable new job generation linked by `reprocess_of` rather than
mutating a failed job or automatically replacing a newer version.
