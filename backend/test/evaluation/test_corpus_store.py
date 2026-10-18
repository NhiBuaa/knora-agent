"""Exercise actual adapter transactions offline, without PostgreSQL services."""

from dataclasses import asdict

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, attributes, sessionmaker
from test_corpus_plan import plan_fixture
from test_live_admission import NOW

from knora.adapters.postgres.database import Base
from knora.adapters.postgres.evaluation_datasets_tables import (
    DatasetDraftTable,
    DatasetSourceTable,
    EvaluationGoldVersionTable,
    ExtractionSnapshotTable,
)
from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkingConfigurationTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    ObjectLifecycleWorkTable,
    OriginalSourceObjectTable,
    WorkspaceAdmissionTable,
    WorkspaceIdentityTable,
    WorkspaceTable,
)
from knora.evaluation.live_admission import LiveAdmission


@pytest.fixture
def corpus_db():
    plan = plan_fixture()
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def sqlite_clock(dbapi, _):
        dbapi.create_function("clock_timestamp", 0, lambda: NOW.strftime("%Y-%m-%d %H:%M:%S.%f"))
        dbapi.create_function("to_tsvector", 2, lambda config, content: content, deterministic=True)

    from sqlalchemy.dialects.postgresql import TSVECTOR
    from sqlalchemy.ext.compiler import compiles, deregister

    @compiles(TSVECTOR, "sqlite")
    def sqlite_vector(type_, compiler, **kw):
        return "TEXT"

    Base.metadata.create_all(
        engine,
        tables=[
            c.__table__
            for c in (
                WorkspaceIdentityTable,
                WorkspaceTable,
                DocumentTable,
                DocumentVersionTable,
                OriginalSourceObjectTable,
                ChunkingConfigurationTable,
                EmbeddingConfigurationTable,
                IngestionJobTable,
                IngestionJobAttemptTable,
                DatasetDraftTable,
                DatasetSourceTable,
                EvaluationGoldVersionTable,
                ExtractionSnapshotTable,
                ChunkSetTable,
                ChunkTable,
                EmbeddingSetTable,
                ChunkEmbeddingTable,
                WorkspaceAdmissionTable,
                ObjectLifecycleWorkTable,
            )
        ],
    )

    class OfflineSession(Session):
        pass

    @event.listens_for(OfflineSession, "loaded_as_persistent")
    def restore_utc(session, instance):
        # SQLite drops timezone information; production PostgreSQL retains it.
        from datetime import UTC, datetime

        for column in instance.__table__.columns:
            value = getattr(instance, column.name)
            if isinstance(value, datetime) and value.tzinfo is None:
                attributes.set_committed_value(instance, column.name, value.replace(tzinfo=UTC))

    factory = sessionmaker(engine, class_=OfflineSession, expire_on_commit=False)
    ref = plan.frozen.reference
    with factory.begin() as s:
        s.add(WorkspaceIdentityTable(id="identity", issuer="issuer", subject="owner"))
        s.add(
            WorkspaceTable(
                id=ref.workspace_id, name="Offline", owner_identity_id="identity", revision=0
            )
        )
        s.add(
            DatasetDraftTable(
                id=ref.dataset_id,
                workspace_id=ref.workspace_id,
                name="Frozen",
                status="FROZEN",
                revision=8,
                reference=asdict(ref),
            )
        )
        s.add(
            EvaluationGoldVersionTable(
                id="gold",
                workspace_id=ref.workspace_id,
                dataset_id=ref.dataset_id,
                version=1,
                digest=ref.digest,
                frozen_json=plan.frozen_json,
                reviews=[],
                draft_revision=7,
            )
        )
        for p in plan.sources:
            s.add(
                DocumentTable(
                    id=p.document_id,
                    workspace_id=ref.workspace_id,
                    source_key=p.source_key,
                    source_name="fixture.pdf",
                    revision=0,
                )
            )
            s.add(
                DocumentVersionTable(
                    id=p.document_version_id,
                    document_id=p.document_id,
                    raw_sha256=p.raw_sha256,
                    media_type="application/pdf",
                    version_number=1,
                )
            )
            s.add(
                OriginalSourceObjectTable(
                    id=p.original_source_object_id,
                    workspace_id=ref.workspace_id,
                    document_version_id=p.document_version_id,
                    object_key=p.object_key,
                    raw_sha256=p.raw_sha256,
                    byte_size=p.byte_size,
                    media_type="application/pdf",
                )
            )
            s.add(
                DatasetSourceTable(
                    id=p.source_id,
                    dataset_id=ref.dataset_id,
                    workspace_id=ref.workspace_id,
                    document_id=p.document_id,
                    document_version_id=p.document_version_id,
                    original_source_object_id=p.original_source_object_id,
                    filename="fixture.pdf",
                    raw_sha256=p.raw_sha256,
                    byte_size=p.byte_size,
                    object_key=p.object_key,
                    idempotency_key=p.source_id,
                    status="READY",
                    snapshot_id=p.snapshot_id,
                )
            )
            s.add(
                ExtractionSnapshotTable(
                    id=p.snapshot_id,
                    workspace_id=ref.workspace_id,
                    source_id=p.source_id,
                    configuration_sha256="c" * 64,
                    extraction_sha256="d" * 64,
                    parser_version="test",
                    extraction_options_version="test",
                    normalizer_version="test",
                    pages=[],
                )
            )
    yield plan, factory
    engine.dispose()
    deregister(TSVECTOR)


def admitted(tmp_path, plan):
    from test_corpus_preparation import corpus_gate

    _, _, _ = corpus_gate(tmp_path)
    import json
    import sqlite3

    with sqlite3.connect(tmp_path / "corpus.sqlite") as db:
        policy = json.loads(db.execute("SELECT policy FROM approvals").fetchone()[0])
    return LiveAdmission(
        {**policy, "scope": plan.scope()}, tmp_path / "journal.sqlite", clock=lambda: NOW
    )


def adapter(factory):
    from knora.adapters.postgres.corpus_preparation import PostgresCorpusPreparationStore

    return PostgresCorpusPreparationStore(factory, database_now=lambda s: NOW)


def test_admission_reuses_versions_and_retains_gold(corpus_db, tmp_path):
    plan, factory = corpus_db
    store, gate = adapter(factory), admitted(tmp_path, plan)
    store.inspect(plan)
    with gate.corpus_operation(plan.scope(), plan.payload()):
        claims = store.begin(plan, gate)
        assert tuple(c.token.job_id for c in claims) == ("job-1", "job-2")
        assert all(c.max_attempts == c.attempt_count == 1 for c in claims)
    with factory() as s:
        assert len(s.scalars(select(DocumentVersionTable)).all()) == 2
        assert s.get(EvaluationGoldVersionTable, "gold").frozen_json == plan.frozen_json
        assert s.get(DatasetDraftTable, "pdf-set").revision == 8
        assert [
            (
                s.get(DocumentTable, p.document_id).current_document_version_id,
                s.get(DocumentTable, p.document_id).revision,
            )
            for p in plan.sources
        ] == [("version-1", 1), ("version-2", 1)]


@pytest.mark.parametrize("drift", ["source", "owner", "revision", "gold", "workspace", "original"])
def test_drift_rolls_back_all_admission_effects(corpus_db, tmp_path, drift):
    plan, factory = corpus_db
    with factory.begin() as s:
        if drift == "source":
            s.get(DatasetSourceTable, "source-2").status = "FAILED"
        elif drift == "owner":
            s.get(WorkspaceIdentityTable, "identity").subject = "foreign"
        elif drift == "revision":
            s.get(DocumentTable, "document-2").revision = 1
        elif drift == "gold":
            s.get(EvaluationGoldVersionTable, "gold").digest = "f" * 64
        elif drift == "workspace":
            s.get(WorkspaceTable, plan.frozen.reference.workspace_id).archived = True
        else:
            s.get(OriginalSourceObjectTable, "original-2").byte_size = 101
    gate = admitted(tmp_path, plan)
    with (
        pytest.raises(ValueError, match="CORPUS_STATE_CHANGED"),
        gate.corpus_operation(plan.scope(), plan.payload()),
    ):
        adapter(factory).begin(plan, gate)
    with factory() as s:
        assert s.scalars(select(IngestionJobTable)).all() == []
        assert s.get(DocumentTable, "document-1").current_document_version_id is None


@pytest.mark.parametrize("phase", ["queued", "expired"])
def test_ordinary_worker_cannot_claim_or_recover_corpus_jobs(corpus_db, tmp_path, phase):
    from datetime import timedelta

    from knora.adapters.postgres.ingestion_jobs.coordination import (
        PostgresIngestionJobCoordinationStore,
    )
    from knora.ingestion.job_processing import AttemptTimingV1, ClaimOperationId, NoEligibleClaim

    plan, factory = corpus_db
    gate = admitted(tmp_path, plan)
    with gate.corpus_operation(plan.scope(), plan.payload()):
        adapter(factory).begin(plan, gate)
    with factory.begin() as s:
        for pin in plan.sources:
            job = s.get(IngestionJobTable, pin.job_id)
            if phase == "queued":
                job.status = "queued"
                job.attempt_count = 0
                s.delete(s.get(IngestionJobAttemptTable, (pin.job_id, 1)))
            else:
                job.lease_expires_at = NOW - timedelta(seconds=1)
    from knora.adapters.postgres.ingestion_jobs.lifecycle import PostgresObjectLifecycleStore

    ordinary = PostgresIngestionJobCoordinationStore(
        factory, lambda s: NOW, PostgresObjectLifecycleStore(factory, lambda s: NOW)
    )
    if phase == "queued":
        assert isinstance(
            ordinary.claim_next_attempt(
                operation_id=ClaimOperationId("ordinary"),
                worker_id="ordinary",
                timing=AttemptTimingV1.standard(),
            ),
            NoEligibleClaim,
        )
    else:
        assert ordinary.observe_expired_attempt() is None


def derivation_handler(plan, provider):
    from hashlib import sha256
    from io import BytesIO
    from types import SimpleNamespace

    from knora.ingestion.job_processing import PdfDerivationHandler, PdfDerivationProfile
    from knora.ingestion.object_store import ObjectMetadata
    from knora.ingestion.pdf import (
        NormalizedPdfPage,
        PdfExtractionResult,
        PreparedPdfChunk,
    )

    def extract(stream, config):
        text = "The sky is blue."
        checksum = sha256(text.encode()).hexdigest()
        return PdfExtractionResult(
            (NormalizedPdfPage(1, text, checksum),),
            (PreparedPdfChunk(0, 1, 1, 1, 0, 16, text, checksum, 5),),
            config.parser_version,
            config.extraction_options_version,
            config.normalizer_version,
            config.tokenizer_name,
            config.tokenizer_version,
            config.chunking_policy_version,
            config.derivation_identity,
        )

    def head(*, workspace_id, object_key):
        pin = next(p for p in plan.sources if p.object_key == object_key)
        return ObjectMetadata(
            workspace_id, object_key, pin.raw_sha256, pin.byte_size, "application/pdf"
        )

    return PdfDerivationHandler(
        object_store=SimpleNamespace(
            head=head, open_read=lambda **kw: BytesIO(b"synthetic fixture")
        ),
        extractor=SimpleNamespace(extract=extract),
        embedding_provider=provider,
        profile=PdfDerivationProfile.milestone_two(
            embedding_configuration=plan.configuration.embedding_configuration
        ),
    )


def test_preparation_uses_actual_guard_handler_and_fenced_finalizer(corpus_db, tmp_path):
    import json

    import httpx
    from test_corpus_preparation import corpus_gate

    from knora.evaluation.contracts import digest_json
    from knora.evaluation.corpus_preparation import prepare_corpus
    from knora.providers.cloudflare.embedding import CloudflareEmbeddingProvider

    plan, factory = corpus_db
    seed, _, _ = corpus_gate(tmp_path)
    policy = {**seed._policy, "scope": plan.scope()}
    policy["providers"][0]["request_digests"] = [digest_json({"documents": ["The sky is blue."]})]
    gate = LiveAdmission(policy, tmp_path / "actual.sqlite", clock=lambda: NOW)
    exchanges = []

    def reply(request):
        exchanges.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"success": True, "result": {"shape": [1, 1024], "data": [[1.0] + [0.0] * 1023]}},
        )

    with gate.sync_client(mock=httpx.MockTransport(reply)) as client:
        provider = CloudflareEmbeddingProvider(
            account_id="a" * 32, api_token="test-only", client=client
        )
        result = prepare_corpus(
            plan,
            admission=gate,
            store=adapter(factory),
            handler=derivation_handler(plan, provider),
            provider_client=client,
            runtime=attempt_runtime(),
        )
    assert len(result) == 2
    assert exchanges == [{"documents": ["The sky is blue."]}] * 2
    assert gate.snapshot() == {"attempts": 2, "pending": None, "stopped": False}
    with factory() as s:
        assert [s.get(IngestionJobTable, p.job_id).status for p in plan.sources] == [
            "succeeded",
            "succeeded",
        ]
        assert [s.get(DocumentTable, p.document_id).revision for p in plan.sources] == [2, 2]
        assert all(
            s.get(DocumentTable, p.document_id).active_embedding_set_id for p in plan.sources
        )
        assert len(s.scalars(select(ChunkEmbeddingTable)).all()) == 2
        assert s.get(EvaluationGoldVersionTable, "gold").frozen_json == plan.frozen_json


@pytest.mark.parametrize(
    "failure", ["unguarded", "late_expiry", "revision", "configuration", "source"]
)
def test_activation_rolls_back_on_missing_authority_or_drift(corpus_db, tmp_path, failure):
    from datetime import timedelta

    from knora.adapters.postgres.ingestion_jobs.coordination import (
        PostgresIngestionJobCoordinationStore,
    )
    from knora.adapters.postgres.ingestion_jobs.lifecycle import PostgresObjectLifecycleStore
    from knora.ingestion.job_processing import (
        CoordinationInvariantError,
        PdfDerivationSuccess,
        TransitionOperationId,
    )
    from knora.ingestion.pdf import PdfExtractionConfiguration

    plan, factory = corpus_db
    gate = admitted(tmp_path, plan)
    store = adapter(factory)
    now = [NOW]
    gate._clock = lambda: now[0]
    config = plan.configuration.embedding_configuration
    extraction = derivation_handler(plan, None)._extractor.extract(
        None, PdfExtractionConfiguration.milestone_two()
    )
    success = PdfDerivationSuccess(
        extraction, ((1.0,) + (0.0,) * 1023,), config.provider, config.model
    )
    with (
        pytest.raises(
            (ValueError, CoordinationInvariantError),
            match="authority required|CORPUS_STATE_CHANGED|LIVE_APPROVAL_EXPIRED|pinned target",
        ),
        gate.corpus_operation(plan.scope(), plan.payload()),
    ):
        claims = store.begin(plan, gate)
        claim = claims[0]
        if failure == "late_expiry":
            real_guard = store._activation_guard

            def expiring_guard(session, actual_plan, admission, actual, post):
                if post:
                    now[0] += timedelta(minutes=6)
                return real_guard(session, actual_plan, admission, actual, post)

            store._activation_guard = expiring_guard
        elif failure != "unguarded":
            with factory.begin() as s:
                if failure == "revision":
                    s.get(DocumentTable, "document-1").revision += 1
                elif failure == "configuration":
                    s.get(EmbeddingConfigurationTable, config.id).model = "changed"
                else:
                    s.get(DatasetSourceTable, "source-1").status = "FAILED"
        if failure == "unguarded":
            ordinary = PostgresIngestionJobCoordinationStore(
                factory, lambda s: NOW, PostgresObjectLifecycleStore(factory, lambda s: NOW)
            )
            ordinary.finalize_success(
                operation_id=TransitionOperationId("unguarded"), claim=claim, success=success
            )
        else:
            store.activate_batch(plan, gate, tuple((actual, success) for actual in claims))
    with factory() as s:
        assert s.get(DocumentTable, "document-1").active_embedding_set_id is None
        assert s.scalars(select(ChunkSetTable)).all() == []
        assert s.scalars(select(ChunkEmbeddingTable)).all() == []
        assert s.get(IngestionJobTable, "job-1").status == "processing"
        assert s.get(IngestionJobAttemptTable, ("job-1", 1)).closed_at is None
        assert s.get(EvaluationGoldVersionTable, "gold").frozen_json == plan.frozen_json


def test_second_activation_failure_rolls_back_both_sources(corpus_db, tmp_path):
    from dataclasses import replace

    from knora.ingestion.job_processing import CoordinationInvariantError, PdfDerivationSuccess
    from knora.ingestion.pdf import PdfExtractionConfiguration

    plan, factory = corpus_db
    store, gate = adapter(factory), admitted(tmp_path, plan)
    extraction = derivation_handler(plan, None)._extractor.extract(
        None, PdfExtractionConfiguration.milestone_two()
    )
    config = plan.configuration.embedding_configuration
    success = PdfDerivationSuccess(
        extraction, ((1.0,) + (0.0,) * 1023,), config.provider, config.model
    )
    with (
        pytest.raises(CoordinationInvariantError, match="invalid vectors"),
        gate.corpus_operation(plan.scope(), plan.payload()),
    ):
        first, second = store.begin(plan, gate)
        store.activate_batch(
            plan, gate, ((first, success), (second, replace(success, vectors=((1.0,),))))
        )
    with factory() as s:
        assert s.scalars(select(ChunkSetTable)).all() == []
        assert s.scalars(select(ChunkEmbeddingTable)).all() == []
        for pin in plan.sources:
            assert s.get(DocumentTable, pin.document_id).active_embedding_set_id is None
            assert s.get(IngestionJobTable, pin.job_id).status == "processing"
            assert s.get(IngestionJobAttemptTable, (pin.job_id, 1)).closed_at is None
        assert s.get(EvaluationGoldVersionTable, "gold").frozen_json == plan.frozen_json


def attempt_runtime():
    import time
    from types import SimpleNamespace

    from knora.adapters.execution.thread_attempt_runner import (
        FixedCapacityThreadAttemptRunner,
        ThreadAttemptScheduler,
    )
    from knora.ingestion.job_processing import AttemptRuntime

    clock = SimpleNamespace(now=time.monotonic)
    return AttemptRuntime(
        FixedCapacityThreadAttemptRunner(max_concurrency=1), clock, ThreadAttemptScheduler(clock)
    )


def test_blocked_extraction_returns_on_authority_expiry(corpus_db, tmp_path):
    from datetime import timedelta
    from threading import Event

    import httpx

    from knora.evaluation.corpus_preparation import prepare_corpus
    from knora.providers.cloudflare.embedding import CloudflareEmbeddingProvider

    plan, factory = corpus_db
    store, gate = adapter(factory), admitted(tmp_path, plan)
    started, release, exited, completed = Event(), Event(), Event(), Event()
    now = [NOW]
    gate._clock = lambda: now[0]
    exchanges = []
    with gate.sync_client(mock=httpx.MockTransport(lambda r: exchanges.append(r))) as client:
        provider = CloudflareEmbeddingProvider(
            account_id="a" * 32, api_token="test-only", client=client
        )
        handler = derivation_handler(plan, provider)
        original = handler._extractor.extract
        execute = handler.execute

        def tracked(work, cancellation):
            try:
                return execute(work, cancellation)
            finally:
                completed.set()

        handler.execute = tracked
        runtime = attempt_runtime()

        def blocked(stream, config):
            started.set()
            now[0] = NOW + timedelta(minutes=6)
            try:
                assert release.wait(5)
                return original(stream, config)
            finally:
                exited.set()

        handler._extractor.extract = blocked
        try:
            with pytest.raises(ValueError, match="LIVE_APPROVAL_EXPIRED"):
                prepare_corpus(
                    plan,
                    admission=gate,
                    store=store,
                    handler=handler,
                    provider_client=client,
                    runtime=runtime,
                )
            assert started.is_set()
            assert gate.snapshot()["stopped"] is True
            assert exchanges == []
            assert runtime.runner.try_reserve() is None
        finally:
            release.set()
            if started.is_set():
                assert exited.wait(5)
                assert completed.wait(5)
        assert gate.snapshot()["attempts"] == 0
        assert exchanges == []
    with factory() as s:
        assert s.scalars(select(ChunkSetTable)).all() == []
        assert all(
            s.get(DocumentTable, p.document_id).active_embedding_set_id is None
            for p in plan.sources
        )


@pytest.mark.parametrize("transition", ["recovery", "heartbeat", "retry", "failure", "superseded"])
def test_ordinary_transition_rejects_constructed_corpus_claim(corpus_db, tmp_path, transition):
    from datetime import timedelta

    from knora.adapters.postgres.ingestion_jobs.coordination import (
        PostgresIngestionJobCoordinationStore,
    )
    from knora.adapters.postgres.ingestion_jobs.lifecycle import PostgresObjectLifecycleStore
    from knora.ingestion.job_processing import (
        CanonicalFailureV1,
        CoordinationInvariantError,
        ExpiredAttemptObservation,
        FailureCauseV1,
        HeartbeatOperationId,
        RetryExhausted,
        ScheduleRetry,
        TransitionOperationId,
        WorkSuperseded,
    )

    plan, factory = corpus_db
    gate = admitted(tmp_path, plan)
    with gate.corpus_operation(plan.scope(), plan.payload()):
        claim = adapter(factory).begin(plan, gate)[0]
    ordinary = PostgresIngestionJobCoordinationStore(
        factory, lambda s: NOW, PostgresObjectLifecycleStore(factory, lambda s: NOW)
    )
    failure = CanonicalFailureV1(
        FailureCauseV1.LEASE_EXPIRED,
        "lease_expired",
        None,
        "failure-causes-v1",
        "supervisor-v1",
    )
    with pytest.raises(CoordinationInvariantError, match="corpus preparation authority required"):
        if transition == "recovery":
            ordinary.apply_expired_recovery(
                operation_id=TransitionOperationId("bypass"),
                observation=ExpiredAttemptObservation(
                    claim.token.job_id, 1, claim.token.worker_id, 1, 1, 1, NOW
                ),
                failure=failure,
                decision=RetryExhausted(),
            )
        elif transition == "heartbeat":
            ordinary.heartbeat(
                operation_id=HeartbeatOperationId("bypass"),
                token=claim.token,
                lease_duration=timedelta(hours=1),
            )
        elif transition == "retry":
            ordinary.schedule_retry(
                operation_id=TransitionOperationId("bypass"),
                claim=claim,
                failure=CanonicalFailureV1(
                    FailureCauseV1.PROVIDER_TRANSIENT,
                    "provider_transient",
                    None,
                    "failure-causes-v1",
                    "cause-mapping-v1",
                ),
                decision=ScheduleRetry(0, 5000000),
            )
        elif transition == "failure":
            from dataclasses import replace

            ordinary.finalize_terminal_failure(
                operation_id=TransitionOperationId("bypass"),
                claim=claim,
                failure=replace(failure, failure_reason="retry_exhausted"),
                decision=RetryExhausted(),
            )
        else:
            ordinary.finalize_superseded(
                operation_id=TransitionOperationId("bypass"), claim=claim, outcome=WorkSuperseded()
            )
    with factory() as s:
        assert s.get(IngestionJobTable, claim.token.job_id).status == "processing"
        assert s.get(IngestionJobAttemptTable, (claim.token.job_id, 1)).closed_at is None


def test_ordinary_claim_replay_rejects_corpus_job(corpus_db, tmp_path):
    from knora.adapters.postgres.ingestion_jobs.coordination import (
        PostgresIngestionJobCoordinationStore,
    )
    from knora.adapters.postgres.ingestion_jobs.lifecycle import PostgresObjectLifecycleStore
    from knora.ingestion.job_processing import (
        AttemptTimingV1,
        ClaimOperationId,
        CoordinationInvariantError,
    )

    plan, factory = corpus_db
    gate = admitted(tmp_path, plan)
    with gate.corpus_operation(plan.scope(), plan.payload()):
        claim = adapter(factory).begin(plan, gate)[0]
    ordinary = PostgresIngestionJobCoordinationStore(
        factory, lambda s: NOW, PostgresObjectLifecycleStore(factory, lambda s: NOW)
    )
    timing = AttemptTimingV1.standard()
    with factory.begin() as s:
        attempt = s.get(IngestionJobAttemptTable, (claim.token.job_id, 1))
        attempt.claim_operation_id = "constructed-replay"
        attempt.claim_request_fingerprint = ordinary._claim_fingerprint(
            worker_id=claim.token.worker_id, timing=timing
        )
    with pytest.raises(CoordinationInvariantError, match="corpus preparation authority required"):
        ordinary.claim_next_attempt(
            operation_id=ClaimOperationId("constructed-replay"),
            worker_id=claim.token.worker_id,
            timing=timing,
        )
