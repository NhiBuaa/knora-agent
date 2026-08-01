from dataclasses import dataclass, field
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    EmbeddingSetTable,
    QuestionTraceTable,
    WorkspaceTable,
)
from knora.answering.interface import CitationProjection, QuestionResult
from knora.answering.module import AnswerQuestion
from knora.answering.stores import QuestionTraceRecord
from knora.domain.errors import KnoraError
from knora.main import create_app
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration

RAW_KEY = "question-key-a"


@dataclass
class RecordingAnswerQuestion:
    calls: list[tuple] = field(default_factory=list)

    async def execute(self, command, principal) -> QuestionResult:
        self.calls.append((command, principal))
        return QuestionResult(
            decision="ANSWER",
            answer="Refunds are available for thirty days. [[E1]]",
            citations=(
                CitationProjection(
                    evidence_id="E1",
                    document_id="document-1",
                    document_version_id="version-1",
                    source_key="support/refunds",
                    source_name="refunds.md",
                    heading_path=("Refunds",),
                    start_line=3,
                    end_line=4,
                    excerpt="Refunds are available for thirty days.",
                    content_checksum="sha256:abc",
                ),
            ),
            refusal_reason=None,
            trace_id="trace-1",
        )


class InvalidGenerationService:
    async def execute(self, command, principal):
        raise KnoraError("GENERATION_OUTPUT_INVALID")


@dataclass
class EmptyAnsweringStore:
    traces: list[QuestionTraceRecord] = field(default_factory=list)

    def retrieve_candidates(self, **kwargs):
        return ()

    def persist_trace(self, trace: QuestionTraceRecord) -> str:
        self.traces.append(trace)
        return "trace-refusal"


class QueryEmbeddingProvider:
    def embed(self, texts, configuration):
        return EmbeddingBatch(
            vectors=(tuple([0.0] * configuration.dimensions),),
            provider=configuration.provider,
            model=configuration.model,
        )


@dataclass
class CountingGenerationProvider:
    calls: int = 0

    async def generate(self, **kwargs):
        self.calls += 1
        raise AssertionError("generation must not run without qualified evidence")


def client_with(service: RecordingAnswerQuestion) -> TestClient:
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="question-a",
                key_hash=hash_api_key(RAW_KEY),
                workspace_id="workspace-a",
                enabled=True,
            ),
        )
    )
    return TestClient(
        create_app(answer_question=service, api_key_authenticator=authenticator)
    )


def test_question_http_contract_projects_validated_citations() -> None:
    service = RecordingAnswerQuestion()

    response = client_with(service).post(
        "/v1/questions",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "question": "What is the refund policy?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "decision": "ANSWER",
        "answer": "Refunds are available for thirty days. [[E1]]",
        "citations": [
            {
                "evidence_id": "E1",
                "document_id": "document-1",
                "document_version_id": "version-1",
                "source_key": "support/refunds",
                "source_name": "refunds.md",
                "heading_path": ["Refunds"],
                "start_line": 3,
                "end_line": 4,
                "excerpt": "Refunds are available for thirty days.",
                "content_checksum": "sha256:abc",
            }
        ],
        "refusal_reason": None,
        "trace_id": "trace-1",
    }
    command, principal = service.calls[0]
    assert command.workspace_id == "workspace-a"
    assert principal.key_id == "question-a"


def test_question_workspace_mismatch_is_rejected_before_application_call() -> None:
    service = RecordingAnswerQuestion()

    response = client_with(service).post(
        "/v1/questions",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-b", "question": "What is the refund policy?"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert service.calls == []


def test_missing_and_invalid_keys_are_rejected_before_question_application_call() -> None:
    service = RecordingAnswerQuestion()
    client = client_with(service)

    missing = client.post(
        "/v1/questions",
        json={"workspace_id": "workspace-a", "question": "What is the refund policy?"},
    )
    invalid = client.post(
        "/v1/questions",
        headers={"X-API-Key": "unknown-key"},
        json={"workspace_id": "workspace-a", "question": "What is the refund policy?"},
    )

    assert missing.status_code == 401
    assert missing.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert invalid.status_code == 401
    assert invalid.json() == missing.json()
    assert service.calls == []


def test_invalid_generation_maps_to_explicit_http_502() -> None:
    response = client_with(InvalidGenerationService()).post(
        "/v1/questions",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "question": "What is the refund policy?"},
    )

    assert response.status_code == 502
    assert response.json() == {"error": {"code": "GENERATION_OUTPUT_INVALID"}}


def test_no_qualified_evidence_returns_deterministic_http_refusal() -> None:
    store = EmptyAnsweringStore()
    generation_provider = CountingGenerationProvider()
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=generation_provider,
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    response = client_with(service).post(
        "/v1/questions",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "question": "Who won the World Cup?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "decision": "REFUSAL",
        "answer": "Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.",
        "citations": [],
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
        "trace_id": "trace-refusal",
    }
    assert generation_provider.calls == 0
    assert store.traces[0].generation_status == "not_called"


def test_http_question_uses_active_postgres_corpus_and_persists_trace() -> None:
    workspace_id = f"question-http-{uuid4()}"
    raw_key = f"key-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Question HTTP integration"))
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="question-integration",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    client = TestClient(create_app(api_key_authenticator=authenticator))

    ingested = client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        headers={"X-API-Key": raw_key},
        data={"source_key": "support/refunds"},
        files={
            "file": (
                "refunds.md",
                b"# Refunds\n\nRefund requests are accepted within thirty days.\n",
            )
        },
    )
    assert ingested.status_code == 201

    with SessionFactory() as session:
        active_content = session.scalar(
            select(ChunkTable.content)
            .join(ChunkSetTable, ChunkSetTable.id == ChunkTable.chunk_set_id)
            .join(EmbeddingSetTable, EmbeddingSetTable.chunk_set_id == ChunkSetTable.id)
            .join(DocumentTable, DocumentTable.active_embedding_set_id == EmbeddingSetTable.id)
            .where(DocumentTable.workspace_id == workspace_id)
            .order_by(ChunkTable.ordinal)
        )

    response = client.post(
        "/v1/questions",
        headers={"X-API-Key": raw_key},
        json={"workspace_id": workspace_id, "question": active_content},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "ANSWER"
    assert payload["answer"].endswith("[[E1]]")
    assert payload["citations"][0]["source_key"] == "support/refunds"
    assert payload["citations"][0]["excerpt"] == active_content
    assert payload["refusal_reason"] is None
    with SessionFactory() as session:
        trace = session.get(QuestionTraceTable, payload["trace_id"])
        assert trace is not None
        assert trace.workspace_id == workspace_id
        assert trace.decision == "ANSWER"
        assert trace.validation_outcome == "valid"
        assert trace.retrieved_chunk_ids
        assert trace.alias_mapping == {"E1": trace.retrieved_chunk_ids[0]}
