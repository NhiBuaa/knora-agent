# Isolated PDF extraction with versioned resource budgets

Status: accepted

The `pypdf` adapter runs in a child process so Knora can enforce a hard extractor RSS/container
ceiling, kill a timed-out or over-budget process, and keep the worker parent healthy. Milestone 2
starts with 25 MiB raw input, 500 pages, 4 MiB per-page and 64 MiB aggregate decompressed content
streams, and 30 seconds for inspection/extraction under a 256 MiB hard memory ceiling. These
limits are versioned ingestion configuration. Budget violations are terminal with an internal
reason; infrastructure failure and process eviction remain bounded policy inputs, while loss of a
worker is durably observed only as lease expiry. Failed jobs retain source and failure evidence but cannot activate or expose partial
derivations.
