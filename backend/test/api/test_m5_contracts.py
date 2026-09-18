"""M5 public REST, SSE, and schema compatibility checks."""

import json
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.answering.interface import QuestionCommand, QuestionEvent
from knora.main import create_app

ROOT = Path(__file__).parents[3]
OPENAPI = json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))
RAW_KEY = "m5-contract-key"

REQUIRED_PATHS = {
    "/health",
    "/v1/questions",
    "/v1/questions/stream",
    "/v1/workspaces/{workspace_id}/documents",
    "/v1/workspaces/{workspace_id}/documents/{document_id}",
    "/v1/workspaces/{workspace_id}/ingestion-jobs/{ingestion_job_id}",
    "/v1/workspaces/{workspace_id}/operator/traces/{trace_id}",
    "/v1/workspaces/{workspace_id}/operator/evaluations/{report_id}",
    "/v1/workspaces/{workspace_id}/operator/operations",
    "/v1/workspaces/{workspace_id}/operator/tool-lifecycle",
}


def _schema(name: str) -> dict:
    return OPENAPI["components"]["schemas"][name]


def test_m5_openapi_exposes_required_paths_and_stable_public_schemas() -> None:
    assert OPENAPI["paths"].keys() >= REQUIRED_PATHS
    assert OPENAPI["paths"]["/v1/questions/stream"]["post"]["responses"]["200"]["content"] == {
        "text/event-stream": {"schema": {"type": "string"}}
    }

    assert set(_schema("QuestionRequest")["required"]) == {"workspace_id", "question"}
    assert set(_schema("QuestionResponse")["required"]) >= {
        "answer",
        "citations",
        "decision",
        "refusal_reason",
        "trace_id",
        "workspace_id",
    }
    lifecycle = _schema("ToolLifecycleResponse")["properties"]
    assert lifecycle["availability"]["enum"] == ["available", "unavailable", "observation_failure"]
    assert set(_schema("ToolLifecycleItemResponse")["required"]) == {"proposal", "approval"}


def test_m5_checked_contract_contains_no_secret_or_raw_provider_fields() -> None:
    serialized = json.dumps(OPENAPI, sort_keys=True).lower()
    private_names = (
        "api_key", "key_hash", "secret_key", "raw_token", "provider_api_key", "authorization_token"
    )
    for private_name in private_names:
        assert private_name not in serialized


@dataclass
class _StreamService:
    calls: list[QuestionCommand]

    async def execute_stream(self, command, principal):
        self.calls.append(command)
        yield QuestionEvent(stage="started", payload={})
        yield QuestionEvent(stage="final_validated", payload={"answer": "ok"}, terminal=True)


def test_m5_sse_public_seam_emits_one_ordered_terminal_event() -> None:
    service = _StreamService([])
    credential = ApiCredential("m5-contract", hash_api_key(RAW_KEY), "workspace-a", True)
    auth = ApiKeyAuthenticator((credential,))
    client = TestClient(create_app(answer_question=service, api_key_authenticator=auth))

    response = client.post(
        "/v1/questions/stream",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "question": "What is known?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    records = [record for record in response.text.split("\n\n") if record]
    assert [record.splitlines()[0] for record in records] == [
        "event: started", "event: final_validated"
    ]
    assert sum(record.startswith("event: final_validated") for record in records) == 1
    assert service.calls == [QuestionCommand("workspace-a", "What is known?")]
