"""Native projection query followed by real PostgreSQL eligibility/text hydration."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import test_s2_search_index_store as lifecycle
from test_s2_lexical_retrieval import _structural_population

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.lexical_retrieval import retrieve_lexical_candidates
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import ChunkTable, DocumentTable
from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import QdrantSearchIndex
from knora.answering.lexical import validate_bm25_result
from knora.answering.stores import RetrievalConfiguration
from knora.domain.errors import KnoraError

lexical_generation = lifecycle.lexical_generation


@pytest.mark.parametrize("archive_after_query", [False, True])
def test_native_query_hydrates_only_still_authorized_postgres_content(
    lexical_generation, archive_after_query
):
    generation = lexical_generation
    checksum = hashlib.sha256("hạn mức 42".encode()).hexdigest()
    generation = replace(
        generation, chunks=(replace(generation.chunks[0], content_checksum=checksum),)
    )
    with SessionFactory.begin() as session:
        session.get(ChunkTable, generation.chunks[0].chunk_id).content_checksum = checksum
    store = PostgresSearchIndexStore(SessionFactory)
    store.request_generation(generation, expected_revision=0)
    run_id = uuid4().hex
    evidence = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]) / ("pg-native-" + run_id + ".json")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "scope": "structural PG/native integration, not application E2E",
        "population_scope": "structural mock; no measured-population acceptance",
        "archive_after_query": archive_after_query,
        "calls": [],
        "status": "incomplete",
    }

    def capture(response):
        response.read()
        assert response.request.url.host == "127.0.0.1" and response.request.url.port == 16433
        assert len(report["calls"]) < 20
        report["calls"].append(
            {
                "method": response.request.method,
                "url": str(response.request.url),
                "request": json.loads(response.request.content)
                if response.request.content
                else None,
                "status": response.status_code,
                "response": response.json(),
            }
        )
        if archive_after_query and response.request.url.path.endswith("/points/query"):
            with SessionFactory.begin() as session:
                session.get(DocumentTable, generation.document_id).archived = True

    configuration = replace(
        RetrievalConfiguration.bm25_diagnostic_v1(), lexical_policy_id=generation.lexical_profile.id
    )
    try:
        with httpx.Client(
            base_url="http://127.0.0.1:16433",
            timeout=10,
            trust_env=False,
            event_hooks={"response": [capture]},
        ) as client:
            port = NativeQdrantSearchIndex(
                index=QdrantSearchIndex("s2_pg_native_" + run_id, generation.lexical_profile),
                client=client,
            )
            port.ensure_collection()
            receipt = port.stage_generation(
                generation, {generation.chunks[0].chunk_id: "hạn mức 42"}
            )
            store.activate_ready(generation, receipt)
            if archive_after_query:
                with pytest.raises(KnoraError) as caught:
                    retrieve_lexical_candidates(
                        SessionFactory,
                        generation.workspace_id,
                        "42",
                        configuration,
                        port,
                        population=_structural_population(generation),
                    )
                assert caught.value.code == "LEXICAL_RETRIEVAL_UNAVAILABLE"
            else:
                result = retrieve_lexical_candidates(
                    SessionFactory,
                    generation.workspace_id,
                    "42",
                    configuration,
                    port,
                    population=_structural_population(generation),
                )
                validate_bm25_result(
                    result, workspace_id=generation.workspace_id, configuration=configuration
                )
                assert [c.chunk_id for c in result.candidates] == [generation.chunks[0].chunk_id]
                assert result.candidates[0].content == "hạn mức 42"
                assert result.candidates[0].source_name == "isolated.pdf"
            assert sum(call["url"].endswith("/points/query") for call in report["calls"]) == 1
            report["status"] = "passed"
    finally:
        evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
