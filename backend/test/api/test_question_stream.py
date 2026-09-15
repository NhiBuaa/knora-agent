from dataclasses import dataclass

from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.answering.interface import QuestionCommand, QuestionEvent
from knora.main import create_app

RAW_KEY = "stream-key-a"


@dataclass
class RecordingStreamService:
    calls: list[tuple[QuestionCommand, object]]

    async def execute_stream(self, command, principal):
        self.calls.append((command, principal))
        yield QuestionEvent(stage="started", payload={})
        yield QuestionEvent(stage="final_validated", payload={"answer": "validated"}, terminal=True)


def client_with(service: RecordingStreamService) -> TestClient:
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="stream-key",
                key_hash=hash_api_key(RAW_KEY),
                workspace_id="workspace-a",
                enabled=True,
            ),
        )
    )
    return TestClient(create_app(answer_question=service, api_key_authenticator=authenticator))


def test_question_stream_returns_ordered_sse_events() -> None:
    service = RecordingStreamService([])

    response = client_with(service).post(
        "/v1/questions/stream",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "question": "What is the policy?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == (
        'event: started\ndata: {}\n\n'
        'event: final_validated\ndata: {"answer":"validated"}\n\n'
    )
    assert service.calls[0][0] == QuestionCommand("workspace-a", "What is the policy?")


def test_question_stream_rejects_workspace_mismatch_before_streaming() -> None:
    service = RecordingStreamService([])

    response = client_with(service).post(
        "/v1/questions/stream",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-b", "question": "What is the policy?"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert service.calls == []
