"""Versioned Vietnamese PDF retrieval labels and provenance checks."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class DatasetContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VietnameseCase:
    id: str
    question: str
    source_key: str
    page_start: int | None
    acceptable_chunk_checksums: tuple[str, ...]
    required_facts: tuple[str, ...]
    expected_behavior: Literal["ANSWER", "REFUSAL"]
    split: Literal["calibration", "held_out"]


@dataclass(frozen=True, slots=True)
class VietnameseDataset:
    cases: tuple[VietnameseCase, ...]
    version: str
    dataset_sha256: str
    profile_id: str
    model_digest: str
    corpus_sha256: str
    chunk_set_ids: tuple[str, ...]
    retrieval_configuration_id: str


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetContractError(f"invalid {field}")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise DatasetContractError(f"invalid {field}")
    return value


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise DatasetContractError(f"invalid {field}")
    return tuple(value)


def load_vietnamese_dataset(path: Path, manifest_path: Path) -> VietnameseDataset:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_sha256") != hashlib.sha256(raw).hexdigest():
        raise DatasetContractError("dataset_sha256 mismatch")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise DatasetContractError("sources missing")
    source_keys = set()
    for source in sources:
        if not isinstance(source, dict):
            raise DatasetContractError("invalid source")
        source_key = _nonempty(source.get("source_key"), "source_key")
        _sha(source.get("raw_sha256"), "raw_sha256")
        if source_key in source_keys:
            raise DatasetContractError("duplicate source_key")
        source_keys.add(source_key)
    if manifest.get("corpus_digest_scheme", "single-original-pdf-sha256-v1") != (
        "single-original-pdf-sha256-v1"
    ):
        raise DatasetContractError("unsupported corpus digest scheme")
    if len(sources) != 1 or sources[0]["raw_sha256"] != manifest.get("corpus_sha256"):
        raise DatasetContractError("source digest does not match single-PDF corpus")
    cases = []
    seen = set()
    for line in raw.decode("utf-8-sig").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise DatasetContractError("case must be an object")
        case_id = _nonempty(record.get("id"), "id")
        if case_id in seen:
            raise DatasetContractError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        question = _nonempty(record.get("question"), "question")
        source_key = _nonempty(record.get("source_key"), "source_key")
        if source_key not in source_keys:
            raise DatasetContractError(f"unknown source_key: {source_key}")
        behavior = record.get("expected_behavior")
        split = record.get("split")
        if behavior not in ("ANSWER", "REFUSAL") or split not in ("calibration", "held_out"):
            raise DatasetContractError(f"invalid behavior/split for {case_id}")
        page = record.get("page_start")
        checksums = _strings(record.get("acceptable_chunk_checksums"), "acceptable_chunk_checksums")
        for checksum in checksums:
            _sha(checksum, "acceptable_chunk_checksums")
        facts = _strings(record.get("required_facts"), "required_facts")
        if behavior == "ANSWER":
            if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                raise DatasetContractError(f"invalid page_start for {case_id}")
            if not checksums or not facts:
                raise DatasetContractError(
                    f"ANSWER case {case_id} requires chunks and required_facts"
                )
        elif page is not None or checksums or facts:
            raise DatasetContractError(
                f"REFUSAL case {case_id} must not have page/chunks/required_facts"
            )
        cases.append(
            VietnameseCase(case_id, question, source_key, page, checksums, facts, behavior, split)
        )
    if not cases:
        raise DatasetContractError("dataset is empty")
    calibration_chunks = {
        checksum
        for case in cases
        if case.split == "calibration"
        for checksum in case.acceptable_chunk_checksums
    }
    held_out_chunks = {
        checksum
        for case in cases
        if case.split == "held_out"
        for checksum in case.acceptable_chunk_checksums
    }
    if calibration_chunks & held_out_chunks:
        raise DatasetContractError("gold Chunk split independence violation")
    chunk_set_ids = _strings(manifest.get("chunk_set_ids"), "chunk_set_ids")
    if not chunk_set_ids:
        raise DatasetContractError("chunk_set_ids missing")
    model_digest = _nonempty(manifest.get("model_digest"), "model_digest")
    if not model_digest.startswith("sha256:"):
        raise DatasetContractError("invalid model_digest")
    _sha(model_digest.removeprefix("sha256:"), "model_digest")
    return VietnameseDataset(
        tuple(cases),
        _nonempty(manifest.get("version"), "version"),
        manifest["dataset_sha256"],
        _nonempty(manifest.get("profile_id"), "profile_id"),
        model_digest,
        _sha(manifest.get("corpus_sha256"), "corpus_sha256"),
        chunk_set_ids,
        _nonempty(manifest.get("retrieval_configuration_id"), "retrieval_configuration_id"),
    )
