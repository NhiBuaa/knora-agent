# Explicit current Document Version reprocessing

Status: accepted

Milestone 2 exposes reprocessing on the current Document Version, not on an Ingestion Job:
`POST /v1/workspaces/{workspace_id}/document-versions/{document_version_id}/reprocess`. The
authorized handler checks source availability, records audit, snapshots immutable config versions
under `same_as_job` or `current`, and enqueues without reading the object; the worker performs the
read and processing. A new idempotent job generation links to `reprocess_of_job_id`, resets its
attempt budget, and never mutates the old job. Non-current targets return a conflict, while a
version replaced during processing ends `superseded`; historical-version reprocessing is deferred.
