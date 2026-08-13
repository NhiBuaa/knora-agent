import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARTIFACT_SHA256 = "692eac26a4d4857bb7fd147213ca8b5691961b3b4878f7dc915bda55ef281f07"
RULES_VERSION = "m3-calibration-independence-comparison-v1"
OVERLAP_THRESHOLD = 0.8
ZIP_TIMESTAMP = (2026, 8, 13, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class SemanticItem:
    item_id: str
    kind: str
    content: str
    source_reference: str

    def record(self) -> dict[str, Any]:
        normalized = normalize(self.content)
        return {
            "item_id": self.item_id,
            "kind": self.kind,
            "source_reference": self.source_reference,
            "content": self.content,
            "content_sha256": sha256(self.content.encode()),
            "normalized": normalized,
            "normalized_sha256": sha256(normalized.encode()),
            "normalized_tokens": normalized.split(),
        }


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_text_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_json(value: Any) -> bytes:
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return (serialized + "\n").encode()


def normalize(content: str) -> str:
    value = unicodedata.normalize("NFKC", content).casefold()
    return " ".join(re.findall(r"\w+", value, flags=re.UNICODE))


def sentences(content: str) -> tuple[str, ...]:
    parts = re.split(r"(?<=[.!?])\s+", content.strip())
    return tuple(part.strip() for part in parts if part.strip())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def calibration_inventory(root: Path) -> tuple[dict[str, Any], list[SemanticItem]]:
    base = root / "evals/calibration/m3_retrieval_v1"
    manifest_path = base / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    if sha256(manifest_bytes) != ARTIFACT_SHA256:
        raise ValueError("frozen calibration manifest digest mismatch")
    manifest = json.loads(manifest_bytes)
    for member in manifest["files"]:
        if sha256((base / member["path"]).read_bytes()) != member["sha256"]:
            raise ValueError(f"frozen calibration member mismatch: {member['path']}")
    cases = read_jsonl(base / "cases.jsonl")
    lineage = read_json(base / "lineage.json")
    corpus_members = [
        member
        for member in manifest["files"]
        if member["path"].startswith("corpus/")
    ]
    corpus_refs = {f"calibration/{Path(member['path']).stem}#0" for member in corpus_members}
    if set(lineage["case_ids"]) != {case["id"] for case in cases}:
        raise ValueError("calibration lineage does not cover every case")
    if set(lineage["documents"]) != {Path(member["path"]).name for member in corpus_members}:
        raise ValueError("calibration lineage does not cover every source")
    judgments: list[dict[str, Any]] = []
    semantic_items: list[SemanticItem] = []
    sources: list[dict[str, Any]] = []
    for member in corpus_members:
        content = (base / member["path"]).read_text(encoding="utf-8").strip()
        source_key = f"calibration/{Path(member['path']).stem}#0"
        facts = list(sentences(content))
        sources.append(
            {
                "source_key": source_key,
                "path": member["path"],
                "content": content,
                "facts": facts,
            }
        )
        semantic_items.append(
            SemanticItem(
                f"source:{source_key}", "source-content", content, member["path"]
            )
        )
        semantic_items.extend(
            SemanticItem(f"fact:{source_key}:{index}", "source-fact", fact, member["path"])
            for index, fact in enumerate(facts)
        )
    for case in cases:
        record = {
            "case_id": case["id"],
            "question": case["question"],
            "applicable": case["applicable"],
            "judgment": case["judgment"],
            "gold_chunk_refs": case["gold_chunk_refs"],
            "near_negative_chunk_refs": case.get("near_negative_chunk_refs", []),
            "unrelated_negative_chunk_refs": case.get("unrelated_negative_chunk_refs", []),
            "author_id": case["author_id"],
        }
        referenced = set(
            record["gold_chunk_refs"]
            + record["near_negative_chunk_refs"]
            + record["unrelated_negative_chunk_refs"]
        )
        if not referenced <= corpus_refs:
            raise ValueError(f"case contains unresolved reference: {case['id']}")
        judgments.append(record)
        semantic_items.append(
            SemanticItem(
                f"question:{case['id']}",
                "question",
                case["question"],
                "cases.jsonl",
            )
        )
    return {
        "artifact_id": manifest["artifact_id"],
        "artifact_sha256": ARTIFACT_SHA256,
        "freeze_status": manifest["freeze_status"],
        "manifest_member_count": len(manifest["files"]),
        "source_count": len(sources),
        "case_count": len(cases),
        "applicable_case_count": sum(case["applicable"] for case in cases),
        "hard_negative_control_count": sum(
            case["judgment"] == "hard-negative-no-hit" for case in cases
        ),
        "lineage": lineage,
        "sources": sources,
        "cases_and_judgments": judgments,
    }, semantic_items


def development_inventory(root: Path) -> tuple[dict[str, Any], list[SemanticItem]]:
    dataset_path = root / "evals/datasets/milestone_3.jsonl"
    dataset_manifest_path = root / "evals/datasets/milestone_3.manifest.json"
    corpus_base = root / "evals/corpora/milestone_3"
    dataset_manifest = read_json(dataset_manifest_path)
    dataset_bytes = canonical_text_bytes(dataset_path)
    if sha256(dataset_bytes) != dataset_manifest["sha256"]:
        raise ValueError("m3-dataset-v1 digest mismatch")
    cases = read_jsonl(dataset_path)
    corpus_manifest = read_json(corpus_base / "manifest.json")
    sources: list[dict[str, Any]] = []
    semantic_items: list[SemanticItem] = []
    for document in corpus_manifest["documents"]:
        path = corpus_base / document["path"]
        content = path.read_text(encoding="utf-8").strip()
        if sha256(canonical_text_bytes(path)) != document["sha256"]:
            raise ValueError(f"m3 corpus digest mismatch: {document['path']}")
        facts = list(sentences(content))
        sources.append({**document, "content": content, "facts": facts})
        semantic_items.append(
            SemanticItem(
                f"source:{document['path']}",
                "source-content",
                content,
                f"corpus/{document['path']}",
            )
        )
        semantic_items.extend(
            SemanticItem(
                f"fact:{document['path']}:{index}",
                "source-fact",
                fact,
                f"corpus/{document['path']}",
            )
            for index, fact in enumerate(facts)
        )
    case_records: list[dict[str, Any]] = []
    for case in cases:
        case_records.append(case)
        semantic_items.append(
            SemanticItem(
                f"question:{case['id']}",
                "question",
                case["question"],
                "datasets/milestone_3.jsonl",
            )
        )
        answer = case["answer_expectations"]
        for index, fact in enumerate(answer["required_facts"]):
            semantic_items.append(
                SemanticItem(
                    f"required-fact:{case['id']}:{index}",
                    "required-fact",
                    fact,
                    "datasets/milestone_3.jsonl",
                )
            )
        if answer["reference_answer"]:
            semantic_items.append(
                SemanticItem(
                    f"reference-answer:{case['id']}",
                    "reference-answer",
                    answer["reference_answer"],
                    "datasets/milestone_3.jsonl",
                )
            )
    if len(cases) != 50:
        raise ValueError("m3-dataset-v1 population is not the complete 50-case release")
    return {
        "dataset_id": dataset_manifest["version"],
        "dataset_sha256": dataset_manifest["sha256"],
        "dataset_case_count": len(cases),
        "corpus_id": corpus_manifest["version"],
        "corpus_document_count": len(sources),
        "corpus_manifest_sha256": sha256((corpus_base / "manifest.json").read_bytes()),
        "sources": sources,
        "cases": case_records,
    }, semantic_items


def comparison_report(
    calibration: list[SemanticItem], development: list[SemanticItem]
) -> dict[str, Any]:
    exact: list[dict[str, Any]] = []
    overlaps: list[dict[str, Any]] = []
    pair_digests: list[str] = []
    for left in calibration:
        left_normalized = normalize(left.content)
        left_tokens = set(left_normalized.split())
        for right in development:
            right_normalized = normalize(right.content)
            right_tokens = set(right_normalized.split())
            denominator = min(len(left_tokens), len(right_tokens))
            overlap = len(left_tokens & right_tokens) / denominator if denominator else 0.0
            pair = {
                "calibration_item_id": left.item_id,
                "development_item_id": right.item_id,
                "exact_normalized_copy": left_normalized == right_normalized,
                "normalized_token_overlap": format(overlap, ".12f"),
            }
            pair_digests.append(sha256(canonical_json(pair)))
            if pair["exact_normalized_copy"]:
                exact.append(pair)
            elif overlap >= OVERLAP_THRESHOLD:
                overlaps.append(pair)
    return {
        "rules_version": RULES_VERSION,
        "normalization": (
            "Unicode NFKC -> Unicode casefold -> regex Unicode word tokens -> "
            "single ASCII-space join"
        ),
        "exact_copy_rule": "normalized strings are byte-equal",
        "normalized_overlap_rule": (
            "size(set(left tokens) intersection set(right tokens)) / "
            "min(size(set(left tokens)), size(set(right tokens)))"
        ),
        "normalized_overlap_threshold": format(OVERLAP_THRESHOLD, ".12f"),
        "calibration_item_count": len(calibration),
        "development_item_count": len(development),
        "evaluated_pair_count": len(calibration) * len(development),
        "pair_population_digest": sha256("\n".join(pair_digests).encode()),
        "exact_copy_match_count": len(exact),
        "normalized_overlap_match_count": len(overlaps),
        "exact_copy_matches": exact,
        "normalized_overlap_matches": overlaps,
        "deterministic_result": "PASS" if not exact and not overlaps else "FAIL",
    }


def reviewer_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "bundle_sha256",
            "calibration_artifact_sha256",
            "reviewer_id",
            "reviewer_was_author",
            "reviewed_complete_population",
            "verdict",
            "rephrase_or_derivation_findings",
            "reviewed_at",
        ],
        "properties": {
            "schema_version": {"const": 1},
            "bundle_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "calibration_artifact_sha256": {"const": ARTIFACT_SHA256},
            "reviewer_id": {"type": "string", "minLength": 1},
            "reviewer_was_author": {"const": False},
            "reviewed_complete_population": {"const": True},
            "verdict": {"enum": ["PASS", "FAIL", "INDETERMINATE"]},
            "rephrase_or_derivation_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "calibration_reference",
                        "development_reference",
                        "assessment",
                    ],
                    "properties": {
                        "calibration_reference": {"type": "string"},
                        "development_reference": {"type": "string"},
                        "assessment": {
                            "enum": ["REPHRASE", "DERIVATION", "INDETERMINATE"]
                        },
                    },
                },
            },
            "reviewed_at": {"type": "string", "format": "date-time"},
        },
    }


def zip_bytes(files: dict[str, bytes], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o444 << 16
            archive.writestr(info, files[name])


def export(root: Path, output: Path) -> None:
    calibration, calibration_items = calibration_inventory(root)
    development, development_items = development_inventory(root)
    files: dict[str, bytes] = {}
    calibration_base = root / "evals/calibration/m3_retrieval_v1"
    calibration_manifest = read_json(calibration_base / "manifest.json")
    calibration_paths = [
        calibration_base / "manifest.json",
        *(calibration_base / member["path"] for member in calibration_manifest["files"]),
    ]
    for path in calibration_paths:
        relative = path.relative_to(calibration_base).as_posix()
        files[f"raw/calibration/{relative}"] = path.read_bytes()
    development_paths = [
        root / "evals/datasets/milestone_3.manifest.json",
        root / "evals/datasets/milestone_3.jsonl",
        *(root / "evals/corpora/milestone_3").glob("*"),
    ]
    for path in development_paths:
        relative = path.relative_to(root / "evals").as_posix()
        files[f"raw/development/{relative}"] = canonical_text_bytes(path)
    files["review/calibration-inventory.json"] = canonical_json(calibration)
    files["review/development-inventory.json"] = canonical_json(development)
    files["review/calibration-semantic-items.json"] = canonical_json(
        [item.record() for item in calibration_items]
    )
    files["review/development-semantic-items.json"] = canonical_json(
        [item.record() for item in development_items]
    )
    files["review/deterministic-comparison-report.json"] = canonical_json(
        comparison_report(calibration_items, development_items)
    )
    files["review/reviewer-attestation.schema.json"] = canonical_json(reviewer_schema())
    files["README.md"] = (
        "# Issue #56 TC-05 independent semantic-review bundle\n\n"
        f"Frozen calibration manifest SHA-256: `{ARTIFACT_SHA256}`.\n\n"
        "This read-only bundle contains the complete frozen calibration manifest and every member, "
        "the complete 50-case m3-dataset-v1 release, every m3-corpus-v1 document and manifest, "
        "review inventories, and the complete deterministic comparison population. It contains no "
        "provider credential, provider response, embedding, score, candidate, or calibration "
        "result.\n\n"
        "The reviewer must inspect all sources, questions, facts, and judgments for copying, "
        "rephrasing, or derivation. Return a separate JSON attestation satisfying "
        "review/reviewer-attestation.schema.json "
        "with PASS, FAIL, or INDETERMINATE. Do not edit this bundle.\n"
    ).encode()
    payload_manifest = {
        "schema_version": 1,
        "bundle_id": "issue-56-tc-05-semantic-review-bundle-v1",
        "calibration_artifact_sha256": ARTIFACT_SHA256,
        "rules_version": RULES_VERSION,
        "content_scope": "complete-populations-not-samples",
        "provider_material_included": False,
        "members": [
            {
                "path": name,
                "byte_count": len(content),
                "sha256": sha256(content),
            }
            for name, content in sorted(files.items())
        ],
    }
    files["BUNDLE-MANIFEST.json"] = canonical_json(payload_manifest)
    zip_bytes(files, output)
    result = {
        "output": str(output),
        "sha256": sha256(output.read_bytes()),
        "byte_count": output.stat().st_size,
        "member_count": len(files),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    export(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
