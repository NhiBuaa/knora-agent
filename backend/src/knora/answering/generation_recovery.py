"""Recover Cloudflare output on one immutable snapshot under the request's deadline."""

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace

from knora.answering.answer_support import (
    AnswerSupportFailure,
    AnswerSupportVerifier,
    digest,
    proof_observation,
    validate_support,
)
from knora.answering.generation_validation import ValidatedGeneration, validate_generation_structure
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence, GenerationProvider, GenerationResult
from knora.providers.openai_compatible.answer_blocks import compose_grounded_answer


@dataclass
class GenerationRecovery:
    generation: GenerationResult | None = None
    support: dict | None = None
    attempts: list[dict] = field(default_factory=list)
    stop_reason: str | None = None

    def observation(self) -> dict:
        return {
            "policy_id": "grounded-recovery-90s-v1",
            "attempts": self.attempts,
            "stop_reason": self.stop_reason,
        }


async def generate_with_recovery(
    *,
    provider: GenerationProvider,
    verifier: AnswerSupportVerifier | None,
    question: str,
    evidence: tuple[GenerationEvidence, ...],
    groups: tuple[tuple[str, str], ...],
    binding: dict,
    revalidate: Callable[[], None],
    is_v3: bool,
    state: GenerationRecovery,
) -> tuple[GenerationResult, ValidatedGeneration | None]:
    # The caller's single asyncio timeout includes retrieval, all calls and trace persistence.
    loop = asyncio.get_running_loop()
    repair = getattr(provider, "repair_grounded_generation", None) if is_v3 else None
    feedback = None
    verify_feedback = None
    rejected_answers = set()
    failures = set()
    pruned = None
    sufficiency_checked = False
    assess_sufficiency = getattr(verifier, "assess_sufficiency", None)
    phase = "generation"
    while True:
        revalidate()
        attempt = {"phase": phase, "status": "started"}
        state.attempts.append(attempt)
        started = loop.time()
        try:
            if phase == "source_sufficiency":
                sufficiency_checked = True
                insufficient, metadata = await assess_sufficiency(
                    question=question,
                    groups=groups,
                    evidence=evidence,
                    snapshot_digest=digest(binding),
                    revalidate=revalidate,
                )
                attempt["provider"] = metadata
                revalidate()
                if insufficient:
                    generation = replace(
                        state.generation,
                        decision="REFUSAL",
                        answer=None,
                        cited_evidence_ids=(),
                        answer_projection=None,
                        refusal_reason="INSUFFICIENT_EVIDENCE",
                    )
                    state.generation = generation
                    state.support.update(
                        status="insufficient",
                        scope="provided_evidence",
                        coverage="unverified",
                        sufficiency=metadata,
                    )
                    attempt.update(
                        status="insufficient", operation="verified_insufficiency_refusal"
                    )
                    state.stop_reason = "insufficient_evidence"
                    return generation, validate_generation_structure(
                        generation, available_evidence_ids=tuple(e.evidence_id for e in evidence)
                    )
                attempt["status"] = "answerable_or_unknown"
                feedback["source_sufficiency"] = metadata.get("result")
                phase = "repair"
                continue
            if phase != "verification":
                if phase in {"prune", "source_repair"}:
                    generation = pruned
                    attempt["operation"] = (
                        "compose_inventory_candidate"
                        if phase == "source_repair"
                        else "remove_rejected_statements"
                    )
                else:
                    state.generation = None
                    generation = (
                        await provider.generate(question=question, evidence=evidence)
                        if phase == "generation"
                        else await repair(question=question, evidence=evidence, feedback=feedback)
                    )
                state.generation = generation
                if phase not in {"prune", "source_repair"}:
                    attempt["provider"] = {
                        k: v
                        for k, v in asdict(generation).items()
                        if k
                        in {
                            "provider",
                            "model",
                            "prompt_version",
                            "finish_reason",
                            "provider_request_id",
                            "usage",
                            "cost",
                        }
                    }
                revalidate()
                if phase == "repair" and generation.provider != "cloudflare-workers-ai":
                    state.stop_reason = "repair_provider_mismatch"
                    raise KnoraError("GENERATION_OUTPUT_INVALID")
                if not is_v3 or generation.provider != "cloudflare-workers-ai":
                    attempt["status"] = "completed"
                    return generation, None
                validated = validate_generation_structure(
                    generation, available_evidence_ids=tuple(e.evidence_id for e in evidence)
                )
                if generation.decision == "REFUSAL":
                    if feedback is not None:
                        state.stop_reason = "repair_refusal"
                        raise KnoraError("GENERATION_OUTPUT_INVALID")
                    attempt["status"] = "completed"
                    return generation, validated
                if verifier is None or generation.answer_projection is None:
                    state.stop_reason = "missing_verification_contract"
                    raise KnoraError("GENERATION_OUTPUT_INVALID")
                candidate_digest = digest(generation.answer)
                attempt["answer_digest"] = candidate_digest
                if candidate_digest in rejected_answers:
                    state.stop_reason = "repeated_candidate"
                    raise KnoraError("GENERATION_OUTPUT_INVALID")
                state.support = {
                    "policy_id": "answer-support-verification-v3-r4-v1",
                    "status": "invalid",
                    "snapshot_binding": binding,
                }
                attempt["status"] = "completed"
                phase = "verification"
                continue

            generation = state.generation
            kwargs = {
                "question": question,
                "groups": groups,
                "answer": generation.answer,
                "answer_projection": generation.answer_projection,
                "evidence": evidence,
                "snapshot_digest": digest(binding),
                "revalidate": revalidate,
            }
            if verify_feedback is not None:
                kwargs["feedback"] = verify_feedback
            proof, metadata = await verifier.verify(**kwargs)
            attempt["provider"] = metadata
            revalidate()
            proof = validate_support(
                json.loads(proof.verdict_json),
                answer=generation.answer,
                projection=generation.answer_projection,
                evidence=evidence,
                snapshot_digest=digest(binding),
                group_ids=tuple(key for key, _ in groups),
            )
            state.support = {
                **proof_observation(proof, generation.answer_projection, groups, metadata),
                "snapshot_binding": binding,
            }
            attempt["status"] = "supported"
            state.stop_reason = "supported"
            return generation, validated
        except asyncio.CancelledError as error:
            attempt["status"] = "cancelled"
            if observation := getattr(error, "observation", None):
                attempt["observation"] = observation
                if state.support is not None:
                    state.support.update(observation)
            state.stop_reason = "cancelled_or_deadline"
            raise
        except KnoraError as error:
            observation = getattr(error, "observation", {})
            attempt.update(status="failed", error_code=error.code, observation=observation)
            if phase == "verification" and state.support is not None:
                state.support.update(observation)
                state.support["status"] = (
                    "unavailable" if error.code == "PROVIDER_REQUEST_FAILED" else "invalid"
                )
            if error.code != "GENERATION_OUTPUT_INVALID" or state.stop_reason is not None:
                state.stop_reason = state.stop_reason or error.code
                raise
            if phase == "source_sufficiency":
                state.stop_reason = "invalid_source_sufficiency"
                raise
            revalidate()
            cloudflare = (
                state.generation is not None
                and state.generation.provider == "cloudflare-workers-ai"
            ) or observation.get("provider", {}).get("provider") == "cloudflare-workers-ai"
            if not is_v3 or not cloudflare or repair is None:
                state.stop_reason = "recovery_unavailable"
                raise
            signature = digest(
                {
                    "phase": phase,
                    "answer": getattr(state.generation, "answer", None),
                    "failure": {k: v for k, v in observation.items() if k != "provider"},
                }
            )
            if signature in failures:
                state.stop_reason = "repeated_failure"
                raise
            failures.add(signature)
            feedback = {k: v for k, v in observation.items() if k != "provider"}
            if isinstance(feedback.get("verdict"), dict):
                verdict = feedback["verdict"]
                failed_id = feedback.get("failed_id")
                feedback["failed_source_quotes"] = [
                    {"alias": ref["alias"], "quote": ref["exact_quote"]}
                    for statement in verdict.get("statements", [])
                    if statement.get("id") == failed_id
                    for ref in statement.get("source_refs", [])
                ]
                feedback["verdict"] = {
                    "statements": [
                        {"id": s.get("id"), "verdict": s.get("verdict")}
                        for s in verdict.get("statements", [])
                    ],
                    "groups": verdict.get("groups", []),
                }
            feedback.setdefault("failure", "invalid_answer_structure_or_source_support")
            if (
                phase == "verification"
                and isinstance(error, AnswerSupportFailure)
                and (
                    observation.get("failure")
                    in {
                        "invalid_verifier_completion",
                        "invalid_verifier_envelope",
                        "invalid_verifier_proof",
                    }
                )
            ):
                verify_feedback = feedback
                continue
            if state.generation is not None:
                rejected_answers.add(digest(state.generation.answer))
                feedback["previous_answer"] = state.generation.answer
                if observation.get("failure") == "unsupported_answer":
                    if (
                        observation.get("repair_facts")
                        and not observation.get("fact_mismatch")
                        and not any(a["phase"] == "source_repair" for a in state.attempts)
                    ):
                        answer, aliases, projection = compose_grounded_answer(
                            {
                                "decision": "ANSWER",
                                "before": [],
                                "items": observation["repair_facts"],
                                "after": [],
                                "refusal_reason": None,
                            },
                            evidence,
                        )
                        pruned = replace(
                            state.generation,
                            answer=answer,
                            cited_evidence_ids=aliases,
                            answer_projection=projection,
                        )
                        verify_feedback = None
                        phase = "source_repair"
                        continue
                    rejected_ids = {
                        s["id"]
                        for s in observation.get("verdict", {}).get("statements", [])
                        if s.get("verdict") in {"UNKNOWN", "CONTRADICTED"}
                    } | {observation.get("failed_id")}
                    statements = state.generation.answer_projection.statements
                    retained = [s for s in statements if s.id not in rejected_ids]
                    if 0 < len(retained) < len(statements):
                        # Deletion supplies no proof: recheck ALL groups on the new digest.
                        answer, aliases, projection = compose_grounded_answer(
                            {
                                "decision": "ANSWER",
                                "before": [
                                    {"text": s.text, "support": list(s.aliases)} for s in retained
                                ],
                                "items": [],
                                "after": [],
                                "refusal_reason": None,
                            },
                            evidence,
                        )
                        pruned = replace(
                            state.generation,
                            answer=answer,
                            cited_evidence_ids=aliases,
                            answer_projection=projection,
                        )
                        verify_feedback = None
                        phase = "prune"
                        continue
            verify_feedback = None
            phase = (
                "source_sufficiency"
                if phase == "verification"
                and observation.get("failure") == "unsupported_answer"
                and not (
                    observation.get("source_facts")
                    and observation.get("verdict", {}).get("statements")
                    and not observation.get("fact_mismatch")
                    # The completed inventory gives repair facts, never final-answer proof.
                    and not any(a["phase"] == "repair" for a in state.attempts)
                )
                and assess_sufficiency is not None
                and not sufficiency_checked
                else "repair"
            )
        finally:
            attempt["latency_ms"] = (loop.time() - started) * 1000
