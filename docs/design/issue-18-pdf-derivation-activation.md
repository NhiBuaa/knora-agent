# Issue #18 PDF derivation and activation design

Status: Approved implementation design (2026-08-09)  
Source: [Issue #18](https://github.com/NhiBuaa/knora-agent/issues/18)  
Depends on: [Issue #17 worker coordination design](issue-17-worker-coordination.md)

## Decision

Issue #18 specializes the existing generic worker-coordination seam. It does not add a second
worker orchestrator, a generic persistence API, or a PDF path in synchronous
`IngestDocument`.

`ProcessIngestionJob[PdfDerivationSuccess]` remains the deep module with one external operation:

```python
result = processor.run_once(worker_id)
```

The concrete handler performs only repeatable work outside a database transaction: it verifies
the immutable Original Source Object metadata, streams the object to `PdfTextExtractor`, validates
the pinned extraction identity, calls `EmbeddingProvider`, and validates the provider response.
The existing PostgreSQL ingestion-job adapter owns the one fenced finalization transaction that
creates or reuses the derivation, conditionally activates it, and records the terminal job and
attempt outcome.

## Concrete immutable success value

`knora/ingestion/job_processing.py` gains the data-only value passed through the existing
`WorkHandler`, `WorkSucceeded`, `ProcessIngestionJob`, and
`IngestionJobCoordinationStore` type parameter:

```python
@dataclass(frozen=True, slots=True)
class PdfDerivationSuccess:
    extraction: PdfExtractionResult
    vectors: tuple[tuple[float, ...], ...]
    embedding_provider: str
    embedding_model: str
```

`PdfExtractionResult` and its page/chunk values are already frozen data. Vectors are a tuple of
tuples, so the payload has no mutable mapping, callback, ORM row, database session, transaction,
object-store handle, or persistence capability. Provider request IDs, usage and cost stay in
internal telemetry; they are not a success-finalization contract.

The handler constructs this value only after all of these checks pass:

1. `ObjectStore.head` exactly matches the claimed Workspace, opaque object key, SHA-256, byte
   size and media type. `IngestionWork` therefore gains the claimed source SHA-256 and byte size;
   an object-store mismatch becomes a typed terminal input failure.
2. The streaming `open_read` result is passed to `PdfTextExtractor`; extraction must have the
   exact parser, extraction-options, normalizer, tokenizer and chunking-policy identities from
   the immutable selected PDF profile and must contain the deterministic page-bounded chunks.
3. The handler calls `EmbeddingProvider.embed` outside a database transaction with exactly the
   chunks' ordered content and the immutable selected `EmbeddingConfiguration`. It requires one
   vector per Chunk, each vector at the configured dimension, and an exact provider/model match.

The selected PDF and embedding profiles are composed once at worker bootstrap from the supported
immutable profile, then matched against the IDs already present in `IngestionWork`. The handler
never asks for a mutable “current” configuration. A later configuration version requires an
explicit additional immutable profile and submission identity; it cannot silently change a job.

`PdfDerivationHandler` is an internal implementation of `WorkHandler[PdfDerivationSuccess]`.
It depends on the real existing seams (`ObjectStore`, `PdfTextExtractor`, and
`EmbeddingProvider`), which have production and deterministic/test adapters. It owns no
lifecycle mutation, retry policy, or activation decision.

## Finalization transaction and responsibility split

`PostgresIngestionJobStore` specializes
`IngestionJobCoordinationStore[PdfDerivationSuccess]`. Its `finalize_success` replaces the
current deliberate Issue #17 invariant error only for `PdfDerivationSuccess`; other success
payloads remain unsupported by this production adapter.

The transaction locks in the established order:

```text
ingestion_jobs -> current ingestion_job_attempts -> documents -> derivation/activation rows
```

After job and open-attempt locks, it samples fresh PostgreSQL time and first proves the claim is
current, processing, owned by the supplied `worker_id + lease_version`, and unexpired. A stale
claim returns `Fenced` before any transition-legality check. Only then may it lock the target
Document and related source/version/configuration/derivation rows.

Inside the same short transaction the store:

1. Reconciles the transition operation ID and immutable request fingerprint before redoing work.
   A replay returns the persisted `FinalizationApplied` or `Fenced` result and never repeats
   extraction, embedding, a CAS, or a provider call.
2. Revalidates that the job, Original Source Object, Document Version, Document and all pinned
   parser/normalizer/chunking/embedding identities agree and are owned by the claimed Workspace.
3. Creates or reuses the complete PDF `ChunkSet` and its immutable PDF Chunks, then creates or
   reuses the matching complete `EmbeddingSet` and Chunk embeddings. It validates deterministic
   ordinals, content checksums, page locator/offset values, vector order/count/dimension, and
   provider/model/configuration compatibility before a set is considered complete.
4. Applies activation only when the target version is still
   `Document.current_document_version_id`. The conditional update also validates the completed
   set's Document, Workspace and embedding-configuration ownership. A zero-row activation CAS
   does not roll back a valid historical derivation; instead, in this same transaction it closes
   the attempt and transitions the job to terminal `superseded`, recording replacement metadata
   when it is available. It does not consume another retry.
5. On a successful CAS, marks the Embedding Set complete, updates the active pointer and its
   embedding configuration, closes the attempt as succeeded, clears current lease/attempt fields,
   records the transition operation, and sets `ingestion_jobs.status = succeeded` atomically.

No transaction covers object I/O, extraction, chunking or provider calls. Any failure before the
commit rolls back all newly inserted derivation rows and leaves the prior active set untouched.
The success response is therefore impossible to observe without the committed complete active
derivation. A conflict discovered while inserting an immutable derivation is reconciled by reading
the unique existing chain and validating compatibility; it never exposes an incomplete set.

## PDF persistence migration

Issue #18 extends the existing derivation schema rather than creating parallel PDF tables.

- `chunk_sets` records the pinned parser and normalizer configuration IDs in addition to its
  chunking configuration. Its uniqueness is the full PDF derivation identity:
  `(document_version_id, parser_configuration_id, normalizer_configuration_id,
  chunking_configuration_id)`.
- `chunks` gains canonical PDF provenance: `page_start`, `page_end`, `start_offset`, and
  `end_offset`. Page boundaries are 1-based physical page indices; offsets are half-open in the
  normalized page text. For the initial page-bounded policy, `page_start == page_end`.
  Existing line columns remain derived compatibility metadata and are never the sole PDF locator.
- Migration constraints reject invalid page ranges and offsets, and enforce that an active
  embedding set is complete and belongs to the same Document/Workspace as its Document pointer.
  The migration preserves valid legacy Markdown rows; nullable/backfill/validate/tighten steps
  distinguish those rows from required Issue #18 PDF provenance.

The persistence implementation must not rely only on application assertions or on a partial unique
index for these ownership and completeness rules. Foreign keys, ownership-safe predicates, and
database constraints/trigger checks provide the final guard.

## Failure and observable-result mapping

The handler maps only its typed failures into the existing closed `HandlerFailureKindV1` values.
The Issue #17 `CauseMappingV1` and `RetryPolicyV1` remain the sole owners of canonical causes and
retry decisions. Provider timeout/429/5xx, transient object/database dependencies, extractor
eviction, and unexpected worker errors become retryable facts where the existing policy says so.
Malformed, encrypted, textless, over-budget, pinned-configuration, object-metadata, vector-count,
dimension, provider-identity, and deterministic parser/chunk failures are terminal typed facts.
Raw provider, SQL, PDF, object-key, and exception text remain telemetry-only.

The finalization adapter returns only the existing typed values:

- completed activation: `FinalizationApplied` -> `Succeeded`;
- stale target CAS: `FinalizationApplied` -> `Superseded`;
- stale/expired lease: `Fenced` -> `LeaseLost`;
- current but illegal state: `InvalidTransition` -> coordination invariant handling.

It does not add a seventh lifecycle result or classify an indeterminate database commit as a
handler failure. Ambiguous finalization remains `CoordinationOutcomeIndeterminate` until its
operation-ID read-back is authoritative.

## Verification surfaces

Application tests cross `ProcessIngestionJob.run_once` with a concrete
`PdfDerivationSuccess` and deterministic ObjectStore, extractor and Embedding Provider adapters.
They cover metadata mismatch, pinned-profile mismatch, vector validation, success, retryable and
terminal failure mapping, and lease loss without outcome persistence.

Focused PostgreSQL tests cover the finalization seam with real PostgreSQL: one complete active
derivation and succeeded job commit; rollback leaves no partial PDF chain; duplicate delivery
reuses a compatible chain; a newer current version yields `superseded`; stale fencing yields
`Fenced`; and foreign Document/Workspace or incomplete-set activation is impossible. Existing
HTTP upload/poll/question tests prove that only the activated complete set becomes answerable.

## Rejected alternatives

1. **Put a session, persistence callback, or generic mapping in the success value.** This would
   allow the handler to cross the persistence seam and make `WorkSucceeded` untyped in practice.
   It is rejected because it weakens locality and violates the Issue #17 generic-success contract.
2. **Let the handler persist chunks/activation.** This mixes remote I/O, transaction ownership,
   fencing, and retry policy in one shallow worker implementation. It is rejected because the
   Postgres adapter must own reconciliation and atomicity.
3. **Mark a job succeeded, then activate in a second transaction.** This could make polling report
   success for invisible or uncommitted knowledge. It is rejected because terminal success and
   activation are one atomic outcome.

## Compatibility and frontier

This design preserves Milestone 1 synchronous ingestion and the Issue #17 public
`ProcessIngestionJob.run_once` interface. It introduces no new ticket, no new generic persistence
method, and no reopening of `grill-with-docs`: the implementation details close the approved
#14/#17 seams without contradicting an authoritative artifact.

The next `feature-delivery` transition is to prepare the locked manual-acceptance guide for Issue
#18. Implementation waits for that guide's explicit human approval.
