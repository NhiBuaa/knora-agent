from knora.providers.generation import GenerationEvidence, GenerationResult


class DeterministicGenerationProvider:
    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[GenerationEvidence, ...],
    ) -> GenerationResult:
        del question
        first = evidence[0]
        return GenerationResult(
            decision="ANSWER",
            answer=f"{first.content} [[{first.evidence_id}]]",
            cited_evidence_ids=(first.evidence_id,),
            refusal_reason=None,
            provider="deterministic-local",
            model="deterministic-cited-answer-v1",
            prompt_version="deterministic-m1-v1",
            finish_reason="stop",
            usage={},
        )
