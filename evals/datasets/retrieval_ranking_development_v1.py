"""Versioned retrieval ranking development supplement dataset and approval validator."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from evals.runners.retrieval_ranking import RankingJudgment


class DatasetContractError(ValueError):
    """Raised when ranking dataset violates schema or authority invariants."""

    pass


@dataclass(frozen=True, slots=True)
class CandidateUniverseChunk:
    chunk_id: str
    source_key: str
    document_version_id: str
    chunk_set_id: str
    raw_sha256: str
    content_checksum: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class RankingDevelopmentCase:
    id: str
    question: str
    expected_behavior: str
    category: str
    language: str
    split: str
    relevant_chunk_ids: tuple[str, ...]
    judgments: tuple[RankingJudgment, ...]
    judgments_by_chunk_id: dict[str, RankingJudgment]


@dataclass(frozen=True, slots=True)
class RankingDevelopmentDataset:
    schema_version: int
    version: str
    corpus_sha256: str
    derivation_sha256: str
    dataset_sha256: str
    candidate_universe: tuple[CandidateUniverseChunk, ...]
    candidate_universe_ids: frozenset[str]
    cases: tuple[RankingDevelopmentCase, ...]
    cases_by_id: dict[str, RankingDevelopmentCase]
    metric_policy: dict[str, object]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DatasetContractError(message)


def _text(value: object, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"invalid {field}")
    return value


def _sha(value: object, field: str) -> str:
    _require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        f"invalid {field}",
    )
    return value


def load_ranking_development_dataset(
    manifest_path: Path, dataset_path: Path
) -> RankingDevelopmentDataset:
    """Load and validate the retrieval ranking development supplement."""
    try:
        manifest_raw = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_raw)
        _require(isinstance(manifest, dict), "manifest must be an object")
        _require(manifest.get("schema_version") == 1, "unsupported schema_version")

        corpus_sha = _sha(manifest.get("corpus_sha256"), "corpus_sha256")
        derivation_sha = _sha(manifest.get("derivation_sha256"), "derivation_sha256")
        expected_dataset_sha = _sha(manifest.get("dataset_sha256"), "dataset_sha256")

        raw_bytes = dataset_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        actual_dataset_sha = hashlib.sha256(raw_bytes).hexdigest()
        _require(actual_dataset_sha == expected_dataset_sha, "dataset_sha256 drift")

        universe_raw = manifest.get("candidate_universe")
        _require(
            isinstance(universe_raw, list) and bool(universe_raw), "candidate_universe missing"
        )
        universe_chunks = []
        universe_ids = set()
        universe_checksums = {}

        for row in universe_raw:
            cid = _text(row.get("chunk_id"), "chunk_id")
            _require(cid not in universe_ids, f"duplicate universe chunk_id: {cid}")
            universe_ids.add(cid)
            checksum = _sha(row.get("content_checksum"), "content_checksum")
            universe_checksums[cid] = checksum
            raw_sha = _sha(row.get("raw_sha256"), "raw_sha256")
            p_start = row.get("page_start")
            p_end = row.get("page_end")
            _require(
                type(p_start) is int and type(p_end) is int and 1 <= p_start <= p_end,
                "invalid chunk pages",
            )
            universe_chunks.append(
                CandidateUniverseChunk(
                    chunk_id=cid,
                    source_key=_text(row.get("source_key"), "source_key"),
                    document_version_id=_text(
                        row.get("document_version_id"), "document_version_id"
                    ),
                    chunk_set_id=_text(row.get("chunk_set_id"), "chunk_set_id"),
                    raw_sha256=raw_sha,
                    content_checksum=checksum,
                    page_start=p_start,
                    page_end=p_end,
                )
            )

        cases = []
        cases_by_id = {}
        seen_case_ids = set()

        for line_num, line in enumerate(raw_bytes.decode("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            _require(isinstance(record, dict), f"case at line {line_num} must be an object")

            case_id = _text(record.get("id"), f"case id at line {line_num}")
            _require(case_id not in seen_case_ids, f"duplicate case id: {case_id}")
            seen_case_ids.add(case_id)

            behavior = record.get("expected_behavior")
            _require(behavior in ("ANSWER", "REFUSAL"), f"invalid expected_behavior for {case_id}")

            split = record.get("split")
            _require(split == "development", f"split must be 'development' for {case_id}")

            judgments_raw = record.get("judgments")
            _require(
                isinstance(judgments_raw, list) and len(judgments_raw) == len(universe_chunks),
                (
                    f"case {case_id} judgments must exhaustively cover "
                    f"candidate universe ({len(universe_chunks)})"
                ),
            )

            judgments = []
            judgments_by_chunk = {}
            case_chunk_ids = set()

            for j_row in judgments_raw:
                _require(isinstance(j_row, dict), f"invalid judgment row in {case_id}")
                q_id = _text(j_row.get("query_id"), "query_id")
                _require(q_id == case_id, f"judgment query_id mismatch: {q_id} != {case_id}")

                cid = _text(j_row.get("chunk_id"), "judgment chunk_id")
                _require(cid in universe_ids, f"judgment chunk_id {cid} not in universe")
                _require(
                    cid not in case_chunk_ids, f"duplicate judgment for chunk {cid} in {case_id}"
                )
                case_chunk_ids.add(cid)

                chk = _sha(j_row.get("content_checksum"), "judgment content_checksum")
                _require(
                    chk == universe_checksums[cid],
                    f"content_checksum drift for chunk {cid} in {case_id}",
                )

                grade = j_row.get("grade")
                _require(grade in (0, 1), f"grade must be 0 or 1, got {grade} in {case_id}")

                reviewer = j_row.get("reviewer")
                _require(reviewer == "NhiBuaa", f"invalid reviewer {reviewer} in {case_id}")

                judgment = RankingJudgment(
                    query_id=case_id,
                    chunk_id=cid,
                    content_checksum=chk,
                    grade=grade,
                    source_key=j_row.get("source_key"),
                    rubric=j_row.get("rubric"),
                    reviewer=reviewer,
                )
                judgments.append(judgment)
                judgments_by_chunk[cid] = judgment

            if behavior == "REFUSAL":
                _require(
                    all(j.grade == 0 for j in judgments),
                    f"REFUSAL case {case_id} must have 0 positive judgments",
                )

            rel_ids = tuple(record.get("relevant_chunk_ids", []))
            _require(
                set(rel_ids) == {j.chunk_id for j in judgments if j.grade > 0},
                f"relevant_chunk_ids mismatch in {case_id}",
            )

            case_obj = RankingDevelopmentCase(
                id=case_id,
                question=_text(record.get("question"), "question"),
                expected_behavior=behavior,
                category=_text(record.get("category"), "category"),
                language=_text(record.get("language"), "language"),
                split=split,
                relevant_chunk_ids=rel_ids,
                judgments=tuple(judgments),
                judgments_by_chunk_id=judgments_by_chunk,
            )
            cases.append(case_obj)
            cases_by_id[case_id] = case_obj

        metric_policy = manifest.get("metric_policy", {})
        _require(isinstance(metric_policy, dict), "metric_policy must be an object")

        return RankingDevelopmentDataset(
            schema_version=1,
            version=manifest.get("version", "retrieval-ranking-development-v1"),
            corpus_sha256=corpus_sha,
            derivation_sha256=derivation_sha,
            dataset_sha256=actual_dataset_sha,
            candidate_universe=tuple(universe_chunks),
            candidate_universe_ids=frozenset(universe_ids),
            cases=tuple(cases),
            cases_by_id=cases_by_id,
            metric_policy=metric_policy,
        )
    except (KeyError, TypeError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise DatasetContractError(f"invalid ranking dataset: {exc}") from exc


def validate_ranking_approval(
    dataset: RankingDevelopmentDataset, approval: dict[str, object]
) -> None:
    """Validate that the ranking development supplement has authoritative owner approval."""
    _require(
        isinstance(approval, dict)
        and approval.get("status") == "approved"
        and approval.get("owner") == "NhiBuaa"
        and approval.get("corpus_sha256") == dataset.corpus_sha256
        and approval.get("derivation_sha256") == dataset.derivation_sha256
        and approval.get("dataset_sha256") == dataset.dataset_sha256,
        "owner ranking approval missing or approval digest drift",
    )
