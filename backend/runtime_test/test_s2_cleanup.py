"""Explicit cleanup touches only a new structural fixture, retaining its collection."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import test_s2_search_index_store as lifecycle

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import ChunkTable
from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import QdrantSearchIndex

lexical_generation = lifecycle.lexical_generation


def test_cleanup_retains_pointers_and_removes_only_stale_fixture_points(lexical_generation):
    text = "hạn mức 42"
    checksum = hashlib.sha256(text.encode()).hexdigest()
    first = replace(
        lexical_generation,
        chunks=(replace(lexical_generation.chunks[0], content_checksum=checksum),),
    )
    with SessionFactory.begin() as session:
        session.get(ChunkTable, first.chunks[0].chunk_id).content_checksum = checksum
    second = replace(first, generation_id=str(uuid4()), revision=2)
    run_id = uuid4().hex
    collection = "s2_cleanup_" + run_id
    report = {
        "run_id": run_id,
        "collection": collection,
        "scope": "new cleanup fixture only; accepted evidence untouched",
        "status": "incomplete",
        "calls": [],
    }
    evidence = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]) / f"cleanup-{run_id}.json"

    def admit(request):
        assert request.url.scheme == "http"
        assert request.url.host == "127.0.0.1"
        assert request.url.port == 16433
        assert request.url.path == f"/collections/{collection}" or request.url.path.startswith(
            f"/collections/{collection}/"
        )
        assert report.get("reserved_calls", 0) < 30
        report["reserved_calls"] = report.get("reserved_calls", 0) + 1

    def capture(response):
        response.read()
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

    try:
        with httpx.Client(
            base_url="http://127.0.0.1:16433",
            timeout=10,
            trust_env=False,
            event_hooks={"request": [admit], "response": [capture]},
        ) as client:
            index = NativeQdrantSearchIndex(
                index=QdrantSearchIndex(collection, first.lexical_profile), client=client
            )
            store = PostgresSearchIndexStore(SessionFactory)
            index.ensure_collection()

            def cleanup(generation):
                with SessionFactory.begin() as session:
                    return store.cleanup_generation_in_transaction(
                        session, generation.generation_id, index.remove_generation
                    )

            def remaining(generation):
                response = client.post(
                    f"/collections/{collection}/points",
                    json={"ids": list(generation.point_ids()), "with_payload": False},
                )
                response.raise_for_status()
                return response.json()["result"]

            store.request_generation(first, expected_revision=0)
            store.activate_ready(
                first, index.stage_generation(first, {first.chunks[0].chunk_id: text})
            )
            calls = len(report["calls"])
            assert cleanup(first) == "retained"
            assert len(report["calls"]) == calls
            store.request_generation(second, expected_revision=1)
            assert cleanup(first) == "retained"  # A still serves while B indexes.
            assert cleanup(second) == "retained"
            store.activate_ready(
                second, index.stage_generation(second, {second.chunks[0].chunk_id: text})
            )
            assert cleanup(first) == "removed"
            assert remaining(first) == []
            assert len(remaining(second)) == 1
            assert cleanup(first) == "removed"  # Repeating the delete is idempotent.
            assert cleanup(second) == "retained"
            store.revoke(workspace_id=second.workspace_id, document_id=second.document_id)
            assert cleanup(second) == "removed"
            assert remaining(second) == []
            assert sum(call["url"].endswith("/points/query") for call in report["calls"]) == 0
            report["status"] = "passed"
    finally:
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
