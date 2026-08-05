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
