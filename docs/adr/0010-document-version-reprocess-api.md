# Explicit current Document Version reprocessing

Status: accepted

Milestone 2 exposes reprocessing on the current Document Version, not on an Ingestion Job:
`POST /v1/workspaces/{workspace_id}/document-versions/{document_version_id}/reprocess`. The
authorized handler checks source availability, records audit, snapshots immutable config versions
and enqueues without reading the object; the worker performs the read and processing. A new
idempotent Job generation links to `reprocess_of_job_id`, resets its attempt budget, and never
mutates the old job. Non-current targets return a conflict, while a version replaced during
processing ends `superseded`; historical-version reprocessing is deferred.

`config_mode` is either `same_as_job` or `current`. A `same_as_job` request must explicitly supply
`config_source_job_id`; the handler must not infer a source Job from timestamp, UUID ordering,
`MAX(id)` or a hidden latest-job rule. The selected Job must exist in the authorized Workspace and
target the same Document Version. The handler snapshots that Job's exact immutable parser,
normalizer, chunking and embedding configuration version IDs. A freshly created generation records
the selected ID as `reprocess_of_job_id`. Invalid, missing or mismatched `config_source_job_id`
rejects before generation creation. A `current` request uses no source Job selector and snapshots
the active immutable configuration versions at request creation. The worker never resolves mutable
or current configuration in either mode. Equal Document Version/configuration work already
processing or succeeded remains eligible for reuse.

One logical accepted manual-reprocess request is the first processing of a scoped
`(workspace_id, reprocess operation, Idempotency-Key)`. It creates exactly one audit record. A
same-key/same-request replay creates no second audit record. A fresh key creates a new audit record
even when equal-work deduplication reuses an existing processing or succeeded generation. The audit
record, request-idempotency binding and durable created-versus-reused generation decision commit
atomically in one PostgreSQL transaction. An accepted logical reprocess request or Job binding must
not exist without its audit record.

The read-only audit projection exposes an audit event ID, Workspace ID, safe authenticated actor/key
identifier, `action = document_version.reprocess`, target Document Version ID, requested and
resolved `config_mode`, resulting Ingestion Job ID, outcome distinguishing created generation from
reused generation, database-created timestamp and any available opaque trace/correlation ID. It
never stores or exposes a raw credential or raw Idempotency-Key. Issue #19 does not require an audit
record for a request rejected before acceptance: authentication/authorization failure, invalid or
missing config mode, historical-target conflict or unavailable source. It also does not require a
public audit HTTP endpoint.
