import asyncio
from collections.abc import Callable
from math import isfinite
from time import get_clock_info, perf_counter

from knora.answering.evidence import EvidenceSelection, select_evidence
from knora.answering.generation_validation import MARKER_PATTERN, validate_generation
from knora.answering.interface import CitationProjection, QuestionCommand, QuestionResult
from knora.answering.retrieval_configuration import RetrievalConfigurationResolver
from knora.answering.stores import (
    AnsweringStore,
    QuestionTraceRecord,
    RetrievalConfiguration,
    RetrievalResult,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration, EmbeddingProvider
from knora.providers.generation import GenerationEvidence, GenerationProvider, GenerationResult


class AnswerQuestion:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        generation_provider: GenerationProvider,
        store: AnsweringStore,
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration | None = None,
        retrieval_configuration_resolver: RetrievalConfigurationResolver | None = None,
        clock: Callable[[], float] | None = None,
        clock_resolution_ms: float | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._generation_provider = generation_provider
        self._store = store
        self._embedding_configuration = embedding_configuration
        self._retrieval_configuration = (
            retrieval_configuration or RetrievalConfiguration.milestone_one()
        )
        self._retrieval_configuration_resolver = retrieval_configuration_resolver
        self._clock = clock or perf_counter
        self._clock_resolution_ms = (
            get_clock_info("perf_counter").resolution * 1000
            if clock_resolution_ms is None
            else clock_resolution_ms
        )
        if not isinstance(self._clock_resolution_ms, (int, float)) or not isfinite(
            float(self._clock_resolution_ms)
        ) or self._clock_resolution_ms <= 0:
            raise ValueError("clock resolution must be a finite positive number")

    async def execute(
        self,
        command: QuestionCommand,
        principal: WorkspacePrincipal,
    ) -> QuestionResult:
        started = self._clock()
        if principal.workspace_id != command.workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        retrieval_configuration = self._retrieval_configuration
        if self._retrieval_configuration_resolver is not None:
            retrieval_configuration = self._retrieval_configuration_resolver.resolve(
                workspace_id=command.workspace_id
            )

        query_batch = await asyncio.to_thread(
            getattr(self._embedding_provider, "embed_queries", self._embedding_provider.embed),
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

        embedding_ended = self._clock()
        retrieval_started = embedding_ended
        retrieval = self._store.retrieve_candidates(
            workspace_id=command.workspace_id,
            query_text=command.question,
            query_vector=query_batch.vectors[0],
            embedding_configuration=self._embedding_configuration,
            retrieval_configuration=retrieval_configuration,
        )
        if isinstance(retrieval, RetrievalResult):
            candidates = retrieval.candidates
            branch_observations = tuple(
                item.as_mapping() for item in retrieval.branch_observations
            )
            retrieval_embedding_set_ids = retrieval.embedding_set_ids
            retrieval_chunk_set_ids = retrieval.chunk_set_ids
        else:
            candidates = tuple(retrieval)
            branch_observations = ()
            retrieval_embedding_set_ids = ()
            retrieval_chunk_set_ids = ()
        retrieval_ended = self._clock()
        selection = select_evidence(candidates, retrieval_configuration)
        selection_ended = self._clock()
        retrieval_latency_ms = (selection_ended - retrieval_started) * 1000
        phase_timings = self._phase_timings(
            started=started,
            embedding_ended=embedding_ended,
            retrieval_ended=retrieval_ended,
            selection_ended=selection_ended,
            generation_ended=selection_ended,
        )
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
                    retrieval_latency_ms=retrieval_latency_ms,
                    started=started,
                    ended_at=selection_ended,
                    retrieval_configuration=retrieval_configuration,
                    branch_observations=branch_observations,
                    retrieval_embedding_set_ids=retrieval_embedding_set_ids,
                    retrieval_chunk_set_ids=retrieval_chunk_set_ids,
                    phase_timings=phase_timings,
                )
            )
            return QuestionResult(
                workspace_id=command.workspace_id,
                decision="REFUSAL",
                answer=None,
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
        generation_ended = self._clock()
        phase_timings = self._phase_timings(
            started=started,
            embedding_ended=embedding_ended,
            retrieval_ended=retrieval_ended,
            selection_ended=selection_ended,
            generation_ended=generation_ended,
        )
        try:
            validated = validate_generation(
                generation,
                available_evidence_ids=tuple(alias_to_candidate),
            )
        except KnoraError:
            trace_ended = self._clock()
            self._store.persist_trace(
                self._trace(
                    command=command,
                    selection=selection,
                    decision=generation.decision,
                    answer=generation.answer,
                    refusal_reason=generation.refusal_reason,
                    generation_status="completed",
                    embedding=query_batch,
                    retrieval_latency_ms=retrieval_latency_ms,
                    alias_mapping={
                        alias: candidate.chunk_id
                        for alias, candidate in alias_to_candidate.items()
                    },
                    parsed_markers=(
                        tuple(MARKER_PATTERN.findall(generation.answer))
                        if isinstance(generation.answer, str)
                        else ()
                    ),
                    validation_outcome="invalid",
                    generation=generation,
                    started=started,
                    ended_at=trace_ended,
                    retrieval_configuration=retrieval_configuration,
                    branch_observations=branch_observations,
                    retrieval_embedding_set_ids=retrieval_embedding_set_ids,
                    retrieval_chunk_set_ids=retrieval_chunk_set_ids,
                    phase_timings=phase_timings,
                )
            )
            raise

        if validated.result.decision == "REFUSAL":
            decision = "REFUSAL"
            answer = None
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

        trace_ended = self._clock()
        trace_id = self._store.persist_trace(
            self._trace(
                command=command,
                selection=selection,
                decision=decision,
                answer=answer if decision == "ANSWER" else None,
                refusal_reason=refusal_reason,
                generation_status="completed",
                embedding=query_batch,
                retrieval_latency_ms=retrieval_latency_ms,
                alias_mapping={
                    alias: candidate.chunk_id for alias, candidate in alias_to_candidate.items()
                },
                parsed_markers=validated.parsed_markers,
                validation_outcome="valid",
                generation=generation,
                started=started,
                ended_at=trace_ended,
                retrieval_configuration=retrieval_configuration,
                branch_observations=branch_observations,
                retrieval_embedding_set_ids=retrieval_embedding_set_ids,
                retrieval_chunk_set_ids=retrieval_chunk_set_ids,
                phase_timings=phase_timings,
            )
        )
        return QuestionResult(
            workspace_id=command.workspace_id,
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
            page_start=candidate.page_start,
            page_end=candidate.page_end,
            start_offset=candidate.start_offset,
            end_offset=candidate.end_offset,
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
        retrieval_latency_ms: float,
        started: float,
        alias_mapping: dict[str, str] | None = None,
        parsed_markers: tuple[str, ...] = (),
        validation_outcome: str = "not_applicable",
        generation: GenerationResult | None = None,
        retrieval_configuration: RetrievalConfiguration | None = None,
        branch_observations: tuple[dict[str, object], ...] = (),
        retrieval_embedding_set_ids: tuple[str, ...] = (),
        retrieval_chunk_set_ids: tuple[str, ...] = (),
        phase_timings: dict[str, object] | None = None,
        ended_at: float | None = None,
    ) -> QuestionTraceRecord:
        retrieved = tuple(item.candidate for item in selection.decisions)
        provider_metadata: dict[str, object] = {
            "retrieval": {"latency_ms": retrieval_latency_ms},
            "embedding": {
                "provider": embedding.provider,
                "model": embedding.model,
                "provider_request_id": embedding.provider_request_id,
                "usage": embedding.usage,
                "cost": embedding.cost,
            },
            "timing": phase_timings or {},
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
        candidate_decisions = []
        for index, item in enumerate(selection.decisions, start=1):
            if item.outcome == "TOKEN_BUDGET_EXCEEDED":
                final_decision = "BUDGET_EXCEEDED"
                decision_reason = "TOKEN_BUDGET"
            elif item.outcome == "CHUNK_COUNT_LIMIT":
                final_decision = "BUDGET_EXCEEDED"
                decision_reason = "CHUNK_COUNT_LIMIT"
            else:
                final_decision = item.outcome
                decision_reason = None
            candidate_decisions.append(
                {
                    "chunk_id": item.candidate.chunk_id,
                    "final_rank": index,
                    "fusion_score": item.candidate.fusion_score,
                    "final_decision": final_decision,
                    "decision_reason": decision_reason,
                    "vector_contribution": item.candidate.vector_contribution,
                    "fts_contribution": item.candidate.fts_contribution,
                }
            )
        return QuestionTraceRecord(
            workspace_id=command.workspace_id,
            question=command.question,
            retrieval_configuration_id=retrieval_configuration.id,
            fusion_policy_version=(
                retrieval_configuration.fusion_policy_id
                or retrieval_configuration.fusion_policy_version
            ),
            embedding_configuration_id=self._embedding_configuration.id,
            candidate_decisions=tuple(candidate_decisions),
            retrieved_chunk_ids=tuple(candidate.chunk_id for candidate in retrieved),
            embedding_set_ids=tuple(
                dict.fromkeys(
                    (*retrieval_embedding_set_ids, *(c.embedding_set_id for c in retrieved))
                )
            ),
            chunk_set_ids=tuple(
                dict.fromkeys(
                    (*retrieval_chunk_set_ids, *(c.chunk_set_id for c in retrieved))
                )
            ),
            decision=decision,
            answer=answer,
            refusal_reason=refusal_reason,
            generation_status=generation_status,
            alias_mapping=alias_mapping or {},
            parsed_markers=parsed_markers,
            validation_outcome=validation_outcome,
            provider_metadata=provider_metadata,
            latency_ms=((ended_at if ended_at is not None else self._clock()) - started) * 1000,
            branch_observations=branch_observations,
        )

    def _phase_timings(
        self,
        *,
        started: float,
        embedding_ended: float,
        retrieval_ended: float,
        selection_ended: float,
        generation_ended: float,
    ) -> dict[str, object]:
        def phase(start_tick: float, end_tick: float) -> dict[str, float]:
            return {
                "start_tick": start_tick,
                "end_tick": end_tick,
                "duration_ms": (end_tick - start_tick) * 1000,
            }

        return {
            "clock_resolution_ms": self._clock_resolution_ms,
            "phases": {
                "query_embedding": phase(started, embedding_ended),
                "candidate_retrieval": phase(embedding_ended, retrieval_ended),
                "evidence_selection": phase(retrieval_ended, selection_ended),
                "generation": phase(selection_ended, generation_ended),
            },
        }
