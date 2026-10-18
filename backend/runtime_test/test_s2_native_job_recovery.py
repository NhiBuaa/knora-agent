"""Crash after native readback, then restage through the replacement durable attempt."""

import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import test_s2_job_recovery as recovery

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import IngestionJobTable, LexicalHeadTable
from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import QdrantSearchIndex
from knora.ingestion.job_processing import (
    FinalizationApplied,
    InvalidTransition,
    TransitionOperationId,
)
from knora.ingestion.search_indexing import LexicalIndexSuccess

extraction_job = recovery.extraction_job
loaded_index_job = recovery.loaded_index_job


def test_crash_after_native_readback_recovers_without_duplicate_points(loaded_index_job):
    store, old_claim, _ = loaded_index_job
    authority = PostgresSearchIndexStore(SessionFactory)
    loaded = authority.load_generation(old_claim.work)
    generation = loaded.generation
    run_id = uuid4().hex
    evidence = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]) / ("native-recovery-" + run_id + ".json")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "scope": "crash/replay structural fixture",
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

    try:
        with httpx.Client(
            base_url="http://127.0.0.1:16433",
            timeout=10,
            trust_env=False,
            event_hooks={"response": [capture]},
        ) as client:
            assert client.get("/").json()["version"] == "1.19.2"
            port = NativeQdrantSearchIndex(
                index=QdrantSearchIndex("s2_recovery_" + run_id, generation.lexical_profile),
                client=client,
            )
            port.ensure_collection()
            receipt = port.stage_generation(generation, dict(loaded.chunk_texts))
            with SessionFactory() as session:
                assert (
                    session.get(LexicalHeadTable, old_claim.work.document_id).active_generation_id
                    is None
                )
                assert session.get(IngestionJobTable, old_claim.token.job_id).status == "processing"
            # The worker is gone after verified readback and before PG finalization.
            replacement = recovery.recover_expired_index(store, old_claim)
            assert isinstance(
                store.finalize_success(
                    operation_id=TransitionOperationId(uuid4().hex),
                    claim=old_claim,
                    success=LexicalIndexSuccess(generation, receipt),
                ),
                InvalidTransition,
            )
            reloaded = authority.load_generation(replacement.work)
            assert reloaded == loaded
            replay_receipt = port.stage_generation(reloaded.generation, dict(reloaded.chunk_texts))
            result = store.finalize_success(
                operation_id=TransitionOperationId(uuid4().hex),
                claim=replacement,
                success=LexicalIndexSuccess(reloaded.generation, replay_receipt),
            )
            assert isinstance(result, FinalizationApplied) and result.outcome == "succeeded"
            count = client.post(
                f"/collections/{port.index.collection_name}/points/count", json={"exact": True}
            )
            count.raise_for_status()
            assert count.json()["result"]["count"] == 1
            with SessionFactory() as session:
                head = session.get(LexicalHeadTable, old_claim.work.document_id)
                assert head.active_generation_id == generation.generation_id and head.revision == 1
                job = session.get(IngestionJobTable, old_claim.token.job_id)
                assert job.attempt_count == 2 and job.status == "succeeded"
            report["status"] = "passed"
    finally:
        evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
