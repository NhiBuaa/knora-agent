
# Milestone 2 Module Seams

Status: Approved
Source: [Milestone 2 specification and design ledger](https://github.com/NhiBuaa/knora-agent/issues/14)

Milestone 2 extends the existing capability-first layout. It does not add a top-level
`milestone-2` package. Existing Milestone 1 interfaces remain stable while PDF submission,
processing, storage, and worker behavior enter through explicit modules and adapters.

## Application modules

### Ingest Document

`IngestDocument` remains the synchronous Markdown and plain-text module:

```text
IngestDocument.execute(command, principal) -> IngestionResult
```

Its implementation remains in `knora/ingestion/module.py`. PDF submission must not add format
switching, background work, or ObjectStore behavior to this module.

### Ingestion Jobs

`IngestionJobs` owns durable submission, status lookup, and reprocessing:

```text
IngestionJobs.submit_pdf(command, principal) -> PdfSubmissionResult
```

Status and reprocess entry points are added to the same module only when their approved tickets
require them. The module hides request idempotency, content/configuration deduplication, source
version creation, current-version updates, job creation, and compensation for an unreferenced
uploaded object.

The interface and implementation stay in `knora/ingestion/jobs.py`. HTTP handlers translate
transport input and delegate to this module. They do not query PostgreSQL tables or construct
object keys.

### Process Ingestion Job

`ProcessIngestionJob` will own worker orchestration when Issues #17 and #18 require it. It will
coordinate claims, fenced leases, ObjectStore reads, extraction, chunking, embedding, persistence,
activation, retries, and cleanup outcomes.

Its target location is `knora/ingestion/job_processing.py`. Do not create the file before a ticket
needs it.

## PDF extraction seam

Issue #16 places the `PdfTextExtractor` interface and PDF result/configuration types in
`knora/ingestion/pdf.py`. The pinned `pypdf` implementation will be an adapter in
`knora/adapters/pdf/pypdf.py`.

The adapter will hide child-process execution, parser options, resource enforcement, and parser
error translation. Deterministic normalization and page-bounded chunking remain behind the PDF
interface. `knora/ingestion/processing.py` remains the Milestone 1 text/Markdown processor and must
not become a format switchboard.

## Persistence and storage seams

### Synchronous derivation persistence

`knora/ingestion/store.py` remains the persistence interface for synchronous Milestone 1
derivations. Its PostgreSQL adapter remains
`knora/adapters/postgres/ingestion_store.py`.

### Ingestion Job persistence

The PostgreSQL adapter for durable Ingestion Jobs is
`knora/adapters/postgres/ingestion_job_store.py`. It owns submission transactions now and will
gain claim, lease, retry, and status projections only through their approved tickets.

`knora/adapters/postgres/tables.py` remains the shared SQLAlchemy table registry. Split it only
when a later ticket demonstrates that one file obscures ownership or migration safety.

### ObjectStore

The `ObjectStore` interface lives in `knora/ingestion/object_store.py`. Callers receive opaque
keys and cannot construct storage paths.

Adapters live under `knora/adapters/object_store/`:

- `filesystem.py` supports local development and deterministic tests.
- `s3.py` is reserved for the S3-compatible adapter introduced by Issue #20.

Do not create `s3.py` before Issue #20 requires it.

## HTTP adapters

HTTP routes and schemas remain under `knora/adapters/http/`. The document upload route selects the
synchronous text module or the durable PDF module from transport metadata, then delegates. It owns
HTTP status selection and serialization, not application rules or persistence.

## Target directory ownership

```text
backend/
├── migrations/
│   └── versions/
├── src/knora/
│   ├── ingestion/
│   │   ├── interface.py
│   │   ├── module.py
│   │   ├── processing.py
│   │   ├── store.py
│   │   ├── jobs.py
│   │   ├── job_processing.py        # create when Issues #17/#18 need it
│   │   ├── object_store.py
│   │   └── pdf.py
│   └── adapters/
│       ├── http/
│       │   ├── routes.py
│       │   └── schemas.py
│       ├── postgres/
│       │   ├── tables.py
│       │   ├── ingestion_store.py
│       │   └── ingestion_job_store.py
│       ├── object_store/
│       │   ├── filesystem.py
│       │   └── s3.py                # create when Issue #20 starts
│       └── pdf/
│           └── pypdf.py
└── test/
    ├── ingestion/
    └── adapters/
        ├── http/
        ├── postgres/
        ├── object_store/
        └── pdf/
```

Tests mirror the module that owns the behavior. Application behavior is tested through the
application interface. Adapter-specific contract tests stay under the matching adapter directory.
PostgreSQL atomicity and concurrency tests may use focused persistence projections where the
approved acceptance seam requires them.

## Dependency direction

- `domain` imports no FastAPI, SQLAlchemy, storage SDK, parser library, or model SDK.
- `ingestion` owns application interfaces and may depend on domain and provider interfaces.
- `adapters` depend on application interfaces. Application modules do not import adapters.
- `main.py` and `bootstrap.py` compose adapters with application modules.

Avoid generic `services`, `repositories`, `utils`, `helpers`, and `common` directories. Add a new
directory only when an approved ticket gives it one clear owner.
