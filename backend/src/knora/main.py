from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from knora.access.api_keys import ApiKeyAuthenticator, credentials_from_json
from knora.adapters.http.routes import router as http_router
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.api.routes import router
from knora.application.answer_question import AnswerQuestion
from knora.domain.errors import KnoraError
from knora.domain.models import RetrievedChunk
from knora.infrastructure.settings import settings
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import DocumentProcessor
from knora.providers.demo import DemoAnswerGenerator, DemoRetriever
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider


def create_app(
    *,
    ingest_document: IngestDocument | None = None,
    api_key_authenticator: ApiKeyAuthenticator | None = None,
) -> FastAPI:
    application = FastAPI(title="Knora Agent", version="0.1.0")
    demo_chunks = [
        RetrievedChunk(
            document_id="refund-policy",
            chunk_id="refund-policy:0",
            source="refund-policy.md",
            content="Khách hàng có thể yêu cầu hoàn tiền trong vòng 30 ngày kể từ ngày mua.",
            score=1.0,
        )
    ]
    application.state.answer_question = AnswerQuestion(
        retriever=DemoRetriever(demo_chunks),
        generator=DemoAnswerGenerator(),
    )
    application.state.ingest_document = ingest_document or IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    application.state.api_key_authenticator = api_key_authenticator or ApiKeyAuthenticator(
        credentials_from_json(settings.api_credentials_json)
    )

    @application.exception_handler(KnoraError)
    async def handle_knora_error(request: Request, error: KnoraError) -> JSONResponse:
        status = {
            "UNAUTHENTICATED": 401,
            "WORKSPACE_ACCESS_DENIED": 403,
            "INVALID_SOURCE_KEY": 400,
            "UNSUPPORTED_DOCUMENT_TYPE": 400,
            "INVALID_DOCUMENT_ENCODING": 400,
            "DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION": 413,
            "DOCUMENT_CONCURRENTLY_UPDATED": 409,
            "EMBEDDING_DIMENSION_MISMATCH": 502,
            "EMBEDDING_CONFIGURATION_MISMATCH": 502,
        }.get(error.code, 400)
        return JSONResponse(status_code=status, content={"error": {"code": error.code}})

    application.include_router(http_router)
    application.include_router(router)
    return application


app = create_app()
