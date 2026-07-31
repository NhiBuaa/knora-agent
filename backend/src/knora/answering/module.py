import asyncio
from time import perf_counter

from knora.answering.evidence import EvidenceSelection, select_evidence
from knora.answering.generation_validation import MARKER_PATTERN, validate_generation
from knora.answering.interface import CitationProjection, QuestionCommand, QuestionResult
from knora.answering.stores import (
    AnsweringStore,
    QuestionTraceRecord,
    RetrievalConfiguration,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration, EmbeddingProvider
from knora.providers.generation import GenerationEvidence, GenerationProvider, GenerationResult

REFUSAL_MESSAGE = "Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này."


class AnswerQuestion:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        generation_provider: GenerationProvider,
        store: AnsweringStore,
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._generation_provider = generation_provider
        self._store = store
        self._embedding_configuration = embedding_configuration
        self._retrieval_configuration = (
            retrieval_configuration or RetrievalConfiguration.milestone_one()
        )

    async def execute(
        self,
        command: QuestionCommand,
        principal: WorkspacePrincipal,
    ) -> QuestionResult:
        started = perf_counter()
        if principal.workspace_id != command.workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")

        query_batch = await asyncio.to_thread(
            self._embedding_provider.embed,
            [command.question],
            self._embedding_configuration,
        )
        if len(query_batch.vectors) != 1 or any(
            len(vector) != self._embedding_configuration.dimensions
            for vector in query_batch.vectors
        ):
            raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")
        if (
            query_batch.provider != self._embedding_configuration.provider
            or query_batch.model != self._embedding_configuration.model
        ):
            raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")

        candidates = self._store.retrieve_candidates(
            workspace_id=command.workspace_id,
            query_vector=query_batch.vectors[0],
            embedding_configuration=self._embedding_configuration,
            retrieval_configuration=self._retrieval_configuration,
        )
        selection = select_evidence(candidates, self._retrieval_configuration)
        if not selection.selected:
            trace_id = self._store.persist_trace(
                self._trace(
                    command=command,
                    selection=selection,
                    decision="REFUSAL",
                    answer=None,
                    refusal_reason="INSUFFICIENT_EVIDENCE",
                    generation_status="not_called",
                    embedding=query_batch,
                    started=started,
                )
            )
            return QuestionResult(
                decision="REFUSAL",
                answer=REFUSAL_MESSAGE,
                citations=(),
                refusal_reason="INSUFFICIENT_EVIDENCE",
                trace_id=trace_id,
            )

        alias_to_candidate = {
            f"E{index}": item.candidate
            for index, item in enumerate(selection.selected, start=1)
        }
        generation = await self._generation_provider.generate(
            question=command.question,
            evidence=tuple(
                GenerationEvidence(evidence_id=alias, content=candidate.content)
                for alias, candidate in alias_to_candidate.items()
            ),
        )
        try:
            validated = validate_generation(
                generation,
                available_evidence_ids=tuple(alias_to_candidate),
            )
        except KnoraError:
            self._store.persist_trace(
                self._trace(
                    command=command,
                    selection=selection,
                    decision=generation.decision,
                    answer=generation.answer,
                    refusal_reason=generation.refusal_reason,
                    generation_status="completed",
                    embedding=query_batch,
                    alias_mapping={
                        alias: candidate.chunk_id
                        for alias, candidate in alias_to_candidate.items()
                    },
                    parsed_markers=tuple(
                        MARKER_PATTERN.findall(generation.answer or "")
                    ),
                    validation_outcome="invalid",
                    generation=generation,
                    started=started,
                )
            )
            raise

        if validated.result.decision == "REFUSAL":
            decision = "REFUSAL"
            answer = REFUSAL_MESSAGE
            refusal_reason = "INSUFFICIENT_EVIDENCE"
            citations: tuple[CitationProjection, ...] = ()
        else:
            decision = "ANSWER"
            answer = validated.result.answer or ""
            refusal_reason = None
            citations = tuple(
                self._citation(alias, alias_to_candidate[alias])
                for alias in validated.parsed_markers
            )

        trace_id = self._store.persist_trace(
            self._trace(
                command=command,
                selection=selection,
                decision=decision,
                answer=answer if decision == "ANSWER" else None,
                refusal_reason=refusal_reason,
                generation_status="completed",
                embedding=query_batch,
                alias_mapping={
                    alias: candidate.chunk_id for alias, candidate in alias_to_candidate.items()
                },
                parsed_markers=validated.parsed_markers,
                validation_outcome="valid",
                generation=generation,
                started=started,
            )
        )
        return QuestionResult(
            decision=decision,
            answer=answer,
            citations=citations,
            refusal_reason=refusal_reason,
            trace_id=trace_id,
        )

    @staticmethod
    def _citation(evidence_id, candidate) -> CitationProjection:
        return CitationProjection(
            evidence_id=evidence_id,
            document_id=candidate.document_id,
            document_version_id=candidate.document_version_id,
            source_key=candidate.source_key,
            source_name=candidate.source_name,
            heading_path=candidate.heading_path,
            start_line=candidate.start_line,
            end_line=candidate.end_line,
            excerpt=candidate.content[:500],
            content_checksum=candidate.content_checksum,
        )

    def _trace(
        self,
        *,
        command: QuestionCommand,
        selection: EvidenceSelection,
        decision: str,
        answer: str | None,
        refusal_reason: str | None,
        generation_status: str,
        embedding: EmbeddingBatch,
        started: float,
        alias_mapping: dict[str, str] | None = None,
        parsed_markers: tuple[str, ...] = (),
        validation_outcome: str = "not_applicable",
        generation: GenerationResult | None = None,
    ) -> QuestionTraceRecord:
        retrieved = tuple(item.candidate for item in selection.decisions)
        provider_metadata: dict[str, object] = {
            "embedding": {
                "provider": embedding.provider,
                "model": embedding.model,
                "provider_request_id": embedding.provider_request_id,
                "usage": embedding.usage,
                "cost": embedding.cost,
            }
        }
        if generation is not None:
            provider_metadata["generation"] = {
                "provider": generation.provider,
                "model": generation.model,
                "prompt_version": generation.prompt_version,
                "finish_reason": generation.finish_reason,
                "provider_request_id": generation.provider_request_id,
                "usage": generation.usage,
                "cost": generation.cost,
            }
        return QuestionTraceRecord(
            workspace_id=command.workspace_id,
            question=command.question,
            retrieval_configuration_id=self._retrieval_configuration.id,
            embedding_configuration_id=self._embedding_configuration.id,
            candidate_decisions=tuple(
                {
                    "chunk_id": item.candidate.chunk_id,
                    "cosine_distance": item.candidate.cosine_distance,
                    "similarity": item.candidate.similarity,
                    "outcome": item.outcome,
                }
                for item in selection.decisions
            ),
            retrieved_chunk_ids=tuple(candidate.chunk_id for candidate in retrieved),
            embedding_set_ids=tuple(dict.fromkeys(c.embedding_set_id for c in retrieved)),
            chunk_set_ids=tuple(dict.fromkeys(c.chunk_set_id for c in retrieved)),
            decision=decision,
            answer=answer,
            refusal_reason=refusal_reason,
            generation_status=generation_status,
            alias_mapping=alias_mapping or {},
            parsed_markers=parsed_markers,
            validation_outcome=validation_outcome,
            provider_metadata=provider_metadata,
            latency_ms=(perf_counter() - started) * 1000,
        )
