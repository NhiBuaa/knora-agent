from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from knora.access.api_keys import ApiKeyAuthenticator, credentials_from_json
from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.adapters.http.routes import router as http_router
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.answering.module import AnswerQuestion
from knora.api.routes import router
from knora.bootstrap import build_provider_selection
from knora.domain.errors import KnoraError
from knora.infrastructure.settings import settings
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
    )
    application.state.ingest_document = ingest_document or IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=providers.embedding_provider,
        store=PostgresIngestionStore(SessionFactory),
    )
    job_store = PostgresIngestionJobStore(SessionFactory)
    object_store = FileSystemObjectStore(settings.object_store_root)
    application.state.ingestion_jobs = ingestion_jobs or IngestionJobs(
        object_store=object_store,
        store=job_store,
    )
    application.state.ingestion_worker = ingestion_worker or ProcessIngestionJob(
        store=job_store,
        handler=PdfDerivationHandler(
            object_store=object_store,
            extractor=PypdfTextExtractor(),
            embedding_provider=providers.embedding_provider,
            profile_resolver=job_store.pdf_profile_for_work,
        ),
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
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
