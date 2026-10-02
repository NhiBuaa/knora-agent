import asyncio
import json
import os
import subprocess
import sys
from dataclasses import replace

import httpx
import pytest

from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration
from knora.providers.generation import GenerationResult


def candidate(**changes):
    values = dict(
        document_id="doc",
        document_version_id="version",
        source_key="source.pdf",
        source_name="source.pdf",
        chunk_set_id="set",
        embedding_set_id="embedding",
        embedding_configuration_id="profile",
        chunk_id="chunk",
        chunk_ordinal=0,
        heading_path=(),
        start_line=1,
        end_line=2,
        content="PRIVATE EVIDENCE",
        content_checksum="a" * 64,
        token_count=10,
        cosine_distance=0.2,
        similarity=0.8,
    )
    values.update(changes)
    return RetrievalCandidate(**values)


class Provider:
    def __init__(self, result):
        self.result = result

    async def generate(self, *, question, evidence):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize(
    ("result", "outcome"),
    [
        (GenerationResult("REFUSAL", None, (), "INSUFFICIENT_EVIDENCE"), "MODEL_REFUSAL"),
        (GenerationResult("ANSWER", "PRIVATE ANSWER [[E1]]", ("E1",), None), "UNEXPECTED_ANSWER"),
        (GenerationResult("ANSWER", "PRIVATE ANSWER [[E9]]", ("E9",), None), "INVALID_OUTPUT"),
        (
            GenerationResult("REFUSAL", "PRIVATE ANSWER", (), "INSUFFICIENT_EVIDENCE"),
            "INVALID_OUTPUT",
        ),
        (RuntimeError("PRIVATE SECRET"), "PROVIDER_ERROR"),
    ],
)
def test_classifies_negative_generation_without_exporting_content(result, outcome):
    from evals.runners.ollama_refusal import evaluate_case

    row = asyncio.run(
        evaluate_case(
            case_id="negative",
            question="PRIVATE QUESTION",
            candidates=(candidate(),),
            configuration=RetrievalConfiguration.milestone_one(),
            provider=Provider(result),
        )
    )
    assert row["outcome"] == outcome
    assert row["generation_called"] is True
    assert "PRIVATE" not in json.dumps(row)


def test_no_evidence_does_not_count_as_model_refusal():
    from evals.runners.ollama_refusal import evaluate_case, summarize

    row = asyncio.run(
        evaluate_case(
            case_id="negative",
            question="unknown",
            candidates=(),
            configuration=RetrievalConfiguration.milestone_one(),
            provider=Provider(AssertionError("must not call")),
        )
    )
    report = summarize([row])
    assert row["outcome"] == "PRE_GENERATION_REFUSAL"
    assert row["generation_called"] is False
    assert report["model_refusal_rate"] is None
    assert report["conversation_gate"] == "NOT_EVALUATED"


def test_selection_respects_threshold_and_production_token_budget():
    from evals.runners.ollama_refusal import evaluate_case

    row = asyncio.run(
        evaluate_case(
            case_id="negative",
            question="unknown",
            candidates=(candidate(similarity=0.2), candidate(token_count=3001)),
            configuration=RetrievalConfiguration.milestone_one(),
            provider=Provider(AssertionError("must not call")),
        )
    )
    assert row["outcome"] == "PRE_GENERATION_REFUSAL"
    assert row["evidence_checksums"] == []


def test_summary_counts_failures_in_model_denominator_and_rejects_empty():
    from evals.runners.ollama_refusal import summarize

    rows = [
        {"outcome": outcome, "generation_called": called}
        for outcome, called in [
            ("MODEL_REFUSAL", True),
            ("UNEXPECTED_ANSWER", True),
            ("PROVIDER_ERROR", True),
            ("PRE_GENERATION_REFUSAL", False),
        ]
    ]
    assert summarize(rows)["model_refusal_rate"] == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="empty"):
        summarize([])


def test_cli_failure_does_not_print_credentials_or_create_report(tmp_path):
    output = tmp_path / "report.json"
    environment = dict(os.environ, KNORA_DATABASE_URL="PRIVATE CONNECTION SECRET")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.runners.ollama_refusal",
            "--dataset",
            "evals/datasets/vietnamese_rag_v1.jsonl",
            "--manifest",
            "evals/datasets/vietnamese_rag_v1.manifest.json",
            "--workspace-id",
            "workspace",
            "--threshold",
            "0.5",
            "--output",
            str(output),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "PRIVATE" not in result.stdout + result.stderr
    assert "no complete report" in result.stderr
    assert not output.exists()


def test_real_adapter_malformed_json_is_invalid_output():
    from evals.runners.ollama_refusal import evaluate_case

    from knora.providers.ollama.generation import OllamaGenerationProvider

    def response(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": "a" * 64}]})
        return httpx.Response(
            200, json={"message": {"content": "PRIVATE MALFORMED JSON"}, "done": True}
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            provider = OllamaGenerationProvider(
                base_url="http://ollama.test",
                expected_digest="sha256:" + "a" * 64,
                client=client,
            )
            return await evaluate_case(
                case_id="negative",
                question="unknown",
                candidates=(candidate(),),
                configuration=RetrievalConfiguration.milestone_one(),
                provider=provider,
            )

    row = asyncio.run(run())
    assert row["outcome"] == "INVALID_OUTPUT"
    assert "PRIVATE" not in json.dumps(row)


def test_rejects_invalid_diagnostic_threshold():
    from evals.runners.ollama_refusal import evaluate_case

    with pytest.raises(ValueError, match="threshold"):
        asyncio.run(
            evaluate_case(
                case_id="negative",
                question="unknown",
                candidates=(),
                configuration=replace(
                    RetrievalConfiguration.milestone_one(), min_similarity=float("nan")
                ),
                provider=Provider(None),
            )
        )
