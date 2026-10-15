"""PDF source-gold adapter to Knora's production HTTP/trace evaluation seam."""

import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path
from time import perf_counter

import httpx
from evals.runners.evaluation import write_report_atomic
from evals.runners.milestone_3 import (
    ObservationFailure,
    validate_public_citations_against_trace,
    validate_public_response,
)
from evals.runners.pdf_source_binding import chunk_record, digest, group_coverage


def publish_json(path: Path, value: object) -> None:
    write_report_atomic(path, value)


class PdfHttpExecutor:
    def __init__(
        self,
        *,
        client,
        headers,
        reader,
        workspace_id,
        run_id,
        embedding_configuration_id,
        poll_interval=1.0,
        max_polls=900,
    ):
        self.client, self.headers, self.reader = client, headers, reader
        self.workspace_id, self.run_id = workspace_id, run_id
        self.embedding_configuration_id = embedding_configuration_id
        self.poll_interval, self.max_polls = poll_interval, max_polls
        self.counters = None

    def is_paused(self):
        return bool(self.counters and load_json(self.counters).get("stop_reason"))

    def assert_not_paused(self):
        if self.is_paused():
            raise ObservationFailure(load_json(self.counters)["stop_reason"])

    async def poll(self, path, terminal, *, id_field, expected_id):
        for _ in range(self.max_polls):
            self.assert_not_paused()
            response = await self.client.get(path, headers=self.headers)
            response.raise_for_status()
            payload = response.json()
            if payload.get(id_field) != expected_id:
                raise ObservationFailure("POLL_ID_MISMATCH")
            if payload["status"] in terminal:
                return payload
            await asyncio.sleep(self.poll_interval)
        raise ObservationFailure("POLL_TIMEOUT")

    async def upload(self, source):
        self.assert_not_paused()
        response = await self.client.post(
            f"/v1/workspaces/{self.workspace_id}/documents",
            headers={**self.headers, "Idempotency-Key": f"{self.run_id}:pdf:{source.id}"},
            data={"workspace_id": self.workspace_id, "source_key": source.id},
            files={"file": (source.path.name, source.path.read_bytes(), "application/pdf")},
        )
        response.raise_for_status()
        submitted = response.json()
        job_id = submitted["ingestion_job_id"]
        return await self.poll(
            f"/v1/workspaces/{self.workspace_id}/ingestion-jobs/{job_id}",
            {"succeeded", "superseded", "failed"},
            id_field="ingestion_job_id",
            expected_id=job_id,
        )

    async def conversation(self, root_case_id):
        response = await self.client.post(
            f"/v1/workspaces/{self.workspace_id}/conversations",
            headers={
                **self.headers,
                "Idempotency-Key": f"{self.run_id}:conversation:{root_case_id}",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("workspace_id") != self.workspace_id:
            raise ObservationFailure("CONVERSATION_WORKSPACE_MISMATCH")
        return payload["id"]

    async def execute(self, case, *, conversation_id=None, parent_turn_id=None, attempt=1):
        row = {
            "run_id": self.run_id,
            "case_id": case.id,
            "attempt_id": f"{self.run_id}:{case.id}:{attempt}",
            "attempt": attempt,
            "workspace_id": self.workspace_id,
            "conversation_id": conversation_id,
            "turn_id": None,
            "trace_id": None,
            "failure_code": None,
        }
        started = perf_counter()
        try:
            if case.parent_case_id and conversation_id is None:
                raise ObservationFailure("FOLLOW_UP_CONTEXT_MISSING")
            if conversation_id:
                path = f"/v1/workspaces/{self.workspace_id}/conversations/{conversation_id}/turns"
                response = await self.client.post(
                    path,
                    headers={**self.headers, "Idempotency-Key": row["attempt_id"]},
                    json={"question": case.question},
                )
                response.raise_for_status()
                turn = response.json()
                row["turn_id"] = turn["id"]
                turn = await self.poll(
                    f"{path}/{turn['id']}",
                    {"answered", "refused", "failed", "interrupted"},
                    id_field="id",
                    expected_id=turn["id"],
                )
                if (
                    turn.get("conversation_id") != conversation_id
                    or turn.get("question") != case.question
                ):
                    raise ObservationFailure("TURN_MISMATCH")
                if turn["status"] in {"failed", "interrupted"}:
                    row["turn_error_code"] = turn.get("error_code")
                    if str(row["turn_error_code"]).startswith("PROVIDER_"):
                        row["provider_error"] = row["turn_error_code"]
                        raise ObservationFailure("PROVIDER_FAILED")
                    raise ObservationFailure("TURN_FAILED")
                payload = turn["result"]
            else:
                response = await self.client.post(
                    "/v1/questions",
                    headers=self.headers,
                    json={"workspace_id": self.workspace_id, "question": case.question},
                )
                response.raise_for_status()
                payload = response.json()
            row["trace_id"] = payload["trace_id"]
            row["response_sha256"] = digest(payload)
            row["public_response"] = payload
            public = validate_public_response(payload)
            trace = self.reader.read_trace(trace_id=row["trace_id"], workspace_id=self.workspace_id)
            if case.parent_case_id and (
                parent_turn_id is None
                or parent_turn_id
                not in trace.provider_metadata.get("conversation_context", {}).get(
                    "selected_turn_ids", []
                )
            ):
                raise ObservationFailure("FOLLOW_UP_CONTEXT_MISSING")
            if (
                payload.get("workspace_id") != self.workspace_id
                or trace.trace_id != row["trace_id"]
                or trace.workspace_id != self.workspace_id
                or trace.retrieval_configuration_id != "retrieval-evidence-containment-v1"
                or trace.embedding_configuration_id != self.embedding_configuration_id
                or (trace.decision, trace.answer, trace.refusal_reason, tuple(trace.parsed_markers))
                != (public.decision, public.answer, public.refusal_reason, public.answer_marker_ids)
            ):
                raise ObservationFailure("OBSERVATION_MISMATCH")
            validate_public_citations_against_trace(
                citations=public.citations,
                alias_mapping=trace.alias_mapping,
                candidates=trace.candidates,
            )
            for citation in payload["citations"]:
                candidate = next(
                    c
                    for c in trace.candidates
                    if c.chunk_id == trace.alias_mapping[citation["evidence_id"]]
                )
                if any(
                    citation.get(key) != getattr(candidate, key)
                    for key in (
                        "document_version_id",
                        "content_checksum",
                        "page_start",
                        "page_end",
                        "start_offset",
                        "end_offset",
                    )
                ):
                    raise ObservationFailure("PDF_CITATION_PROVENANCE_MISMATCH")
            current = {
                c.chunk_id: chunk_record(c)
                for c in self.reader.read_pdf_chunks(workspace_id=self.workspace_id)
            }
            if any(current.get(c.chunk_id) != chunk_record(c) for c in trace.candidates):
                raise ObservationFailure("PDF_DERIVATION_MISMATCH")
            row.update(
                decision=public.decision,
                selected_chunk_ids=[
                    c.chunk_id for c in trace.candidates if c.final_decision == "SELECTED"
                ],
                candidates=[
                    chunk_record(c)
                    | {"final_decision": c.final_decision, "final_rank": c.final_rank}
                    for c in trace.candidates
                ],
                retrieval_latency_ms=trace.retrieval_latency_ms,
                provider_metadata=trace.provider_metadata,
            )
        except ObservationFailure as error:
            row["failure_code"] = str(error)
        except httpx.HTTPStatusError as error:
            row["http_status"] = error.response.status_code
            try:
                code = error.response.json().get("error", {}).get("code")
            except (ValueError, AttributeError):
                code = None
            row["provider_error"] = (
                code if isinstance(code, str) and code.startswith("PROVIDER_") else None
            )
            row["failure_code"] = "PROVIDER_FAILED" if row["provider_error"] else "HTTP_FAILED"
        except (httpx.HTTPError, KeyError, TypeError, ValueError, LookupError, StopIteration):
            row["failure_code"] = "OBSERVATION_FAILED"
        row["end_to_end_latency_ms"] = (perf_counter() - started) * 1000
        return row


def build_report(dataset, observations, bindings, response_reviews, *, source_results=None):
    rows = {row["case_id"]: row for row in observations}
    if len(rows) != len(observations) or set(rows) - {c.id for c in dataset.cases}:
        raise ValueError("observations must contain exactly one selected attempt per known case")
    counts = dict(
        total=len(dataset.cases),
        attempted=len(rows),
        observed=0,
        retrieval_evaluable=0,
        extraction_or_mapping_missing=0,
        not_run=0,
        observation_failed=0,
        provider_failed=0,
    )
    cases = []
    for case in dataset.cases:
        row = rows.get(case.id)
        result = {"case_id": case.id, "status": "not_run", "semantic_review": "pending"}
        if row is None:
            counts["not_run"] += 1
        elif row.get("failure_code"):
            kind = (
                "provider_failed"
                if row["failure_code"] == "PROVIDER_FAILED"
                else "observation_failed"
            )
            counts[kind] += 1
            result.update(
                status=kind,
                failure_code=row["failure_code"],
                provider_error=row.get("provider_error"),
            )
        else:
            counts["observed"] += 1
            result.update(
                status="observed",
                response_sha256=row["response_sha256"],
                decision_matches_expected=row["decision"] == case.expected_behavior,
            )
            if any(
                not any(bindings.get(anchor) for anchor in group) for group in case.evidence_groups
            ):
                counts["extraction_or_mapping_missing"] += 1
                result["status"] = "extraction_or_mapping_missing"
            elif case.evidence_groups:
                counts["retrieval_evaluable"] += 1
                coverage = group_coverage(case.evidence_groups, bindings, row["selected_chunk_ids"])
                result.update(
                    evidence_group_coverage=list(coverage), all_groups_covered=all(coverage)
                )
            review = response_reviews.get(case.id)
            if review:
                if (
                    review.get("reviewer") != "NhiBuaa"
                    or review.get("response_sha256") != row["response_sha256"]
                ):
                    raise ValueError("response review digest/owner mismatch")
                result["semantic_review"] = review
        cases.append(result)
    evaluable = [c["all_groups_covered"] for c in cases if "all_groups_covered" in c]
    return {
        "schema_version": 1,
        "dataset_sha256": dataset.dataset_sha256,
        "corpus_sha256": dataset.corpus_sha256,
        "denominators": counts,
        "cases": cases,
        "ingestion": source_results or {},
        "tools": "not_run",
        "metrics": {
            "all_evidence_groups_covered": sum(evaluable) / len(evaluable) if evaluable else None
        },
        "acceptance": "pending_owner_review_and_B",
        "paid_budget_usd": 0,
        "cost": {"observed_invoice_usd": None, "status": "unavailable"},
    }


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def revalidation_evaluator_sha256():
    """Bind review to the current checker, PDF executor and production preview policy."""
    root = Path(__file__).resolve().parents[2]
    paths = (
        "evals/runners/milestone_3.py",
        "evals/runners/pdf_retrieval_v3.py",
        "backend/src/knora/answering/excerpt.py",
    )
    return digest(
        {
            path: hashlib.sha256((root / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for path in paths
        }
    )


def load_revalidation_selection(output, record_path, *, proposal_sha256, derivation_sha256):
    """Select one owner-reviewed replay of an immutable failed capture, never a new attempt."""
    record = load_json(record_path)
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != 1
        or record.get("status") != "approved"
        or record.get("reviewer") != "NhiBuaa"
        or record.get("decision_url")
        != "https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6186149890"
        or not proposal_sha256
        or record.get("proposal_sha256") != proposal_sha256
        or record.get("evaluator_sha256") != revalidation_evaluator_sha256()
    ):
        raise ValueError("revalidation owner/code/proposal review mismatch")
    identity = record.get("identity")
    keys = {
        "run_id",
        "case_id",
        "attempt_id",
        "attempt",
        "workspace_id",
        "conversation_id",
        "turn_id",
        "trace_id",
        "response_sha256",
        "corpus_sha256",
        "dataset_sha256",
        "derivation_sha256",
    }
    if (
        not isinstance(identity, dict)
        or set(identity) != keys
        or any(not isinstance(identity[k], str) or not identity[k] for k in keys - {"attempt"})
        or type(identity["attempt"]) is not int
        or identity["attempt"] < 1
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", identity["case_id"])
        or not derivation_sha256
        or identity["derivation_sha256"] != derivation_sha256
        or identity["attempt_id"]
        != f"{identity['run_id']}:{identity['case_id']}:{identity['attempt']}"
    ):
        raise ValueError("revalidation identity mismatch")
    output = Path(output)
    path = output / f"case-{identity['case_id']}-attempt-{identity['attempt']}.json"
    if not path.is_file() or path.resolve().parent != output.resolve():
        raise ValueError("revalidation original capture missing or unsafe")
    raw = path.read_bytes()
    original = json.loads(raw.decode("utf-8-sig"))
    observation = record.get("observation")
    if (
        hashlib.sha256(raw).hexdigest() != record.get("original_capture_sha256")
        or not isinstance(original, dict)
        or any(original.get(k) != v for k, v in identity.items())
        or original.get("failure_code") != "CASE_FAILED_NO_RETRY"
        or original.get("observation_failure_code") != "CITATION_STRUCTURAL_ERROR"
        or not isinstance(original.get("public_response"), dict)
        or "end_to_end_latency_ms" not in original
        or digest(original.get("public_response")) != identity["response_sha256"]
        or not isinstance(observation, dict)
        or digest(observation) != record.get("observation_sha256")
    ):
        raise ValueError("revalidation capture/observation digest or identity mismatch")
    mutable = {
        "failure_code",
        "decision",
        "selected_chunk_ids",
        "candidates",
        "provider_metadata",
        "retrieval_latency_ms",
        "revalidation",
    }
    required = {
        "failure_code",
        "decision",
        "selected_chunk_ids",
        "candidates",
        "provider_metadata",
        "retrieval_latency_ms",
    }
    if (
        not required <= observation.keys()
        or observation["failure_code"] is not None
        or observation["decision"] != original["public_response"].get("decision")
        or any(
            key not in mutable and (key not in observation or observation[key] != original[key])
            for key in original
        )
        or set(observation) - set(original) - mutable
        or (
            "retrieval_latency_ms" in original
            and observation["retrieval_latency_ms"] != original["retrieval_latency_ms"]
        )
        or any(
            int(p.stem.rsplit("-", 1)[1]) > identity["attempt"]
            for p in output.glob(f"case-{identity['case_id']}-attempt-*.json")
        )
    ):
        raise ValueError("revalidation changed stable capture data or selected a stale attempt")
    return {identity["case_id"]: observation}


def validate_artifact_identity(row, dataset, run_id, workspace_id, *, derivation_sha256=None):
    expected = {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "dataset_sha256": dataset.dataset_sha256,
        "corpus_sha256": dataset.corpus_sha256,
    }
    if derivation_sha256 is not None:
        expected["derivation_sha256"] = derivation_sha256
    if any(row.get(key) != value for key, value in expected.items()):
        raise ValueError("saved artifact identity mismatch")


def validate_counter_identity(counters, dataset, run_id):
    if counters.get("run_identity") != {
        "run_id": run_id,
        "corpus_sha256": dataset.corpus_sha256,
        "dataset_sha256": dataset.dataset_sha256,
        "baseline": "pypdf-layout-v2/qwen3-06b/gpt-oss20b/containment0.65",
    }:
        raise ValueError("runtime counter identity mismatch")


async def collect_cases(
    dataset,
    executor,
    output: Path,
    *,
    derivation_sha256=None,
    resume_quota=False,
    revalidation_record=None,
    proposal_sha256=None,
):
    """Resume captured cases without re-answering them for tools or framework metrics."""
    selections = (
        load_revalidation_selection(
            output,
            revalidation_record,
            proposal_sha256=proposal_sha256,
            derivation_sha256=derivation_sha256,
        )
        if revalidation_record is not None
        else {}
    )
    for case_id, selected in selections.items():
        if case_id not in {case.id for case in dataset.cases}:
            raise ValueError("revalidation case is not in dataset")
        try:
            validate_artifact_identity(
                selected,
                dataset,
                executor.run_id,
                executor.workspace_id,
                derivation_sha256=derivation_sha256,
            )
        except ValueError as error:
            raise ValueError("revalidation dataset/run identity mismatch") from error
    child_parents = {case.parent_case_id for case in dataset.cases if case.parent_case_id}
    conversations = {}
    rows = []
    by_case = {}
    for case in dataset.cases:
        previous = sorted(
            output.glob(f"case-{case.id}-attempt-*.json"),
            key=lambda p: int(p.stem.rsplit("-", 1)[1]),
        )
        path = previous[-1] if previous else output / f"case-{case.id}-attempt-1.json"
        row = load_json(path) if previous else None
        if case.id in selections:
            row = selections[case.id]
        retry = bool(
            row
            and resume_quota
            and row.get("failure_code") in {"QUOTA_PAUSED", "FREE_PREFLIGHT_EXPIRED"}
        )
        if row and any(
            row.get(key) != expected
            for key, expected in (
                ("run_id", executor.run_id),
                ("workspace_id", executor.workspace_id),
                ("dataset_sha256", dataset.dataset_sha256),
                ("corpus_sha256", dataset.corpus_sha256),
                ("case_id", case.id),
                ("derivation_sha256", derivation_sha256),
            )
        ):
            raise ValueError("resumed observation identity mismatch")
        if row is None or retry:
            executor.assert_not_paused()
            parent = by_case.get(case.parent_case_id)
            missing_parent = case.parent_case_id and (
                not parent or parent.get("failure_code") or not parent.get("turn_id")
            )
            attempt = row["attempt"] + 1 if row else 1
            path = output / f"case-{case.id}-attempt-{attempt}.json"
            conversation_id = conversations.get(case.parent_case_id)
            if retry:
                conversation_id = row.get("conversation_id")
            if case.id in child_parents and conversation_id is None:
                conversation_id = await executor.conversation(case.id)
            if missing_parent:
                row = {
                    "run_id": executor.run_id,
                    "workspace_id": executor.workspace_id,
                    "case_id": case.id,
                    "attempt_id": f"{executor.run_id}:{case.id}:{attempt}",
                    "attempt": attempt,
                    "conversation_id": conversation_id,
                    "failure_code": "FOLLOW_UP_CONTEXT_MISSING",
                    "dispatch_attempted": False,
                }
            else:
                pending = output / f"dispatch-{case.id}-attempt-{attempt}.json"
                publish_json(
                    pending,
                    {
                        "run_id": executor.run_id,
                        "case_id": case.id,
                        "attempt": attempt,
                        "conversation_id": conversation_id,
                        "status": "dispatch_started",
                    },
                )
                row = await executor.execute(
                    case,
                    conversation_id=conversation_id,
                    parent_turn_id=parent["turn_id"] if parent else None,
                    attempt=attempt,
                )
            if executor.is_paused():
                row["failure_code"] = load_json(executor.counters)["stop_reason"]
            row.update(
                dataset_sha256=dataset.dataset_sha256,
                corpus_sha256=dataset.corpus_sha256,
                derivation_sha256=derivation_sha256,
            )
            publish_json(path, row)
        rows.append(row)
        by_case[case.id] = row
        if row.get("conversation_id"):
            conversations[case.id] = row["conversation_id"]
    return rows


def selected_observations(
    output, *, revalidation_record=None, proposal_sha256=None, derivation_sha256=None
):
    selections = (
        load_revalidation_selection(
            output,
            revalidation_record,
            proposal_sha256=proposal_sha256,
            derivation_sha256=derivation_sha256,
        )
        if revalidation_record is not None
        else {}
    )
    rows = {}
    for path in output.glob("case-*.json"):
        row = load_json(path)
        previous = rows.get(row["case_id"])
        if previous is None or row["attempt"] > previous["attempt"]:
            rows[row["case_id"]] = row
    return list((rows | selections).values())


def main():
    from evals.datasets.pdf_retrieval_v3_v1 import load_dataset, validate_approval
    from evals.runners.pdf_source_binding import propose_bindings, validate_binding_review

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("validate", "upload", "propose", "collect", "report"))
    parser.add_argument(
        "--manifest", type=Path, default=Path("evals/datasets/pdf_retrieval_v3_v1.manifest.json")
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/datasets/pdf_retrieval_v3_v1.jsonl")
    )
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--workspace-id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8153")
    parser.add_argument("--binding-review", type=Path)
    parser.add_argument("--response-reviews", type=Path)
    parser.add_argument("--counters", type=Path)
    parser.add_argument("--resume-quota", action="store_true")
    args = parser.parse_args()
    dataset = load_dataset(args.manifest, args.dataset)
    if args.stage == "validate":
        publish_json(
            args.output,
            {
                "status": "owner_review_pending",
                "corpus_sha256": dataset.corpus_sha256,
                "dataset_sha256": dataset.dataset_sha256,
                "pdfs": len(dataset.sources),
                "cases": len(dataset.cases),
            },
        )
        return
    if not args.approval:
        parser.error("--approval is required before B or scoring")
    validate_approval(dataset, load_json(args.approval))
    if not args.run_id or not args.workspace_id:
        parser.error("--run-id and --workspace-id required")
    if args.stage == "report":
        if not args.binding_review:
            parser.error("--binding-review is required before scoring")
        proposals = load_json(args.output / "binding-proposals.json")
        if (
            proposals["corpus_sha256"] != dataset.corpus_sha256
            or proposals["dataset_sha256"] != dataset.dataset_sha256
        ):
            raise ValueError("binding corpus/gold drift")
        bindings = validate_binding_review(proposals, load_json(args.binding_review))
        rows = selected_observations(args.output)
        for row in rows:
            validate_artifact_identity(
                row,
                dataset,
                args.run_id,
                args.workspace_id,
                derivation_sha256=proposals["derivation_sha256"],
            )
        source_results = {
            row["source_id"]: row
            for row in (load_json(p) for p in args.output.glob("source-*.json"))
        }
        for row in source_results.values():
            validate_artifact_identity(row, dataset, args.run_id, args.workspace_id)
        report = build_report(
            dataset,
            rows,
            bindings,
            load_json(args.response_reviews) if args.response_reviews else {},
            source_results=source_results,
        )
        report.update(
            run_id=args.run_id,
            workspace_id=args.workspace_id,
            derivation_sha256=proposals["derivation_sha256"],
            binding_review_sha256=digest(load_json(args.binding_review)),
        )
        if args.counters:
            counters = load_json(args.counters)
            validate_counter_identity(counters, dataset, args.run_id)
            report["request_counters"] = counters
        publish_json(args.output / "report.json", report)
        return
    import os
    from urllib.parse import urlparse

    database = urlparse(os.environ["KNORA_DATABASE_URL"])
    if (
        database.hostname not in {"127.0.0.1", "localhost"}
        or database.port != 55453
        or not database.path.startswith("/knora153s1_")
    ):
        parser.error("use owned loopback55453 knora153s1_ database")
    from knora.adapters.postgres.database import SessionFactory
    from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader

    reader = PostgresEvaluationReader(SessionFactory)
    if args.stage == "propose":
        publish_json(
            args.output / "binding-proposals.json",
            propose_bindings(dataset, reader.read_pdf_chunks(workspace_id=args.workspace_id)),
        )
        return
    if args.base_url != "http://127.0.0.1:8153":
        parser.error("conditional B uses the owned loopback8153 runtime")
    if not args.counters:
        parser.error("--counters required for conditional B")
    counters = load_json(args.counters)
    validate_counter_identity(counters, dataset, args.run_id)
    token = os.environ["KNORA_S1_BEARER_TOKEN"]

    async def run():
        async with httpx.AsyncClient(base_url=args.base_url, timeout=120) as client:
            executor = PdfHttpExecutor(
                client=client,
                headers={"Authorization": f"Bearer {token}"},
                reader=reader,
                workspace_id=args.workspace_id,
                run_id=args.run_id,
                embedding_configuration_id="embedding-cloudflare-qwen3-06b-v1",
            )
            executor.counters = args.counters
            if args.stage == "upload":
                for source in dataset.sources:
                    path = args.output / f"source-{source.id}.json"
                    if path.exists():
                        saved = load_json(path)
                        validate_artifact_identity(saved, dataset, args.run_id, args.workspace_id)
                        if (
                            saved.get("source_id") != source.id
                            or saved.get("raw_sha256") != source.sha256
                        ):
                            raise ValueError("saved source identity mismatch")
                        continue
                    source_result = await executor.upload(source)
                    source_result.update(
                        source_id=source.id,
                        raw_sha256=source.sha256,
                        run_id=args.run_id,
                        workspace_id=args.workspace_id,
                        corpus_sha256=dataset.corpus_sha256,
                        dataset_sha256=dataset.dataset_sha256,
                    )
                    publish_json(path, source_result)
            else:
                if not args.binding_review:
                    parser.error("--binding-review is required before questions")
                proposals = propose_bindings(
                    dataset, reader.read_pdf_chunks(workspace_id=args.workspace_id)
                )
                validate_binding_review(proposals, load_json(args.binding_review))
                rows = await collect_cases(
                    dataset,
                    executor,
                    args.output,
                    derivation_sha256=proposals["derivation_sha256"],
                    resume_quota=args.resume_quota,
                )
                for row in rows:
                    # Records carry source/derivation identity before immutable publication.
                    if row.get("derivation_sha256") != proposals["derivation_sha256"]:
                        raise ValueError("collected derivation identity mismatch")

    asyncio.run(run())


if __name__ == "__main__":
    main()
