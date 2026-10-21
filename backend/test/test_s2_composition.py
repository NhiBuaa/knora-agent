"""Offline composition and HTTP admission; no database or native runtime acceptance."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knora import main
from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.infrastructure.settings import Settings
from knora.ingestion.job_processing import PdfDerivationHandler
from knora.ingestion.jobs import (
    PdfExtractionSubmissionConfiguration,
    PdfSubmissionConfiguration,
    PdfSubmissionResult,
)
from knora.ingestion.search_indexing import DerivationJobHandler


@pytest.mark.parametrize(
    "config_id,manifest,profile",
    [
        (
            "retrieval-bm25-top8-v1",
            "frozen47-lexical-population-v1.json",
            "bm25-word-frozen47-population-v1",
        ),
        (
            "retrieval-bm25-upload-fixture-top8-v1",
            "upload-lexical-population-v1.json",
            "bm25-word-upload-fixture-population-v1",
        ),
    ],
)
def test_opt_in_wires_pdf_submission_worker_answering_and_lifecycle_without_embedding_or_http(
    monkeypatch, config_id, manifest, profile
):
    settings = Settings(
        _env_file=None,
        retrieval_configuration_id=config_id,
        lexical_population_manifest="evals/fixtures/pdf_retrieval_v3_s2/" + manifest,
        lexical_qdrant_url="http://127.0.0.1:16433",
        lexical_qdrant_collection="s2_composition_fixture",
    )
    monkeypatch.setattr(main, "settings", settings)
    seen = []

    class Jobs:
        def submit_pdf(self, command, principal):
            seen.append(command)
            return PdfSubmissionResult(
                "extract", "created", "queued", "document", "version", "retained"
            )

    app = main.create_app(
        ingestion_jobs=Jobs(),
        workspace_admission_store=None,
        api_key_authenticator=ApiKeyAuthenticator(
            (ApiCredential("key", hash_api_key("secret"), "workspace", True),)
        ),
    )
    assert app.state.answer_question._embedding_provider is None
    assert app.state.answer_question._embedding_configuration is None
    store = app.state.answer_question._store
    population = store._lexical_population
    assert population.profile.id == profile
    assert store._lexical_index.index.profile == population.profile
    worker = app.state.ingestion_worker
    assert isinstance(worker._handler, DerivationJobHandler)
    assert worker._handler._pdf_handler._lexical_population is population
    assert worker._handler._index_handler._lexical_population is population
    assert worker._store._submission_store._retrieval_configuration.id == config_id
    assert worker._store._submission_store._document_reader._lexical_population is population
    assert app.state.document_reader._lexical_population is population
    assert app.state.operator_observability._trace_reader._reader._lexical_population is population
    initialized = []
    monkeypatch.setattr(
        type(store._lexical_index),
        "ensure_collection",
        lambda self: initialized.append(self.index.collection_name),
    )
    http_client = store._lexical_index._client
    assert not http_client.is_closed
    with TestClient(app) as client:
        response = client.post(
            "/v1/workspaces/workspace/documents",
            headers={"X-API-Key": "secret", "Idempotency-Key": "fixture"},
            data={"source_key": "refund"},
            files={
                "file": (
                    "refund-policy.pdf",
                    Path("evals/fixtures/pdf_retrieval_v3_s2/refund-policy.pdf").read_bytes(),
                    "application/pdf",
                )
            },
        )
    assert response.status_code == 202, response.text
    config = seen[0].configuration
    assert isinstance(config, PdfExtractionSubmissionConfiguration)
    assert config.lexical_profile == population.profile
    assert config.parser_configuration_id == "pdf-parser-pypdf-6-14-2-layout-lines-v2"
    assert initialized == ["s2_composition_fixture"]
    assert http_client.is_closed


def test_dense_default_keeps_pdf_derivation_and_embedding_submission(monkeypatch):
    monkeypatch.setattr(main, "settings", Settings(_env_file=None))
    app = main.create_app(workspace_admission_store=None)
    assert isinstance(app.state.pdf_submission_configuration, PdfSubmissionConfiguration)
    assert isinstance(app.state.ingestion_worker._handler, PdfDerivationHandler)
    assert app.state.answer_question._store._lexical_index is None


@pytest.mark.parametrize(
    "missing", ["lexical_population_manifest", "lexical_qdrant_url", "lexical_qdrant_collection"]
)
def test_opt_in_fails_closed_without_complete_runtime_configuration(monkeypatch, missing):
    values = dict(
        retrieval_configuration_id="retrieval-bm25-upload-fixture-top8-v1",
        lexical_population_manifest="evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json",
        lexical_qdrant_url="http://127.0.0.1:16433",
        lexical_qdrant_collection="s2_composition_fixture",
    )
    values[missing] = None
    monkeypatch.setattr(main, "settings", Settings(_env_file=None, **values))
    with pytest.raises(ValueError, match="lexical"):
        main.create_app(workspace_admission_store=None)


def test_failed_native_startup_closes_its_client(monkeypatch):
    from knora.ingestion.search_indexing import LexicalProjectionUnavailable

    monkeypatch.setattr(
        main,
        "settings",
        Settings(
            _env_file=None,
            retrieval_configuration_id="retrieval-bm25-upload-fixture-top8-v1",
            lexical_population_manifest="evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json",
            lexical_qdrant_url="http://127.0.0.1:16433",
            lexical_qdrant_collection="s2_composition_fixture",
        ),
    )
    app = main.create_app(workspace_admission_store=None)
    projection = app.state.answer_question._store._lexical_index

    def unavailable(self):
        raise LexicalProjectionUnavailable("offline startup fixture")

    monkeypatch.setattr(type(projection), "ensure_collection", unavailable)
    with pytest.raises(LexicalProjectionUnavailable), TestClient(app):
        pytest.fail("startup must not become ready")
    assert projection._client.is_closed
