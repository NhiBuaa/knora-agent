from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class DatasetContractError(ValueError):
    pass


QUALITY_CATEGORIES = {
    "lexical_exact_match",
    "semantic_paraphrase",
    "multi_source",
    "insufficient_evidence_refusal",
}


@dataclass(frozen=True, slots=True)
class RetrievalRelevance:
    applicable: bool
    acceptable_relevant_chunks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerExpectations:
    required_facts: tuple[str, ...]
    reference_answer: str | None


@dataclass(frozen=True, slots=True)
class EvidenceExpectations:
    expected_source_documents: tuple[str, ...]
    acceptable_cited_chunks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Milestone3Case:
    id: str
    category: str
    workspace_id: str
    question: str
    expected_behavior: str
    retrieval_relevance: RetrievalRelevance
    answer_expectations: AnswerExpectations
    evidence_expectations: EvidenceExpectations
    refusal_expectation: str | None


@dataclass(frozen=True, slots=True)
class Milestone3Dataset:
    cases: tuple[Milestone3Case, ...]


@dataclass(frozen=True, slots=True)
class DatasetManifestIdentity:
    version: str
    checksum: str


@dataclass(frozen=True, slots=True)
class Milestone3CorpusManifest:
    version: str
    workspace_id: str
    chunk_set_id: str
    chunks: frozenset[str]


def _required(record: dict[str, object], field: str, label: str) -> object:
    if field not in record:
        raise DatasetContractError(f"case {label} missing field: {field}")
    return record[field]


def _strings(value: object, field: str, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise DatasetContractError(f"case {label} invalid field: {field}")
    return tuple(value)


def load_milestone_3_dataset(path: Path) -> Milestone3Dataset:
    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line
    ]
    cases: list[Milestone3Case] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise DatasetContractError("case must be an object")
        label = str(record.get("id", "unknown"))
        case_id = _required(record, "id", label)
        category = _required(record, "category", label)
        workspace_id = _required(record, "workspace_id", label)
        question = _required(record, "question", label)
        expected_behavior = _required(record, "expected_behavior", label)
        relevance_raw = _required(record, "retrieval_relevance", label)
        answer_raw = _required(record, "answer_expectations", label)
        evidence_raw = _required(record, "evidence_expectations", label)
        refusal = record.get("refusal_expectation")
        if not all(
            isinstance(value, str) and value
            for value in (case_id, category, workspace_id, question)
        ):
            raise DatasetContractError(f"case {label} has invalid scalar fields")
        if case_id in seen:
            raise DatasetContractError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        if category not in QUALITY_CATEGORIES:
            raise DatasetContractError(f"unknown category: {category}")
        if expected_behavior not in {"ANSWER", "REFUSAL"}:
            raise DatasetContractError(f"unknown expected behavior: {expected_behavior}")
        if (
            not isinstance(relevance_raw, dict)
            or not isinstance(answer_raw, dict)
            or not isinstance(evidence_raw, dict)
        ):
            raise DatasetContractError(f"case {case_id} has invalid expectation object")
        applicable = relevance_raw.get("applicable")
        if not isinstance(applicable, bool):
            raise DatasetContractError(f"case {case_id} retrieval relevance requires applicability")
        relevant = _strings(
            relevance_raw.get("acceptable_relevant_chunks"), "acceptable_relevant_chunks", case_id
        )
        facts = _strings(answer_raw.get("required_facts"), "required_facts", case_id)
        sources = _strings(
            evidence_raw.get("expected_source_documents"), "expected_source_documents", case_id
        )
        cited = _strings(
            evidence_raw.get("acceptable_cited_chunks"), "acceptable_cited_chunks", case_id
        )
        reference_answer = answer_raw.get("reference_answer")
        if reference_answer is not None and not isinstance(reference_answer, str):
            raise DatasetContractError(f"case {case_id} invalid reference answer")
        if expected_behavior == "ANSWER":
            if not applicable or not relevant:
                raise DatasetContractError(
                    f"ANSWER case {case_id} requires applicable retrieval relevance"
                )
            if not facts:
                raise DatasetContractError(
                    f"ANSWER case {case_id} requires non-empty required facts"
                )
            if not sources or not cited:
                raise DatasetContractError(f"ANSWER case {case_id} requires evidence expectations")
            if refusal is not None:
                raise DatasetContractError(
                    f"ANSWER case {case_id} must not have a refusal expectation"
                )
        else:
            if applicable or relevant:
                raise DatasetContractError(
                    f"REFUSAL case {case_id} must not apply retrieval relevance"
                )
            if facts:
                raise DatasetContractError(f"REFUSAL case {case_id} must not require facts")
            if refusal != "INSUFFICIENT_EVIDENCE":
                raise DatasetContractError(f"REFUSAL case {case_id} requires INSUFFICIENT_EVIDENCE")
        cases.append(
            Milestone3Case(
                case_id,
                category,
                workspace_id,
                question,
                expected_behavior,
                RetrievalRelevance(applicable, relevant),
                AnswerExpectations(facts, reference_answer),
                EvidenceExpectations(sources, cited),
                refusal,
            )
        )
    if not 50 <= len(cases) <= 100:
        raise DatasetContractError("dataset must contain 50 to 100 cases")
    missing = QUALITY_CATEGORIES - {case.category for case in cases}
    if missing:
        raise DatasetContractError("dataset missing categories: " + ", ".join(sorted(missing)))
    return Milestone3Dataset(tuple(cases))


def load_milestone_3_dataset_manifest(path: Path, dataset_path: Path) -> DatasetManifestIdentity:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("path") != dataset_path.name:
        raise DatasetContractError("dataset path does not match manifest")
    digest = hashlib.sha256(
        dataset_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    ).hexdigest()
    if payload.get("sha256") != digest:
        raise DatasetContractError("dataset checksum mismatch")
    return DatasetManifestIdentity(str(payload["version"]), f"sha256:{digest}")


def load_milestone_3_corpus_manifest(path: Path) -> Milestone3CorpusManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks: set[str] = set()
    root = path.parent
    for document in payload["documents"]:
        source = root / document["path"]
        content = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if hashlib.sha256(content).hexdigest() != document["sha256"]:
            raise DatasetContractError(f"corpus checksum mismatch: {document['path']}")
        references = document["chunk_references"]
        if not isinstance(references, list) or not all(
            isinstance(item, str) and item for item in references
        ):
            raise DatasetContractError(f"invalid chunk references: {document['path']}")
        for reference in references:
            if reference in chunks:
                raise DatasetContractError(f"ambiguous Chunk reference: {reference}")
            chunks.add(reference)
    return Milestone3CorpusManifest(
        str(payload["version"]),
        str(payload["workspace_id"]),
        str(payload["chunk_set_id"]),
        frozenset(chunks),
    )


def validate_milestone_3_references(
    dataset: Milestone3Dataset, corpus: Milestone3CorpusManifest
) -> None:
    for case in dataset.cases:
        if case.workspace_id != corpus.workspace_id:
            raise DatasetContractError(f"case {case.id} Workspace does not match corpus")
        references = set(case.retrieval_relevance.acceptable_relevant_chunks) | set(
            case.evidence_expectations.acceptable_cited_chunks
        )
        unknown = references - corpus.chunks
        if unknown:
            raise DatasetContractError(
                f"case {case.id} references unknown relevant Chunk: " + ", ".join(sorted(unknown))
            )
        unknown_sources = set(case.evidence_expectations.expected_source_documents) - {
            reference.rsplit("#", 1)[0] for reference in corpus.chunks
        }
        if unknown_sources:
            raise DatasetContractError(
                f"case {case.id} references unknown source document: "
                + ", ".join(sorted(unknown_sources))
            )
        cited_sources = {
            reference.rsplit("#", 1)[0]
            for reference in case.evidence_expectations.acceptable_cited_chunks
        }
        if not cited_sources.issubset(case.evidence_expectations.expected_source_documents):
            raise DatasetContractError(
                f"case {case.id} cites a Chunk outside expected source documents"
            )
