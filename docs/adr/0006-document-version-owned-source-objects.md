# Document Version-owned original PDFs

Status: accepted

The original PDF is an immutable source artifact owned by its Document Version, not by the
terminal lifecycle of an Ingestion Job. It remains available for reprocessing, citation viewing,
debugging and reproducibility until version retention permits hard deletion; superseded versions
respect citation/trace/evaluation retention, while failed uploads use bounded diagnostic
retention. Only staging, temporary and partial derivation objects are terminal-job cleanup targets.
The S3-compatible `ObjectStore` is streaming and minimal (`put_stream`, `open_read`, `head`,
idempotent `delete`), and an orphan sweeper reconciles the unavoidable database/object-store
transaction gap.

## Object Lifecycle Retention decision

A Failed-upload Diagnostic Artifact is only a source or staging object from an upload that failed
before the object became the Original Source Object of a committed Document Version. It is retained
for at least 24 hours from the Knora-owned durable timestamp recorded when it is classified as a
failed-upload diagnostic artifact. It is ineligible for automatic cleanup before that time and
eligible, but not required to be deleted immediately, afterwards.

The 24-hour diagnostic-retention policy is independent of the Idempotency Record's 24-hour
retention. It neither derives from nor shares lifecycle authority with request idempotency.

An Original Source Object remains owned by its Document Version even if the associated Ingestion
Job later fails, exhausts retries, reaches a resource limit, is superseded, or reaches another
terminal outcome. It is never a terminal-job cleanup target. It may be deleted only through an
approved hard-deletion path after authoritative checks establish that no current or active
ownership constraint and no citation, trace, evaluation, or other version-retention reference
blocks deletion.

Cleanup is asynchronous and idempotent. A cleanup failure is retried independently and cannot
change the submission or ingestion outcome. A sweeper or cleanup worker must revalidate, immediately
before a destructive delete, the authoritative database ownership/reference state and Workspace
scope; a stale discovery result is insufficient. If reconciliation attached the object as a retained
Original Source Object after discovery, deletion is suppressed. The process must never cross a
Workspace boundary.
