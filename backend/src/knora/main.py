from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from knora.access.api_keys import ApiKeyAuthenticator, credentials_from_json
from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.adapters.http.routes import router as http_router
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.object_store.inventory import JsonlObjectInventory
from knora.adapters.object_store.s3 import BotoS3CapabilityClient, S3CapabilityClient, S3ObjectStore
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.object_reconciliation import (
    PostgresClock,
    PostgresObjectReferenceResolver,
)
from knora.adapters.postgres.operational_observability import PostgresOperationalMetricsStore
from knora.answering.module import AnswerQuestion
from knora.answering.retrieval_configuration import (
    DeploymentRetrievalConfigurationResolver,
    resolve_retrieval_configuration,
)
from knora.api.routes import router
from knora.bootstrap import build_provider_selection
from knora.domain.errors import KnoraError
from knora.infrastructure.settings import ObjectStoreSettings, settings
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    PdfDerivationHandler,
    ProcessIngestionJob,
    RetryPolicyV1,
    SystemRandomSource,
    UuidOperationIds,
)
from knora.ingestion.jobs import IngestionJobs
from knora.ingestion.module import IngestDocument
from knora.ingestion.object_lifecycle import (
    LifecycleClock,
    LifecycleRandomSource,
    ObjectInventory,
    ObjectLifecycleMaintenance,
    ObjectLifecycleReconciler,
    ObjectLifecycleRetryPolicyV1,
    ObjectLifecycleWorker,
    SystemLifecycleRandomSource,
)
from knora.ingestion.object_store import ObjectStore
from knora.ingestion.operational_observability import (
    AlertPolicyV1,
    LoggingOperationalTelemetry,
    OperationalAlertConfigurationV1,
    OperationalMetricsStore,
    OperationalObservability,
    OperationalTelemetry,
)
from knora.ingestion.processing import DocumentProcessor
from knora.providers.embedding import EmbeddingConfiguration


def create_app(
    *,
    ingest_document: IngestDocument | None = None,
    ingestion_jobs: IngestionJobs | None = None,
    answer_question: AnswerQuestion | None = None,
    api_key_authenticator: ApiKeyAuthenticator | None = None,
    embedding_configuration: EmbeddingConfiguration | None = None,
    ingestion_worker: ProcessIngestionJob | None = None,
    object_store: ObjectStore | None = None,
    s3_client: S3CapabilityClient | None = None,
    lifecycle_maintenance: ObjectLifecycleMaintenance | None = None,
    lifecycle_inventory: ObjectInventory | None = None,
    lifecycle_clock: LifecycleClock | None = None,
    lifecycle_random_source: LifecycleRandomSource | None = None,
    operational_metrics_store: OperationalMetricsStore | None = None,
    operational_telemetry: OperationalTelemetry | None = None,
    operational_alert_configuration: OperationalAlertConfigurationV1 | None = None,
) -> FastAPI:
    providers = build_provider_selection(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        del application
        try:
            yield
        finally:
            close_embedding = getattr(providers.embedding_provider, "close", None)
            if close_embedding is not None:
                close_embedding()
            close_generation = getattr(providers.generation_provider, "aclose", None)
            if close_generation is not None:
                await close_generation()

    application = FastAPI(title="Knora Agent", version="0.1.0", lifespan=lifespan)
    selected_embedding_configuration = (
        embedding_configuration or providers.embedding_configuration
    )
    application.state.answer_question = answer_question or AnswerQuestion(
        embedding_provider=providers.embedding_provider,
        generation_provider=providers.generation_provider,
        store=PostgresAnsweringStore(SessionFactory),
        embedding_configuration=selected_embedding_configuration,
        retrieval_configuration_resolver=DeploymentRetrievalConfigurationResolver(
            resolve_retrieval_configuration(
                settings.retrieval_configuration_id,
                vector_min_similarity=settings.vector_min_similarity,
            )
        ),
    )
    application.state.ingest_document = ingest_document or IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=providers.embedding_provider,
        store=PostgresIngestionStore(SessionFactory),
    )
    runtime_object_store_settings = ObjectStoreSettings.from_runtime(settings)
    selected_object_store = object_store
    if selected_object_store is None and runtime_object_store_settings.backend == "filesystem":
        selected_object_store = FileSystemObjectStore(runtime_object_store_settings.root)
    if selected_object_store is None and runtime_object_store_settings.backend == "s3_compatible":
        if not runtime_object_store_settings.s3_bucket:
            raise ValueError("S3-compatible ObjectStore requires a bucket")
        if s3_client is None:
            if (
                runtime_object_store_settings.s3_access_key is None
                or runtime_object_store_settings.s3_secret_key is None
            ):
                raise ValueError("S3-compatible ObjectStore requires access credentials")
            s3_client = BotoS3CapabilityClient(
                endpoint_url=runtime_object_store_settings.s3_endpoint,
                region_name=runtime_object_store_settings.s3_region,
                access_key=runtime_object_store_settings.s3_access_key.get_secret_value(),
                secret_key=runtime_object_store_settings.s3_secret_key.get_secret_value(),
            )
        selected_object_store = S3ObjectStore(
            client=s3_client,
            bucket=runtime_object_store_settings.s3_bucket,
        )
    if selected_object_store is None:
        raise ValueError("unsupported object_store_backend")
    job_store = PostgresIngestionJobStore(SessionFactory)
    selected_lifecycle_maintenance = lifecycle_maintenance or job_store
    selected_lifecycle_clock = lifecycle_clock or PostgresClock(SessionFactory)
    application.state.ingestion_jobs = ingestion_jobs or IngestionJobs(
        object_store=selected_object_store,
        store=job_store,
        lifecycle_maintenance=selected_lifecycle_maintenance,
        lifecycle_clock=selected_lifecycle_clock,
    )
    application.state.ingestion_worker = ingestion_worker or ProcessIngestionJob(
        store=job_store,
        handler=PdfDerivationHandler(
            object_store=selected_object_store,
            extractor=PypdfTextExtractor(),
            embedding_provider=providers.embedding_provider,
            profile_resolver=job_store.pdf_profile_for_work,
        ),
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
    )
    application.state.object_lifecycle_worker = ObjectLifecycleWorker(
        maintenance=selected_lifecycle_maintenance,
        object_store=selected_object_store,
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=lifecycle_random_source or SystemLifecycleRandomSource()
        ),
    )
    selected_inventory = lifecycle_inventory
    if selected_inventory is None and settings.object_inventory_manifest:
        selected_inventory = JsonlObjectInventory(settings.object_inventory_manifest)
    application.state.object_lifecycle_reconciler = None
    if selected_inventory is not None:
        minimum_age_seconds = settings.object_inventory_minimum_age_seconds
        if minimum_age_seconds is None or minimum_age_seconds < 0:
            raise ValueError(
                "object inventory reconciliation requires a non-negative minimum age setting"
            )
        application.state.object_lifecycle_reconciler = ObjectLifecycleReconciler(
            inventory=selected_inventory,
            references=PostgresObjectReferenceResolver(SessionFactory),
            maintenance=selected_lifecycle_maintenance,
            minimum_age=timedelta(seconds=minimum_age_seconds),
            now=selected_lifecycle_clock,
        )
    selected_alert_configuration = operational_alert_configuration
    if selected_alert_configuration is None and settings.operational_alert_configuration_json:
        selected_alert_configuration = OperationalAlertConfigurationV1.from_json(
            settings.operational_alert_configuration_json
        )
    selected_metrics_store = operational_metrics_store
    if selected_metrics_store is None:
        selected_metrics_store = PostgresOperationalMetricsStore(
            SessionFactory,
            retry_window=timedelta(seconds=settings.operational_metrics_retry_window_seconds),
        )
    application.state.operational_observability = OperationalObservability(
        store=selected_metrics_store,
        telemetry=operational_telemetry or LoggingOperationalTelemetry(),
        alert_policy=AlertPolicyV1() if selected_alert_configuration is not None else None,
        alert_configuration=selected_alert_configuration,
    )
    application.state.api_key_authenticator = api_key_authenticator or ApiKeyAuthenticator(
        credentials_from_json(settings.api_credentials_json)
    )
    application.state.embedding_configuration = selected_embedding_configuration

    @application.exception_handler(KnoraError)
    async def handle_knora_error(request: Request, error: KnoraError) -> JSONResponse:
        status = {
            "UNAUTHENTICATED": 401,
            "WORKSPACE_ACCESS_DENIED": 403,
            "INVALID_SOURCE_KEY": 400,
            "INVALID_SOURCE_NAME": 400,
            "UNSUPPORTED_DOCUMENT_TYPE": 400,
            "INVALID_DOCUMENT_ENCODING": 400,
            "DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION": 413,
            "DOCUMENT_CONCURRENTLY_UPDATED": 409,
            "EMBEDDING_DIMENSION_MISMATCH": 502,
            "EMBEDDING_CONFIGURATION_MISMATCH": 502,
            "GENERATION_OUTPUT_INVALID": 502,
            "PROVIDER_REQUEST_FAILED": 502,
            "PROVIDER_RESPONSE_INVALID": 502,
            "PERSISTENCE_OPERATION_FAILED": 500,
            "INVALID_IDEMPOTENCY_KEY": 400,
            "MISSING_IDEMPOTENCY_KEY": 400,
            "INVALID_PDF_SIGNATURE": 400,
            "PDF_STREAM_NOT_SEEKABLE": 400,
            "OBJECT_STORE_METADATA_INVALID": 500,
            "OBJECT_NOT_FOUND": 404,
            "PDF_RESOURCE_LIMIT_EXCEEDED": 413,
            "PDF_INGESTION_NOT_CONFIGURED": 503,
            "INGESTION_JOB_NOT_FOUND": 404,
            "DOCUMENT_VERSION_NOT_FOUND": 404,
            "SOURCE_OBJECT_NOT_AVAILABLE": 404,
            "DOCUMENT_VERSION_NOT_CURRENT": 409,
            "INVALID_CONFIG_MODE": 400,
            "CONFIG_SOURCE_JOB_REQUIRED": 400,
            "CONFIG_SOURCE_JOB_NOT_ALLOWED": 400,
            "CONFIG_SOURCE_JOB_INVALID": 400,
            "CONFIGURATION_NOT_AVAILABLE": 409,
            "IDEMPOTENCY_KEY_CONFLICT": 409,
        }.get(error.code, 400)
        return JSONResponse(status_code=status, content={"error": {"code": error.code}})

    application.include_router(http_router)
    application.include_router(router)
    return application


app = create_app()
