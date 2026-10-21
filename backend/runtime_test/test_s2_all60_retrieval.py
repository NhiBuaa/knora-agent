"""One bounded frozen-query BM25 batch; never generation or semantic evaluation."""

import hashlib
import json
import os
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import httpx
from backend.runtime_test.s2_frozen_restore import load_frozen_inputs, restore_frozen_population
from backend.runtime_test.s2_runtime_guard import require_owned_s2_database
from evals.runners.pdf_retrieval_v3 import build_bm25_comparison, collect_bm25_cases, publish_json
from sqlalchemy import select

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import LexicalHeadTable
from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import QdrantSearchIndex
from knora.answering.stores import RetrievalConfiguration
from knora.infrastructure.lexical_configuration import load_lexical_population
from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration


def test_frozen_all60_native_top200_primary_top8_existing_selector():
    require_owned_s2_database(SessionFactory.kw["bind"].url)
    dataset, chunks, bindings, baseline, protected = load_frozen_inputs()
    evidence_root = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"])
    # A replacement requires a new explicit invocation; failed dispatches are never replayed.
    assert len(list(evidence_root.glob("all60-*"))) < 3, (
        "initial run plus two replacements exhausted"
    )
    run_id = uuid4().hex
    artifact = evidence_root / ("all60-" + run_id)
    artifact.mkdir(parents=True, exist_ok=False)
    configuration = RetrievalConfiguration.bm25_top8_v1()
    population = load_lexical_population(
        configuration, "evals/fixtures/pdf_retrieval_v3_s2/frozen47-lexical-population-v1.json"
    )
    report = {
        "run_id": run_id,
        "status": "incomplete",
        "native_calls": [],
        "corpus_sha256": dataset.corpus_sha256,
        "dataset_sha256": dataset.dataset_sha256,
        "derivation_sha256": "fd5711d2ce76e40dae231cc441feddce61aa36451ae073e4a55f3bbfda3f46f2",
        "protected_inputs": protected,
        "population_profile": asdict(population.profile),
        "population_profile_digest": population.profile.digest(),
        "generation_status": "not_run",
        "semantic_quality": "not_assessed",
        "scope": "retrieval-only comparison with frozen B context; no fresh context claim",
    }
    by_source = defaultdict(list)
    for row in chunks:
        by_source[row["source_key"]].append(row)
    report["source_results"] = [
        {
            "source_key": source.id,
            "raw_sha256": source.sha256,
            "frozen_chunk_count": len(by_source.get(source.id, ())),
            "restore_status": "frozen_chunks"
            if by_source.get(source.id)
            else "not_restored_no_frozen_chunks",
        }
        for source in dataset.sources
    ]

    def capture_request(request):
        assert (request.url.scheme, request.url.host, request.url.port) == (
            "http",
            "127.0.0.1",
            16433,
        )
        assert len(report["native_calls"]) < 200
        if request.url.path.endswith("/points/query"):
            assert (
                sum(call["url"].endswith("/points/query") for call in report["native_calls"]) < 60
            )
        report["native_calls"].append(
            {
                "method": request.method,
                "url": str(request.url),
                "request": json.loads(request.content) if request.content else None,
            }
        )

    def capture_response(response):
        response.read()
        report["native_calls"][-1].update(status=response.status_code, response=response.json())

    try:
        workspace_id, documents = restore_frozen_population(
            SessionFactory, dataset, chunks, evidence_root / "frozen-source-objects"
        )
        report.update(workspace_id=workspace_id, restored_document_ids=documents)
        authority = PostgresSearchIndexStore(SessionFactory)
        with httpx.Client(
            base_url="http://127.0.0.1:16433",
            timeout=20,
            trust_env=False,
            event_hooks={"request": [capture_request], "response": [capture_response]},
        ) as client:
            assert client.get("/").json()["version"] == "1.19.2"
            port = NativeQdrantSearchIndex(
                index=QdrantSearchIndex("s2_all60_" + run_id, population.profile), client=client
            )
            port.ensure_collection()
            generations = []
            for source_key, rows in sorted(by_source.items()):
                with SessionFactory() as session:
                    head = session.scalar(
                        select(LexicalHeadTable).where(
                            LexicalHeadTable.document_id == documents[source_key]
                        )
                    )
                    revision = head.revision if head else 0
                generation = LexicalGeneration(
                    generation_id=str(uuid4()),
                    workspace_id=workspace_id,
                    document_id=documents[source_key],
                    document_version_id=rows[0]["document_version_id"],
                    chunk_set_id=rows[0]["chunk_set_id"],
                    lexical_profile=population.profile,
                    revision=revision + 1,
                    chunks=tuple(
                        LexicalChunk(row["chunk_id"], row["ordinal"], row["content_checksum"])
                        for row in rows
                    ),
                )
                authority.request_generation(generation, expected_revision=revision)
                generations.append(generation)
            report["generations"] = [asdict(g) for g in generations]
            assert len(generations) == 14 and sum(len(g.chunks) for g in generations) == 47
            texts = {row["chunk_id"]: row["content"] for row in chunks}
            points = []
            for generation in generations:
                points.extend(
                    port.index.stage_body(
                        generation, {c.chunk_id: texts[c.chunk_id] for c in generation.chunks}
                    )["points"]
                )
            assert len(points) == 47 <= 64
            # The approved all60 envelope permits exactly one47-point indexing batch.
            staged = client.put(
                f"/collections/{port.index.collection_name}/points?wait=true",
                json={"points": points},
            )
            staged.raise_for_status()
            port._require_completed(staged.json())
            for generation in generations:
                persisted = client.post(
                    f"/collections/{port.index.collection_name}/points",
                    json=port.index.persisted_points_body(generation),
                )
                persisted.raise_for_status()
                assert persisted.json()["status"] == "ok"
                receipt = port.index.parse_stage_response(generation, persisted.json()["result"])
                authority.activate_ready(generation, receipt)
            store = PostgresAnsweringStore(
                SessionFactory, lexical_index=port, lexical_population=population
            )
            # All authority and population guards run in the production store, without mocking.
            store.require_lexical_corpus(workspace_id, configuration.lexical_policy_id)
            rows = collect_bm25_cases(
                dataset,
                store,
                baseline,
                artifact / "captures",
                run_id=run_id,
                workspace_id=workspace_id,
                configuration=configuration,
                derivation_sha256=report["derivation_sha256"],
            )
            comparison = build_bm25_comparison(dataset, rows, baseline, bindings)
            publish_json(artifact / "comparison.json", comparison)
            report["case_count"] = len(rows)
            report["operational_failures"] = [
                {"case_id": row["case_id"], "failure_code": row["failure_code"]}
                for row in rows
                if row["failure_code"]
            ]
            report["native_query_count"] = sum(
                call["url"].endswith("/points/query") for call in report["native_calls"]
            )
            assert len(rows) == comparison["denominator"] == 60
            assert report["native_query_count"] == 60
            assert not report["operational_failures"], report["operational_failures"]
            assert all(row["generation_status"] == "not_run" for row in rows)
        report["status"] = "passed_retrieval_only"
    finally:
        report["protected_inputs_unchanged"] = all(
            hashlib.sha256(Path(path).read_bytes()).hexdigest() == pin
            for path, pin in protected.items()
        )
        publish_json(artifact / "report.json", report)
        assert report["protected_inputs_unchanged"]
