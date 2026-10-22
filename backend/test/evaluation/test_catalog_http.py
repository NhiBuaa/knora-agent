from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.domain.access import WorkspacePrincipal
from knora.evaluation.contracts import DatasetReference, LegacyDatasetReference
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
                id="draft-1", workspace_id=workspace_id, name="PDF draft", status="DRAFT", cases=()
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


def test_catalog_uses_frozen_population_and_never_attaches_old_digest_to_new_draft():
    client, _ = client_with_catalog()
    accepted = SimpleNamespace(
        case_id="accepted", question="Question?", expected="ANSWER", category="single-hop"
    )
    rejected = SimpleNamespace(
        case_id="rejected", question="Rejected?", expected="ANSWER", category="single-hop"
    )
    reference = DatasetReference(
        dataset_id="pdf-1",
        version=1,
        workspace_id="workspace-a",
        format="pdf-gold-v1",
        metric_contract="pdf-metrics-v1",
        digest="b" * 64,
    )
    draft = SimpleNamespace(
        id="pdf-1",
        workspace_id="workspace-a",
        name="PDF",
        status="FROZEN",
        cases=(accepted, rejected),
        reference=reference,
    )
    client.app.state.dataset_service = SimpleNamespace(
        list_datasets=lambda *args: (draft,),
        get_frozen_dataset=lambda *args: SimpleNamespace(
            gold=SimpleNamespace(cases=(accepted,)), reference=reference
        ),
    )
    headers = {"X-API-Key": "catalog-key"}
    frozen = client.get("/v1/workspaces/workspace-a/evaluation/datasets", headers=headers).json()[
        "items"
    ][0]
    assert frozen["case_count"] == 1
    assert [case["id"] for case in frozen["cases"]] == ["accepted"]
    assert frozen["reference"]["digest"] == reference.digest
    draft.status = "DRAFT"
    editing = client.get("/v1/workspaces/workspace-a/evaluation/datasets", headers=headers).json()[
        "items"
    ][0]
    assert editing["case_count"] == 2
    assert editing["reference"] is None
