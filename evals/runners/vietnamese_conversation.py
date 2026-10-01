"""Explicit local Conversation regressions; never activates or seals a release policy."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from evals.datasets.vietnamese_rag_v1 import VietnameseDataset, load_vietnamese_dataset
from sqlalchemy.engine import make_url


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def code_provenance(root):
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("evaluation requires committed inputs and runtime")
    return {"git_commit": git("rev-parse", "HEAD"), "git_tree": git("rev-parse", "HEAD^{tree}")}


def validate_private_output(path):
    parent = path.resolve().parent
    while not parent.exists():
        parent = parent.parent
    result = subprocess.run(
        ["git", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip() == "true":
        raise ValueError("private response artifact must stay outside all Git worktrees")


def validate_evaluation_database(database_url: str) -> None:
    url = make_url(database_url)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"127.0.0.1", "localhost"}
        or bool(url.query)
        or re.fullmatch(r"knora_issue[0-9]+_eval(?:_[a-z0-9]+)*", url.database or "") is None
    ):
        raise ValueError("live regression requires an isolated local evaluation database")


def evaluate_observations(
    dataset: VietnameseDataset, observations: list[dict], semantic_reviews=(), *, runtime_binding
) -> dict:
    """Structural/gold hits cannot stand in for response-bound semantic review."""
    by_id = {}
    for row in observations:
        case_id = row.get("case_id")
        if case_id in by_id or row.get("embedding_profile_id") != dataset.profile_id:
            raise ValueError("duplicate or profile-mismatched observation")
        by_id[case_id] = row
    if set(by_id) != {case.id for case in dataset.cases}:
        raise ValueError("missing or unexpected case observation")
    for field in (
        "retrieval_configuration_id",
        "context_policy_id",
        "model",
        "prompt_version",
        "generation_model_digest",
        "prompt_sha256",
    ):
        if not runtime_binding.get(field):
            raise ValueError("missing runtime provenance")
    turns, traces = set(), set()
    for row in observations:
        turn_id, trace_id = row.get("turn_id"), row.get("trace_id")
        if not turn_id or turn_id in turns:
            raise ValueError("invalid Turn provenance")
        turns.add(turn_id)
        if row.get("status") in {"failed", "outcome_unknown"}:
            continue
        if not trace_id or trace_id in traces or row.get("result_trace_id") != trace_id:
            raise ValueError("invalid trace provenance")
        traces.add(trace_id)
        fields = ("retrieval_configuration_id", "context_policy_id")
        if any(row.get(field) != runtime_binding[field] for field in fields):
            raise ValueError("mismatched runtime provenance")
        if row.get("generation_status") == "completed":
            if row.get("provider") != "ollama" or any(
                row.get(field) != runtime_binding[field]
                for field in ("model", "prompt_version", "generation_model_digest", "prompt_sha256")
            ):
                raise ValueError("mismatched generation provenance")
        elif not (
            row.get("generation_status") == "not_called"
            and row.get("decision") == "REFUSAL"
            and row.get("provider") is None
        ):
            raise ValueError("missing generation provenance")
    reviews = {}
    for review in semantic_reviews:
        case_id = review.get("case_id")
        if (
            case_id in reviews
            or case_id not in by_id
            or by_id[case_id]["decision"] != "ANSWER"
            or review.get("response_sha256") != response_sha256(dataset, by_id[case_id])
            or not isinstance(review.get("passed"), bool)
            or not isinstance(review.get("reason"), str)
            or not review["reason"].strip()
        ):
            raise ValueError("invalid or stale semantic review")
        reviews[case_id] = review
    rows = []
    for case in dataset.cases:
        observed = by_id[case.id]
        if observed.get("question_sha256") != text_sha256(case.question):
            raise ValueError("question-mismatched observation")
        citations = observed.get("citations", [])
        gold_hit = any(
            citation.get("source_key") == case.source_key
            and citation.get("page_start") == case.page_start
            and citation.get("content_checksum") in case.acceptable_chunk_checksums
            for citation in citations
        )
        correct = (
            observed.get("decision") == case.expected_behavior
            and observed.get("status")
            == ("answered" if case.expected_behavior == "ANSWER" else "refused")
            and observed.get("structural_valid") is True
        )
        review = reviews.get(case.id)
        if case.expected_behavior == "REFUSAL":
            passed = correct and not citations
        else:
            passed = correct and gold_hit and review is not None and review["passed"]
        rows.append(
            {
                **observed,
                "expected_behavior": case.expected_behavior,
                "decision_correct": correct,
                "citation_gold_hit": gold_hit,
                "semantic_review": review,
                "passed": passed,
            }
        )
    failed = any(
        not row["decision_correct"]
        or (row["expected_behavior"] == "REFUSAL" and bool(row.get("citations")))
        or (row["expected_behavior"] == "ANSWER" and not row["citation_gold_hit"])
        or (row["semantic_review"] is not None and not row["semantic_review"]["passed"])
        for row in rows
    )
    missing_review = any(
        row["expected_behavior"] == "ANSWER" and row["semantic_review"] is None for row in rows
    )
    status = (
        "REGRESSION_FAILED"
        if failed
        else "AWAITING_SEMANTIC_REVIEW"
        if missing_review
        else "REGRESSION_PASSED"
    )
    negatives = [row for row in rows if row["expected_behavior"] == "REFUSAL"]
    return {
        "schema_version": 1,
        "status": status,
        "scope": "development_exposed_one_pdf_regressions",
        "held_out_after_tuning": False,
        "release_gate": "NOT_EVALUATED",
        "sealed_artifact": None,
        "dataset_version": dataset.version,
        "dataset_sha256": dataset.dataset_sha256,
        "corpus_sha256": dataset.corpus_sha256,
        "chunk_set_ids": dataset.chunk_set_ids,
        "embedding_profile_id": dataset.profile_id,
        "embedding_model_digest": dataset.model_digest,
        "runtime_binding": runtime_binding,
        "case_count": len(rows),
        "decision_correct_count": sum(row["decision_correct"] for row in rows),
        "citation_gold_hit_count": sum(row["citation_gold_hit"] for row in rows),
        "semantic_passed_count": sum(
            row["semantic_review"] is not None and row["semantic_review"]["passed"] for row in rows
        ),
        "model_refusal_count": sum(
            row["passed"]
            and row.get("generation_status") == "completed"
            and row.get("provider") == "ollama"
            for row in negatives
        ),
        "pre_generation_refusal_count": sum(
            row["passed"] and row.get("generation_status") == "not_called" for row in negatives
        ),
        "cases": rows,
    }


def response_sha256(dataset, row):
    """Bind review to text, decision and the entire ordered public citation projection."""
    response = {
        key: row.get(key)
        for key in (
            "case_id",
            "question_sha256",
            "answer_sha256",
            "decision",
            "refusal_reason",
            "citations",
        )
    }
    response["dataset_sha256"] = dataset.dataset_sha256
    return text_sha256(json.dumps(response, sort_keys=True, separators=(",", ":")))


async def collect_conversation_cases(
    dataset, *, store, runner, workspace_id, read_observation, record
):
    run_id = str(uuid4())
    conversation = store.create(workspace_id, f"regression-{run_id}")
    observed = []
    for case in dataset.cases:
        admission = store.submit_turn(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            idempotency_key=f"{run_id}:{case.id}",
            question=case.question,
            auto_title=f"Regression {run_id}",
            request_fingerprint=text_sha256(" ".join(case.question.split())),
        )
        await runner.run_once(worker_id=f"regression-{run_id}", workspace_id=workspace_id)
        turn = store.get_turn(workspace_id, conversation.id, admission.turn.id)
        if (
            turn is None
            or turn.question != case.question
            or turn.status not in {"answered", "refused", "failed", "outcome_unknown"}
        ):
            raise ValueError("evaluation Turn identity mismatch")
        row = read_observation(case, turn)
        observed.append(row)
        record(row)
    return {"conversation_id": conversation.id, "observations": observed}


def configuration_from_calibration(dataset, calibration):
    from knora.answering.stores import RetrievalConfiguration

    for field, expected in (
        ("status", "RETRIEVAL_PASSED"),
        ("profile_id", dataset.profile_id),
        ("model_digest", dataset.model_digest),
        ("dataset_sha256", dataset.dataset_sha256),
        ("corpus_sha256", dataset.corpus_sha256),
        ("chunk_set_ids", list(dataset.chunk_set_ids)),
        ("policy_id", "qwen-vietnamese-evidence-v1"),
        ("regression_case_passed", True),
    ):
        if calibration.get(field) != expected:
            raise ValueError("candidate calibration provenance mismatch")
    payload = json.dumps(calibration, sort_keys=True, separators=(",", ":"))
    return RetrievalConfiguration.qwen_containment_candidate_v2(
        min_similarity=calibration.get("candidate_threshold"),
        provenance_sha256=text_sha256(payload),
    )


def validate_calibration_target(calibration_dataset, target_dataset):
    for field in ("profile_id", "model_digest", "corpus_sha256", "chunk_set_ids"):
        if getattr(calibration_dataset, field) != getattr(target_dataset, field):
            raise ValueError("calibration target corpus or profile mismatch")


async def run_live(args):
    # Imports belong inside the CLI's sanitized failure boundary. No application-global
    # Settings or default database is used by this explicit evaluation composition.
    import httpx
    from evals.runners.vietnamese_retrieval import load_active_bindings, validate_active_corpus
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from knora.adapters.postgres.answering_store import PostgresAnsweringStore
    from knora.adapters.postgres.conversation_store import PostgresConversationStore
    from knora.adapters.postgres.tables import (
        ChunkTable,
        ConversationTurnTable,
        QuestionTraceTable,
    )
    from knora.answering.module import AnswerQuestion
    from knora.conversations.context import CONTEXT_POLICY_ID
    from knora.conversations.runner import ConversationRunner
    from knora.providers.ollama.embedding import (
        OllamaEmbeddingProvider,
        resolve_ollama_embedding_configuration,
    )
    from knora.providers.ollama.generation import (
        OLLAMA_PROMPT_VERSION,
        OLLAMA_SYSTEM_PROMPT,
        OllamaGenerationProvider,
    )

    database_url = os.environ["KNORA_DATABASE_URL"]
    validate_evaluation_database(database_url)
    validate_private_output(args.private_output)
    provenance = code_provenance(Path(__file__).resolve().parents[2])
    dataset = load_vietnamese_dataset(args.dataset, args.manifest)
    calibration_dataset = load_vietnamese_dataset(
        args.calibration_dataset, args.calibration_manifest
    )
    validate_calibration_target(calibration_dataset, dataset)
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    configuration = configuration_from_calibration(calibration_dataset, calibration)
    if CONTEXT_POLICY_ID != "conversation-context-v2":
        raise ValueError("reference-context prerequisite is missing")
    runtime_binding = dict(
        retrieval_configuration_id=configuration.id,
        context_policy_id=CONTEXT_POLICY_ID,
        model="qwen3:8b",
        prompt_version=OLLAMA_PROMPT_VERSION,
        generation_model_digest=args.generation_digest,
        prompt_sha256=text_sha256(OLLAMA_SYSTEM_PROMPT),
    )
    engine = create_engine(database_url)
    factory = sessionmaker(engine)
    generation = OllamaGenerationProvider(
        base_url=args.ollama_url, model="qwen3:8b", expected_digest=args.generation_digest
    )
    private_rows = []
    try:
        validate_active_corpus(dataset, load_active_bindings(factory, args.workspace_id))
        with factory() as session:
            if session.scalar(
                select(ConversationTurnTable.id)
                .where(
                    ConversationTurnTable.workspace_id == args.workspace_id,
                    ConversationTurnTable.status.in_(("queued", "processing")),
                )
                .limit(1)
            ):
                raise ValueError("evaluation Workspace has pending Turns")
        with httpx.Client(base_url=args.ollama_url, timeout=120, trust_env=False) as client:
            profile = resolve_ollama_embedding_configuration(client, "qwen3-embedding:0.6b")
            if profile.id != dataset.profile_id or not profile.deployment_identity.endswith(
                dataset.model_digest
            ):
                raise ValueError("evaluation embedding deployment mismatch")
            embedding = OllamaEmbeddingProvider(client=client)
            store = PostgresConversationStore(factory)
            answering_store = PostgresAnsweringStore(factory)
            answer = AnswerQuestion(
                embedding_provider=embedding,
                generation_provider=generation,
                store=answering_store,
                embedding_configuration=profile,
                retrieval_configuration=configuration,
            )
            runner = ConversationRunner(
                store=store, answer_question=answer, result_reader=answering_store
            )

            def read_observation(case, turn):
                with factory() as session:
                    trace = session.scalar(
                        select(QuestionTraceTable).where(
                            QuestionTraceTable.workspace_id == args.workspace_id,
                            QuestionTraceTable.conversation_turn_id == turn.id,
                        )
                    )
                    metadata = trace.provider_metadata if trace is not None else {}
                    generation_metadata = metadata.get("generation", {})
                    context_metadata = metadata.get("conversation_context", {})
                    if trace is not None and (
                        trace.retrieval_configuration_id != configuration.id
                        or trace.embedding_configuration_id != profile.id
                        or trace.question != case.question
                        or context_metadata.get("policy_id") != CONTEXT_POLICY_ID
                    ):
                        raise ValueError("evaluation trace provenance mismatch")
                    if generation_metadata and (
                        generation_metadata.get("provider") != "ollama"
                        or generation_metadata.get("model") != "qwen3:8b"
                        or generation_metadata.get("prompt_version") != OLLAMA_PROMPT_VERSION
                    ):
                        raise ValueError("evaluation generation provenance mismatch")
                    result = turn.result
                    citations = [asdict(item) for item in result.citations] if result else []
                    response = (
                        (result.answer or "") if result else (trace.answer or "") if trace else ""
                    )
                    evidence_content = {
                        chunk.id: chunk.content
                        for chunk in session.scalars(
                            select(ChunkTable).where(
                                ChunkTable.id.in_(
                                    list(trace.alias_mapping.values()) if trace else []
                                )
                            )
                        )
                    }
                    private_rows.append(
                        {
                            "case_id": case.id,
                            "question": case.question,
                            "answer": response,
                            "decision": result.decision if result else None,
                            "citations": citations,
                            "selected_evidence": {
                                alias: evidence_content[chunk_id]
                                for alias, chunk_id in (
                                    trace.alias_mapping if trace else {}
                                ).items()
                            },
                        }
                    )
                    row = {
                        "case_id": case.id,
                        "turn_id": turn.id,
                        "status": turn.status,
                        "error_code": turn.error_code,
                        "question_sha256": text_sha256(case.question),
                        "answer_sha256": text_sha256(response),
                        "embedding_profile_id": profile.id,
                        "retrieval_configuration_id": configuration.id,
                        "context_policy_id": CONTEXT_POLICY_ID,
                        "trace_id": trace.id if trace else None,
                        "result_trace_id": result.trace_id if result else None,
                        "decision": result.decision if result else None,
                        "refusal_reason": result.refusal_reason if result else None,
                        "structural_valid": bool(
                            trace
                            and trace.validation_outcome in ("valid", "not_applicable")
                            and result
                        ),
                        "generation_status": trace.generation_status if trace else None,
                        "provider": generation_metadata.get("provider"),
                        "model": generation_metadata.get("model"),
                        "prompt_version": generation_metadata.get("prompt_version"),
                        "generation_model_digest": args.generation_digest,
                        "prompt_sha256": runtime_binding["prompt_sha256"],
                        "latency_ms": trace.latency_ms if trace else None,
                        "citations": [
                            {
                                **{
                                    key: value
                                    for key, value in citation.items()
                                    if key != "excerpt"
                                },
                                "excerpt_sha256": text_sha256(citation["excerpt"]),
                            }
                            for citation in citations
                        ],
                    }
                    row["response_sha256"] = response_sha256(dataset, row)
                    private_rows[-1]["response_sha256"] = row["response_sha256"]
                    return row

            def record(row):
                # Local response artifact is intentionally separate from sanitized Git reports.
                args.private_output.parent.mkdir(parents=True, exist_ok=True)
                args.private_output.write_text(
                    json.dumps(private_rows, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(
                    json.dumps(
                        {
                            "case_id": row["case_id"],
                            "status": row["status"],
                            "decision": row["decision"],
                        }
                    ),
                    flush=True,
                )

            collected = await collect_conversation_cases(
                dataset,
                store=store,
                runner=runner,
                workspace_id=args.workspace_id,
                read_observation=read_observation,
                record=record,
            )
            report = evaluate_observations(
                dataset, collected["observations"], runtime_binding=runtime_binding
            )
            report.update(
                workspace_id=args.workspace_id,
                conversation_id=collected["conversation_id"],
                retrieval_configuration=asdict(configuration),
                generation_model_digest=args.generation_digest,
                prompt_sha256=text_sha256(OLLAMA_SYSTEM_PROMPT),
                context_policy_id=CONTEXT_POLICY_ID,
                transport_gate="DIRECT_DURABLE_CONVERSATION_NOT_BROWSER_AUTH",
                code_provenance=provenance,
                calibration_dataset_sha256=calibration_dataset.dataset_sha256,
                calibration_artifact_sha256=hashlib.sha256(
                    args.calibration.read_bytes()
                ).hexdigest(),
                rubric_version="vietnamese-rag-v2-development",
                rubric_sha256=hashlib.sha256(args.rubric.read_bytes()).hexdigest(),
            )
            return report
    finally:
        await generation.aclose()
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "dataset",
        "manifest",
        "calibration",
        "calibration-dataset",
        "calibration-manifest",
        "output",
        "private-output",
        "rubric",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--generation-digest", required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11435")
    args = parser.parse_args()
    validate_private_output(args.private_output)
    report = asyncio.run(run_live(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"], "case_count": report["case_count"]}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Conversation regression failed; no complete report was produced."
        ) from None
