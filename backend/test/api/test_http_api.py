from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.main import create_app

RAW_KEY = "test-demo-key"
client = TestClient(
    create_app(
        api_key_authenticator=ApiKeyAuthenticator(
            (
                ApiCredential(
                    key_id="test-demo",
                    key_hash=hash_api_key(RAW_KEY),
                    workspace_id="demo",
                    enabled=True,
                ),
            )
        )
    )
)


def test_health_reports_service_is_ready() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knora-agent"}


def test_question_endpoint_returns_a_cited_answer_for_demo_corpus() -> None:
    response = client.post(
        "/v1/questions",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "demo", "question": "Chính sách hoàn tiền là gì?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["citations"][0]["source"] == "refund-policy.md"


def test_question_endpoint_rejects_blank_questions() -> None:
    response = client.post(
        "/v1/questions",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "demo", "question": "   "},
    )

    assert response.status_code == 422
