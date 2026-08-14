import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import ChunkTable, QuestionTraceTable
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.retrieval_configuration import (
    CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
    resolve_retrieval_configuration,
)
from knora.answering.retrieval_v2 import normalize_fts_m3_or_v2
from knora.domain.access import WorkspacePrincipal
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.gemini.embedding import GeminiEmbeddingProvider

WORKSPACE_ID = "evaluation-m3-v1"


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def trace_projection(trace_id: str) -> dict[str, Any]:
    with SessionFactory() as session:
        trace = session.get(QuestionTraceTable, trace_id)
        if trace is None or trace.workspace_id != WORKSPACE_ID:
            raise ValueError("exact production trace is missing")
        chunk_ids = [item["chunk_id"] for item in trace.candidate_decisions]
        chunks = session.execute(
            select(ChunkTable.id, ChunkTable.ordinal).where(ChunkTable.id.in_(chunk_ids))
        ).all()
        ordinals = {chunk_id: ordinal for chunk_id, ordinal in chunks}
        return {
            "trace_id": trace.id,
            "workspace_id": trace.workspace_id,
            "retrieval_configuration_id": trace.retrieval_configuration_id,
            "embedding_configuration_id": trace.embedding_configuration_id,
            "fusion_policy_id": trace.fusion_policy_version,
            "embedding_set_ids": trace.embedding_set_ids,
            "chunk_set_ids": trace.chunk_set_ids,
            "retrieved_chunk_ids": trace.retrieved_chunk_ids,
            "decision": trace.decision,
            "generation_status": trace.generation_status,
            "alias_mapping": trace.alias_mapping,
            "parsed_markers": trace.parsed_markers,
            "validation_outcome": trace.validation_outcome,
            "candidate_decisions": [
                {
                    **item,
                    "chunk_ordinal": ordinals[item["chunk_id"]],
                }
                for item in trace.candidate_decisions
            ],
        }


async def execute(output_path: Path) -> None:
    api_key = os.environ.get("KNORA_GEMINI_API_KEY")
    if not api_key:
        raise ValueError("runtime Gemini credential is absent")
    provider = GeminiEmbeddingProvider(api_key=api_key)
    configurations = {
        "semantic-vector": (
            "retrieval-m3-vector-v2",
            "How long will normal delivery need?",
        ),
        "lexical-hybrid": (
            "retrieval-m3-rrf-v2",
            "billing period",
        ),
        "mixed-hybrid": (
            "retrieval-m3-rrf-v2",
            "Where is a refund paid and how long is standard delivery?",
        ),
    }
    runs = []
    try:
        for label, (configuration_id, question) in configurations.items():
            service = AnswerQuestion(
                embedding_provider=provider,
                generation_provider=DeterministicGenerationProvider(),
                store=PostgresAnsweringStore(SessionFactory),
                embedding_configuration=EmbeddingConfiguration.gemini_m3(),
                retrieval_configuration=resolve_retrieval_configuration(
                    configuration_id,
                    vector_min_similarity=CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
                ),
            )
            result = await service.execute(
                QuestionCommand(workspace_id=WORKSPACE_ID, question=question),
                WorkspacePrincipal(
                    workspace_id=WORKSPACE_ID, key_id="issue-56-acceptance"
                ),
            )
            projection = trace_projection(result.trace_id)
            runs.append(
                {
                    "label": label,
                    "question_sha256": sha256(question.encode()),
                    "result_decision": result.decision,
                    "citation_count": len(result.citations),
                    "trace": projection,
                }
            )
    finally:
        provider.close()
        api_key = ""
    lexical_cases = {
        "refund-period": "What is the REFUND—period?",
        "numeric": "30 days",
        "operator-like": "' OR 1=1; refund refund",
        "empty": "the and what",
        "unicode": "ＲＥＦＵＮＤ\u0301\u2003period",
        "punctuation": "refund!!!...period",
        "long-token": "x" * 5000,
    }
    lexical_results = {
        label: normalize_fts_m3_or_v2(value)
        for label, value in lexical_cases.items()
    }
    evidence = {
        "schema_version": 1,
        "workspace_id": WORKSPACE_ID,
        "production_seam": "AnswerQuestion->AnsweringStore.retrieve_candidates",
        "calibrated_vector_min_similarity": format(
            CALIBRATED_M3_VECTOR_MIN_SIMILARITY, ".12f"
        ),
        "runs": runs,
        "lexical_adversarial_results": lexical_results,
        "empty_query_yields_no_lexemes": lexical_results["empty"] == (),
        "credential_retained": False,
        "provider_vectors_retained": False,
        "provider_payloads_retained": False,
    }
    for run in runs:
        trace = run["trace"]
        if trace["embedding_configuration_id"] != "embedding-gemini-m1-v1":
            raise ValueError("production trace embedding configuration mismatch")
        decisions = trace["candidate_decisions"]
        if any(
            item.get("vector_contribution")
            and item["vector_contribution"]["branch_rank"] > 8
            for item in decisions
        ):
            raise ValueError("vector candidate budget exceeded")
        if any(
            item.get("fts_contribution")
            and item["fts_contribution"]["branch_rank"] > 8
            for item in decisions
        ):
            raise ValueError("FTS candidate budget exceeded")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_json(evidence))
    print(
        json.dumps(
            {
                "status": "PASSED",
                "run_count": len(runs),
                "evidence_sha256": sha256(output_path.read_bytes()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(execute(Path(sys.argv[1]).resolve()))
