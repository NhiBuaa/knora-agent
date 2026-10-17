from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from test_pdf_runs import WORKSPACE, binding_for, frozen_dataset

from knora.evaluation.pdf_runtime import pdf_http_profile


def response_and_trace():
    frozen = frozen_dataset()
    binding = binding_for(frozen)
    payload = {
        "trace_id": "exact-trace",
        "decision": "ANSWER",
        "answer": "Blue [[E1]]",
        "refusal_reason": None,
        "citations": [
            {
                "evidence_id": "E1",
                "source_key": "source",
                "excerpt": "The sky is blue.",
                "start_line": 1,
                "end_line": 1,
            }
        ],
    }
    candidate = SimpleNamespace(
        chunk_id="chunk-1",
        document_version_id="version-1",
        chunk_set_id="set-1",
        workspace_id=WORKSPACE,
        source_key="source",
        content="The sky is blue.",
        start_line=1,
        end_line=1,
        final_rank=1,
        final_decision="SELECTED",
    )
    trace = SimpleNamespace(
        trace_id="exact-trace",
        workspace_id=WORKSPACE,
        retrieval_configuration_id="retrieval-test",
        embedding_configuration_id="embedding-test",
        candidates=(candidate,),
        alias_mapping={"E1": "chunk-1"},
        provider_metadata={"generation": binding["generation"].copy()},
        retrieval_latency_ms=1.2,
        embedding_set_ids=("embedding-set-1",),
        chunk_set_ids=("set-1",),
        decision="ANSWER",
        answer="Blue [[E1]]",
        refusal_reason=None,
        parsed_markers=("E1",),
    )
    return frozen, binding, payload, trace


@pytest.mark.asyncio
async def test_http_pdf_capture_correlates_exact_trace_and_preserves_actual_generation_evidence():
    frozen, binding, payload, trace = response_and_trace()
    requests = []
    reads = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    def read_trace(**kwargs):
        reads.append(kwargs)
        return trace

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        profile = pdf_http_profile(
            profile_id="offline-http",
            kind="offline",
            endpoint="http://owned.test/v1/questions",
            api_key="key",
            trace_reader=SimpleNamespace(read_trace=read_trace),
            client=client,
            prepare=lambda _: deepcopy(binding),
        )
        observed = await profile.execute(frozen.gold.cases[0], binding)
    assert observed["status"] == "OBSERVED"
    assert reads == [{"trace_id": "exact-trace", "workspace_id": WORKSPACE}]
    assert (
        requests[0].content
        == b'{"workspace_id":"pdf-workspace","question":"What color is the sky?"}'
    )
    assert observed["candidate_chunk_ids"] == ["chunk-1"]
    assert observed["generation_chunk_ids"] == ["chunk-1"]
    assert observed["generation_evidence"] == [["E1", "The sky is blue."]]
    assert observed["public_citations"][0]["evidence_id"] == "E1"
    assert observed["citation_correctness"] is True
    assert observed["provider_metadata"] == trace.provider_metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "drift",
    [
        "workspace_id",
        "trace_id",
        "answer",
        "embedding_configuration_id",
        "generation",
        "embedding_set_ids",
        "foreign_chunk",
        "rank",
    ],
)
async def test_pdf_http_rejects_trace_or_source_drift(drift):
    frozen, binding, payload, trace = response_and_trace()
    if drift == "generation":
        trace.provider_metadata["generation"]["model"] = "other"
    elif drift == "foreign_chunk":
        trace.candidates[0].chunk_id = "foreign"
    elif drift == "rank":
        trace.candidates[0].final_rank = 2
    else:
        setattr(trace, drift, "other")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        profile = pdf_http_profile(
            profile_id="offline-http",
            kind="offline",
            endpoint="http://owned.test/v1/questions",
            api_key="key",
            trace_reader=SimpleNamespace(read_trace=lambda **_: trace),
            client=client,
            prepare=lambda _: binding,
        )
        observed = await profile.execute(frozen.gold.cases[0], binding)
    assert observed["status"] == "FAILED"
    assert observed["failure_code"]
    assert observed["trace_id"] == "exact-trace"


@pytest.mark.asyncio
async def test_pdf_http_does_not_retry_uncertain_timeout():
    frozen, binding, _, _ = response_and_trace()
    attempts = []

    def timeout(request):
        attempts.append(request)
        raise httpx.ReadTimeout("unknown outcome", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        profile = pdf_http_profile(
            profile_id="offline-http",
            kind="offline",
            endpoint="http://owned.test/v1/questions",
            api_key="key",
            trace_reader=object(),
            client=client,
            prepare=lambda _: binding,
        )
        with pytest.raises(httpx.ReadTimeout):
            await profile.execute(frozen.gold.cases[0], binding)
    assert len(attempts) == 1
