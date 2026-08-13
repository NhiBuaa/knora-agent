import hashlib
import json
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from knora.answering.calibration_independence_v2 import (
    AuthoredCalibrationItem,
    IndependencePolicy,
    SemanticReview,
    audit_calibration_independence,
)

REQUIRED_JUDGMENT_CATEGORIES = {
    "applicable-relevance",
    "gold",
    "near-negative",
    "unrelated-negative",
    "hard-negative-no-hit",
}


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _semantic_review(base: Path, artifact_digest: str) -> SemanticReview | None:
    path = base / "semantic-review.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    expected_keys = {
        "schema_version",
        "reviewer_id",
        "reviewer_was_author",
        "rephrase_or_derivation_found",
        "calibration_artifact_sha256",
        "reviewed_at",
    }
    if set(record) != expected_keys or record["schema_version"] != 1:
        raise ValueError("invalid independent semantic review schema")
    if not isinstance(record["reviewer_id"], str) or not record["reviewer_id"]:
        raise ValueError("invalid independent semantic reviewer identity")
    if record["reviewer_was_author"] is not False:
        raise ValueError("semantic reviewer is not independent")
    if record["rephrase_or_derivation_found"] is not False:
        raise ValueError("semantic review found derivation")
    if record["calibration_artifact_sha256"] != artifact_digest:
        raise ValueError("semantic review is not bound to frozen calibration")
    try:
        datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError("invalid semantic review timestamp") from error
    return SemanticReview(
        reviewer_id=record["reviewer_id"],
        reviewer_was_author=False,
        rephrase_or_derivation_found=False,
        calibration_sha256=artifact_digest,
    )


def validate(base: Path, development_dataset: Path) -> dict[str, object]:
    manifest_path = base / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["artifact_id"] != "m3-retrieval-calibration-v1":
        raise ValueError("wrong calibration artifact identity")
    if manifest["freeze_status"] != "frozen-before-first-execution":
        raise ValueError("calibration artifact is not frozen before first execution")
    artifact_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    for record in manifest["files"]:
        if hashlib.sha256((base / record["path"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"calibration checksum mismatch: {record['path']}")
    cases = [
        json.loads(line)
        for line in (base / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    documents = [record for record in manifest["files"] if record["path"].startswith("corpus/")]
    applicable = [case for case in cases if case["applicable"]]
    if len(documents) <= 8:
        raise ValueError("calibration candidate universe is not informative")
    source_keys = {
        f"calibration/{Path(record['path']).stem}#0" for record in documents
    }
    for case in applicable:
        gold = set(case["gold_chunk_refs"])
        near = set(case["near_negative_chunk_refs"])
        unrelated = set(case["unrelated_negative_chunk_refs"])
        if not gold or not gold | near | unrelated <= source_keys:
            raise ValueError(f"unresolved calibration judgment reference: {case['id']}")
        if gold & near or gold & unrelated or near & unrelated:
            raise ValueError(f"overlapping calibration judgment: {case['id']}")
        if len(source_keys - gold) < 8:
            raise ValueError(f"insufficient non-gold distractors: {case['id']}")
    if not any(len(case["gold_chunk_refs"]) > 1 for case in applicable):
        raise ValueError("multi-relevant gold coverage is missing")
    if not any(case["judgment"] == "hard-negative-no-hit" for case in cases):
        raise ValueError("calibration judgments are incomplete")
    lineage = json.loads((base / "lineage.json").read_text(encoding="utf-8"))
    if set(lineage["case_ids"]) != {case["id"] for case in cases}:
        raise ValueError("calibration case lineage is incomplete")
    if set(lineage["documents"]) != {Path(record["path"]).name for record in documents}:
        raise ValueError("calibration document lineage is incomplete")
    if set(lineage["judgment_categories"]) != REQUIRED_JUDGMENT_CATEGORIES:
        raise ValueError("calibration judgment lineage is incomplete")
    development_records = [
        json.loads(line)
        for line in development_dataset.read_text(encoding="utf-8").splitlines()
    ]
    development = list(_strings(development_records))
    development_corpus = development_dataset.parents[1] / "corpora" / "milestone_3"
    development.extend(
        path.read_text(encoding="utf-8")
        for path in sorted(development_corpus.glob("*.txt"))
    )
    authored_questions = tuple(
        AuthoredCalibrationItem(
            case["id"], "question", case["question"], case["author_id"]
        )
        for case in cases
    )
    authored_documents = tuple(
        AuthoredCalibrationItem(
            f"document:{Path(record['path']).name}",
            "document",
            (base / record["path"]).read_text(encoding="utf-8"),
            lineage["authoring_identity"],
        )
        for record in documents
    )
    authored = authored_questions + authored_documents
    semantic_review = _semantic_review(base, artifact_digest)
    pending_review = SemanticReview(
        "pending-independent-review", True, False, artifact_digest
    )
    deterministic = audit_calibration_independence(
        calibration_sha256=artifact_digest,
        calibration_items=authored,
        development_items=tuple(development),
        semantic_review=semantic_review or pending_review,
        policy=IndependencePolicy.v1(),
    )
    if deterministic.exact_copy_matches or deterministic.normalized_overlap_matches:
        raise ValueError("calibration independence deterministic oracle failed")
    return {
        "artifact_id": manifest["artifact_id"],
        "artifact_sha256": artifact_digest,
        "file_count": len(manifest["files"]),
        "case_count": len(cases),
        "applicable_case_count": len(applicable),
        "deterministic_independence": "PASS",
        "independent_semantic_review": "PASS" if semantic_review else "PENDING",
        "first_execution_allowed": deterministic.passed,
    }


if __name__ == "__main__":
    print(json.dumps(validate(Path(sys.argv[1]), Path(sys.argv[2])), sort_keys=True))
