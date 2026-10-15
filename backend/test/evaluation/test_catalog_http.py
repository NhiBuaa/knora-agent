from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.domain.access import WorkspacePrincipal
from knora.evaluation.contracts import LegacyDatasetReference
from knora.main import create_app


def client_with_catalog(capabilities=("operator:read",)):
    from knora.adapters.http.evaluation_catalog import router

    calls = []
    reference = LegacyDatasetReference(
        format="m3-native-v1",
        dataset_id="m3-dataset-v1",
        version=1,
        workspace_id="workspace-a",
        native_digest="a" * 64,
        metric_contract="m3-retrieval-metrics-v1",
    )
    entry = SimpleNamespace(
        reference=reference,
        dataset=SimpleNamespace(
            cases=(
                SimpleNamespace(
                    id="answer-1",
                    question="Public question",
                    expected_behavior="ANSWER",
                    category="single-hop",
                ),
            )
        ),
    )

    def native(workspace_id):
        calls.append(("native", workspace_id))
        return (entry,)

    def drafts(workspace_id, principal):
        calls.append(("drafts", workspace_id))
        return (
            SimpleNamespace(
                id="draft-1", workspace_id=workspace_id, name="PDF draft", status="DRAFT"
            ),
        )

    class ScopedAuthenticator(ApiKeyAuthenticator):
        def authenticate(self, raw_key):
            authenticated = super().authenticate(raw_key)
            return WorkspacePrincipal(
                authenticated.workspace_id, authenticated.key_id, capabilities
            )

    app = create_app(
        api_key_authenticator=ScopedAuthenticator(
            (
                ApiCredential(
                    key_id="catalog",
                    key_hash=hash_api_key("catalog-key"),
                    workspace_id="workspace-a",
                    enabled=True,
                ),
            )
        )
    )
    app.include_router(router)
    app.state.evaluation_catalog = SimpleNamespace(list_datasets=native)
    app.state.dataset_service = SimpleNamespace(list_datasets=drafts)
    return TestClient(app), calls


def test_catalog_combines_builder_and_native_without_rewriting_identity():
    client, calls = client_with_catalog()
    response = client.get(
        "/v1/workspaces/workspace-a/evaluation/datasets", headers={"X-API-Key": "catalog-key"}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    items = response.json()["items"]
    assert [item["id"] for item in items] == ["draft-1", "m3-dataset-v1"]
    assert items[0]["reference"] is None
    assert items[0]["case_count"] == 0
    assert items[1]["reference"]["native_digest"] == "a" * 64
    assert items[1]["reference"]["metric_contract"] == "m3-retrieval-metrics-v1"
    assert items[1]["cases"][0]["expected_behavior"] == "ANSWER"
    assert items[1]["case_count"] == 1
    assert calls == [("drafts", "workspace-a"), ("native", "workspace-a")]


@pytest.mark.parametrize(
    ("workspace", "capabilities"),
    [("workspace-b", ("operator:read",)), ("workspace-a", ("documents:read",))],
)
def test_catalog_denies_before_either_source_lookup(workspace, capabilities):
    client, calls = client_with_catalog(capabilities)
    response = client.get(
        f"/v1/workspaces/{workspace}/evaluation/datasets", headers={"X-API-Key": "catalog-key"}
    )
    assert response.status_code == 403
    assert calls == []
