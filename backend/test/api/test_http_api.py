from fastapi.testclient import TestClient

from knora.main import app

client = TestClient(app)


def test_health_reports_service_is_ready() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knora-agent"}


def test_question_endpoint_returns_a_cited_answer_for_demo_corpus() -> None:
    response = client.post(
        "/v1/questions",
        json={"workspace_id": "demo", "question": "Chính sách hoàn tiền là gì?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is False
    assert payload["citations"][0]["source"] == "refund-policy.md"


def test_question_endpoint_rejects_blank_questions() -> None:
    response = client.post(
        "/v1/questions",
        json={"workspace_id": "demo", "question": "   "},
    )

    assert response.status_code == 422
