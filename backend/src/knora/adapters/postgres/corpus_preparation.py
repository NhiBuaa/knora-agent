"""Exact retained-version admission, using the existing fenced PDF finalizer."""

from contextlib import contextmanager
from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import func, select, text

from knora.adapters.postgres.evaluation_datasets_tables import (
    DatasetDraftTable,
    DatasetSourceTable,
    EvaluationGoldVersionTable,
    ExtractionSnapshotTable,
)
from knora.adapters.postgres.ingestion_jobs.coordination import (
    PostgresIngestionJobCoordinationStore,
)
from knora.adapters.postgres.ingestion_jobs.lifecycle import PostgresObjectLifecycleStore
from knora.adapters.postgres.ingestion_jobs.submission import PostgresPdfSubmissionStore
from knora.adapters.postgres.tables import (
    ChunkingConfigurationTable,
    ChunkSetTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    WorkspaceIdentityTable,
    WorkspaceTable,
)
from knora.evaluation.contracts import FrozenDataset, digest_json
from knora.ingestion.job_processing import (
    ClaimedAttempt,
    FencingToken,
    FinalizationApplied,
    TransitionOperationId,
)
from knora.ingestion.jobs import PreparedPdfSubmission
from knora.ingestion.object_store import ObjectMetadata


def _require(condition):
    if not condition:
        raise ValueError("CORPUS_STATE_CHANGED")


def _locked(session, table, identity):
    row = session.scalar(
        select(table)
        .where(table.id == identity)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    _require(row is not None)
    return row


class PostgresCorpusPreparationStore:
    def __init__(self, session_factory, *, database_now=None):
        self._sessions = session_factory
        self._now = database_now or (
            lambda s: s.execute(select(func.clock_timestamp())).scalar_one()
        )

    @staticmethod
    def _bound_transaction(session):
        # Bound each PostgreSQL wait; durable stop intent is recorded outside the mutation lock.
        if session.bind.dialect.name == "postgresql":
            session.execute(text("SET LOCAL statement_timeout = '2000ms'"))
            session.execute(text("SET LOCAL lock_timeout = '1000ms'"))

    def _load(self, session, plan, *, target=None, poststate=False):
        ref = plan.frozen.reference
        workspace = _locked(session, WorkspaceTable, ref.workspace_id)
        _require(not workspace.archived and workspace.revision == plan.workspace_revision)
        owner = _locked(session, WorkspaceIdentityTable, workspace.owner_identity_id)
        _require((owner.issuer, owner.subject) == (plan.owner_issuer, plan.owner_subject))
        draft = _locked(session, DatasetDraftTable, ref.dataset_id)
        _require(
            draft.workspace_id == ref.workspace_id
            and draft.status == "FROZEN"
            and draft.revision == plan.dataset_revision
            and draft.reference == asdict(ref)
        )
        gold = session.scalar(
            select(EvaluationGoldVersionTable)
            .where(
                EvaluationGoldVersionTable.workspace_id == ref.workspace_id,
                EvaluationGoldVersionTable.dataset_id == ref.dataset_id,
                EvaluationGoldVersionTable.version == ref.version,
            )
            .with_for_update()
        )
        _require(
            gold is not None
            and gold.digest == ref.digest
            and FrozenDataset.from_json(gold.frozen_json).to_json() == plan.frozen_json
        )
        rows = []
        for pin in sorted(plan.sources, key=lambda p: p.document_id):
            source = _locked(session, DatasetSourceTable, pin.source_id)
            _require(
                (
                    source.workspace_id,
                    source.dataset_id,
                    source.document_id,
                    source.document_version_id,
                    source.raw_sha256,
                    source.byte_size,
                    source.object_key,
                    source.original_source_object_id,
                    source.snapshot_id,
                    source.status,
                )
                == (
                    ref.workspace_id,
                    ref.dataset_id,
                    pin.document_id,
                    pin.document_version_id,
                    pin.raw_sha256,
                    pin.byte_size,
                    pin.object_key,
                    pin.original_source_object_id,
                    pin.snapshot_id,
                    "READY",
                )
            )
            snapshot = _locked(session, ExtractionSnapshotTable, pin.snapshot_id)
            _require(
                snapshot.workspace_id == ref.workspace_id
                and snapshot.source_id == pin.source_id
                and snapshot.extraction_sha256 == pin.snapshot_sha256
                and snapshot.configuration_sha256 == pin.snapshot_configuration_sha256
            )
            document = _locked(session, DocumentTable, pin.document_id)
            _require(
                document.workspace_id == ref.workspace_id and document.source_key == pin.source_key
            )
            version = _locked(session, DocumentVersionTable, pin.document_version_id)
            _require(
                (version.document_id, version.raw_sha256, version.media_type)
                == (pin.document_id, pin.raw_sha256, "application/pdf")
            )
            original = _locked(session, OriginalSourceObjectTable, pin.original_source_object_id)
            _require(
                (
                    original.workspace_id,
                    original.document_version_id,
                    original.object_key,
                    original.raw_sha256,
                    original.byte_size,
                    original.media_type,
                    original.deleted_at,
                )
                == (
                    ref.workspace_id,
                    pin.document_version_id,
                    pin.object_key,
                    pin.raw_sha256,
                    pin.byte_size,
                    "application/pdf",
                    None,
                )
            )
            if target is None:
                _require(
                    (
                        document.revision,
                        document.current_document_version_id,
                        document.active_embedding_set_id,
                    )
                    == (
                        pin.expected_revision,
                        pin.expected_current_version_id,
                        pin.expected_active_set_id,
                    )
                )
            elif pin.job_id == target.token.job_id:
                job = _locked(session, IngestionJobTable, pin.job_id)
                attempt = session.scalar(
                    select(IngestionJobAttemptTable)
                    .where(
                        IngestionJobAttemptTable.ingestion_job_id == pin.job_id,
                        IngestionJobAttemptTable.attempt_number == target.token.attempt_number,
                    )
                    .with_for_update()
                )
                _require(
                    job.workspace_id == ref.workspace_id
                    and job.operation == "corpus_prepare"
                    and job.target_document_version_id == pin.document_version_id
                    and job.attempt_count == 1
                    and job.max_attempts == 1
                    and attempt is not None
                )
                if poststate:
                    _require(job.status == "succeeded" and attempt.closed_at is not None)
                else:
                    _require(
                        job.status == "processing"
                        and job.current_attempt_number == 1
                        and attempt.closed_at is None
                    )
                revision = pin.expected_revision + int(
                    pin.expected_current_version_id != pin.document_version_id
                )
                _require(
                    document.current_document_version_id == pin.document_version_id
                    and document.revision == revision + int(poststate)
                )
                if not poststate:
                    _require(document.active_embedding_set_id == pin.expected_active_set_id)
                else:
                    active = _locked(session, EmbeddingSetTable, document.active_embedding_set_id)
                    chunks = _locked(session, ChunkSetTable, active.chunk_set_id)
                    _require(
                        active.status == "completed"
                        and active.embedding_configuration_id
                        == plan.configuration.embedding_configuration.id
                        and chunks.document_version_id == pin.document_version_id
                        and document.active_embedding_configuration_id
                        == active.embedding_configuration_id
                    )
            rows.append((pin, document, original))
        return rows

    def inspect(self, plan):
        with self._sessions.begin() as session:
            self._bound_transaction(session)
            self._load(session, plan)

    def begin(self, plan, admission):
        scope, claims = plan.scope(), []
        provenance = admission.verify(scope)
        with admission.corpus_mutation(scope), self._sessions.begin() as session:
            self._bound_transaction(session)
            rows = self._load(session, plan)
            now = self._now(session)
            _require(now < admission.valid_until)
            for pin, _, _ in rows:
                _require(session.get(IngestionJobTable, pin.job_id) is None)
            for pin, document, original in rows:
                prepared = PreparedPdfSubmission(
                    workspace_id=scope["workspace_id"],
                    source_key=pin.source_key,
                    source_name=document.source_name,
                    source_object=ObjectMetadata(
                        scope["workspace_id"],
                        pin.object_key,
                        pin.raw_sha256,
                        pin.byte_size,
                        "application/pdf",
                    ),
                    content_fingerprint=digest_json(
                        {"scope": scope, "provenance": provenance, "job_id": pin.job_id}
                    ),
                    idempotency_operation="corpus_prepare",
                    idempotency_key=pin.job_id,
                    idempotency_expires_at=admission.valid_until,
                    configuration=plan.configuration,
                )
                PostgresPdfSubmissionStore._get_or_create_chunking_configuration(session, prepared)
                PostgresPdfSubmissionStore._get_or_create_embedding_configuration(session, prepared)
                if document.current_document_version_id != pin.document_version_id:
                    document.current_document_version_id = pin.document_version_id
                    document.revision += 1
                config = plan.configuration
                worker = f"corpus:{plan.profile_id}"
                session.add(
                    IngestionJobTable(
                        id=pin.job_id,
                        workspace_id=scope["workspace_id"],
                        operation="corpus_prepare",
                        document_id=pin.document_id,
                        target_document_version_id=pin.document_version_id,
                        source_object_id=original.id,
                        content_fingerprint=prepared.content_fingerprint,
                        parser_configuration_id=config.parser_configuration_id,
                        normalizer_configuration_id=config.normalizer_configuration_id,
                        chunking_configuration_id=config.chunking_configuration.id,
                        embedding_configuration_id=config.embedding_configuration.id,
                        status="processing",
                        attempt_count=1,
                        max_attempts=1,
                        worker_id=worker,
                        lease_version=1,
                        lease_expires_at=admission.valid_until,
                        current_attempt_number=1,
                        current_attempt_started_at=now,
                        current_attempt_deadline_at=admission.valid_until,
                        started_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.flush()
                session.add(
                    IngestionJobAttemptTable(
                        ingestion_job_id=pin.job_id,
                        attempt_number=1,
                        worker_id=worker,
                        lease_version=1,
                        attempt_started_at=now,
                        deadline_at=admission.valid_until,
                        initial_lease_expires_at=admission.valid_until,
                        claim_operation_id=str(uuid4()),
                        claim_request_fingerprint=prepared.content_fingerprint,
                    )
                )
                session.flush()
                claims.append(
                    ClaimedAttempt(
                        token=FencingToken(pin.job_id, 1, worker, 1),
                        work=plan.work(pin),
                        attempt_count=1,
                        max_attempts=1,
                        attempt_started_at=now,
                        initial_lease_expires_at=admission.valid_until,
                        deadline_at=admission.valid_until,
                    )
                )
            session.flush()
            admission.check_mutation(scope)
        by_job = {c.token.job_id: c for c in claims}
        return tuple(by_job[p.job_id] for p in plan.sources)

    def _activation_guard(self, session, plan, admission, claim, poststate):
        self._bound_transaction(session)
        admission.check_mutation(plan.scope())
        _require(claim.token.job_id in {p.job_id for p in plan.sources})
        self._load(session, plan, target=claim, poststate=poststate)
        config = plan.configuration
        for table, expected in (
            (ChunkingConfigurationTable, config.chunking_configuration),
            (EmbeddingConfigurationTable, config.embedding_configuration),
        ):
            row = _locked(session, table, expected.id)
            _require(all(getattr(row, key) == value for key, value in asdict(expected).items()))
        _require(
            (
                claim.work.parser_configuration_id,
                claim.work.normalizer_configuration_id,
                claim.work.chunking_configuration_id,
                claim.work.embedding_configuration_id,
            )
            == (
                config.parser_configuration_id,
                config.normalizer_configuration_id,
                config.chunking_configuration.id,
                config.embedding_configuration.id,
            )
        )
        admission.check_mutation(plan.scope())

    def check_ready(self, plan, admission, claim):
        with self._sessions.begin() as session:
            self._activation_guard(session, plan, admission, claim, False)

    def activate_batch(self, plan, admission, items):
        _require(
            len(items) == 2
            and {claim.token.job_id for claim, _ in items} == {pin.job_id for pin in plan.sources}
        )

        class BoundSessionFactory:
            def __init__(self, session):
                self._session = session

            @contextmanager
            def begin(self):
                yield self._session

            @contextmanager
            def __call__(self):
                yield self._session

        with admission.corpus_mutation(plan.scope()), self._sessions.begin() as session:
            self._bound_transaction(session)
            lifecycle = PostgresObjectLifecycleStore(self._sessions, self._now)
            coordinator = PostgresIngestionJobCoordinationStore(
                BoundSessionFactory(session),
                self._now,
                lifecycle,
                corpus_activation_guard=lambda actual, claim, post: self._activation_guard(
                    actual, plan, admission, claim, post
                ),
            )
            results = []
            for claim, success in items:
                result = coordinator.finalize_success(
                    operation_id=TransitionOperationId(str(uuid4())),
                    claim=claim,
                    success=success,
                )
                if not isinstance(result, FinalizationApplied) or result.outcome != "succeeded":
                    raise ValueError("CORPUS_ACTIVATION_FAILED")
                results.append(result)
            admission.check_mutation(plan.scope())
            return tuple(results)
