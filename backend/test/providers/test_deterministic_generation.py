import pytest

from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.generation import GenerationEvidence


@pytest.mark.asyncio
async def test_deterministic_generation_returns_valid_request_scoped_alias() -> None:
    result = await DeterministicGenerationProvider().generate(
        question="What is the refund policy?",
        evidence=(GenerationEvidence(evidence_id="E1", content="Refunds last thirty days."),),
    )

    assert result.decision == "ANSWER"
    assert result.answer == "Refunds last thirty days. [[E1]]"
    assert result.cited_evidence_ids == ("E1",)
    assert result.provider == "deterministic-local"
