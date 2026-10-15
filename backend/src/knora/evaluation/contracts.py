"""Portable, immutable evaluation gold and references for the PDF workbench."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")


def _digest(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _tuple(value: tuple[Any, ...], name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be an immutable tuple")


def _array(value: Any, name: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be an array")
    return tuple(value)


def _unique(values: tuple[str, ...], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {name}")


def _object(value: Any, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.keys() != fields:
        raise ValueError(f"expected JSON object fields {sorted(fields)}")
    return value


def _read_json(value: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = item
        return result

    return json.loads(value, object_pairs_hook=pairs)


def canonical_json(value: Any) -> str:
    """Serialize JSON data with stable UTF-8-compatible canonical spelling."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DatasetIdentity:
    dataset_id: str
    version: int
    workspace_id: str
    format: str
    metric_contract: str

    def __post_init__(self) -> None:
        for name in ("dataset_id", "workspace_id", "metric_contract"):
            _nonempty(getattr(self, name), name)
        if type(self.version) is not int or self.version < 1:
            raise ValueError("version must be a positive integer")
        if self.format != "pdf-gold-v1":
            raise ValueError("unsupported gold format")

    @classmethod
    def from_dict(cls, value: Any) -> DatasetIdentity:
        return cls(**_object(value, set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class PdfSource:
    document_id: str
    document_version_id: str
    raw_sha256: str

    def __post_init__(self) -> None:
        _nonempty(self.document_id, "document_id")
        _nonempty(self.document_version_id, "document_version_id")
        _digest(self.raw_sha256, "raw_sha256")

    @classmethod
    def from_dict(cls, value: Any) -> PdfSource:
        return cls(**_object(value, set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class EvidenceAnchor:
    document_version_id: str
    physical_page: int
    quote: str
    extraction_snapshot_id: str | None = None
    extraction_sha256: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        _nonempty(self.document_version_id, "document_version_id")
        _nonempty(self.quote, "quote")
        if type(self.physical_page) is not int or self.physical_page < 1:
            raise ValueError("physical_page must be one-based")
        snapshot = self.extraction_snapshot_id is not None
        checksum = self.extraction_sha256 is not None
        offsets = self.start_offset is not None or self.end_offset is not None
        if snapshot != checksum or (offsets and not snapshot):
            raise ValueError("offsets require an extraction snapshot and checksum")
        if snapshot:
            _nonempty(self.extraction_snapshot_id, "extraction_snapshot_id")
            _digest(self.extraction_sha256, "extraction_sha256")
        if offsets and (
            type(self.start_offset) is not int
            or type(self.end_offset) is not int
            or self.start_offset < 0
            or self.end_offset <= self.start_offset
        ):
            raise ValueError("offsets must be a nonempty half-open range")

    @classmethod
    def from_dict(cls, value: Any) -> EvidenceAnchor:
        return cls(**_object(value, set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class EvidenceGroup:
    alternatives: tuple[EvidenceAnchor, ...]

    def __post_init__(self) -> None:
        _tuple(self.alternatives, "alternatives")
        if not self.alternatives or not all(
            isinstance(a, EvidenceAnchor) for a in self.alternatives
        ):
            raise ValueError("evidence group needs anchor alternatives")
        if len(self.alternatives) != len(set(self.alternatives)):
            raise ValueError("duplicate evidence alternatives")

    @classmethod
    def from_dict(cls, value: Any) -> EvidenceGroup:
        data = _object(value, {"alternatives"})
        return cls(
            tuple(EvidenceAnchor.from_dict(a) for a in _array(data["alternatives"], "alternatives"))
        )


@dataclass(frozen=True)
class NoAnswerScope:
    checked_document_version_ids: tuple[str, ...]
    verification_note: str

    def __post_init__(self) -> None:
        _tuple(self.checked_document_version_ids, "checked_document_version_ids")
        if not self.checked_document_version_ids:
            raise ValueError("no-answer scope needs checked source versions")
        for source_id in self.checked_document_version_ids:
            _nonempty(source_id, "checked_document_version_id")
        _unique(self.checked_document_version_ids, "checked source version")
        _nonempty(self.verification_note, "verification_note")

    @classmethod
    def from_dict(cls, value: Any) -> NoAnswerScope:
        data = _object(value, set(cls.__dataclass_fields__))
        return cls(
            _array(data["checked_document_version_ids"], "checked_document_version_ids"),
            data["verification_note"],
        )


@dataclass(frozen=True)
class Case:
    case_id: str
    question: str
    expected: Literal["ANSWER", "REFUSAL"]
    reference_answer: str | None
    required_facts: tuple[str, ...]
    language: str
    category: str
    evidence_groups: tuple[EvidenceGroup, ...]
    context_dependencies: tuple[str, ...] = ()
    no_answer_scope: NoAnswerScope | None = None

    def __post_init__(self) -> None:
        for name in ("case_id", "question", "language", "category"):
            _nonempty(getattr(self, name), name)
        for name in ("required_facts", "evidence_groups", "context_dependencies"):
            _tuple(getattr(self, name), name)
        for dependency in self.context_dependencies:
            _nonempty(dependency, "context dependency")
        _unique(self.context_dependencies, "context dependency")
        if self.expected == "ANSWER":
            _nonempty(self.reference_answer, "reference_answer")
            if not self.required_facts or not all(
                isinstance(fact, str) and fact.strip() for fact in self.required_facts
            ):
                raise ValueError("ANSWER needs required facts")
            if not self.evidence_groups or not all(
                isinstance(group, EvidenceGroup) for group in self.evidence_groups
            ):
                raise ValueError("ANSWER needs required evidence groups")
            if self.no_answer_scope is not None:
                raise ValueError("ANSWER cannot have no-answer scope")
        elif self.expected == "REFUSAL":
            if self.reference_answer is not None or self.required_facts or self.evidence_groups:
                raise ValueError("REFUSAL cannot have answer gold or evidence")
            if not isinstance(self.no_answer_scope, NoAnswerScope):
                raise ValueError("REFUSAL needs no-answer scope")
        else:
            raise ValueError("unsupported expected result")

    @classmethod
    def from_dict(cls, value: Any) -> Case:
        data = _object(value, set(cls.__dataclass_fields__))
        return cls(
            case_id=data["case_id"],
            question=data["question"],
            expected=data["expected"],
            reference_answer=data["reference_answer"],
            required_facts=_array(data["required_facts"], "required_facts"),
            language=data["language"],
            category=data["category"],
            evidence_groups=tuple(
                EvidenceGroup.from_dict(g)
                for g in _array(data["evidence_groups"], "evidence_groups")
            ),
            context_dependencies=_array(data["context_dependencies"], "context_dependencies"),
            no_answer_scope=(
                NoAnswerScope.from_dict(data["no_answer_scope"])
                if data["no_answer_scope"] is not None
                else None
            ),
        )


@dataclass(frozen=True)
class GoldDataset:
    identity: DatasetIdentity
    sources: tuple[PdfSource, ...]
    cases: tuple[Case, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, DatasetIdentity):
            raise ValueError("dataset needs typed identity")
        _tuple(self.sources, "sources")
        _tuple(self.cases, "cases")
        if not self.sources or not self.cases:
            raise ValueError("dataset needs sources and cases")
        if not all(isinstance(source, PdfSource) for source in self.sources):
            raise ValueError("dataset needs PDF sources")
        if not all(isinstance(case, Case) for case in self.cases):
            raise ValueError("dataset needs typed cases")
        versions = tuple(source.document_version_id for source in self.sources)
        _unique(versions, "document version ID")
        ids = tuple(case.case_id for case in self.cases)
        _unique(ids, "case ID")
        case_by_id = {case.case_id: case for case in self.cases}
        for case in self.cases:
            for group in case.evidence_groups:
                for anchor in group.alternatives:
                    if anchor.document_version_id not in versions:
                        raise ValueError("evidence references unknown document version")
            if case.no_answer_scope and any(
                version not in versions
                for version in case.no_answer_scope.checked_document_version_ids
            ):
                raise ValueError("no-answer scope references unknown document version")
            if any(dependency not in case_by_id for dependency in case.context_dependencies):
                raise ValueError("context dependency references unknown case")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(case_id: str) -> None:
            if case_id in visiting:
                raise ValueError("cyclic context dependencies")
            if case_id in visited:
                return
            visiting.add(case_id)
            for dependency in case_by_id[case_id].context_dependencies:
                visit(dependency)
            visiting.remove(case_id)
            visited.add(case_id)

        for case_id in ids:
            visit(case_id)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return asdict(self)

    @property
    def digest(self) -> str:
        return digest_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> GoldDataset:
        data = _object(value, {"identity", "sources", "cases"})
        return cls(
            DatasetIdentity.from_dict(data["identity"]),
            tuple(PdfSource.from_dict(source) for source in _array(data["sources"], "sources")),
            tuple(Case.from_dict(case) for case in _array(data["cases"], "cases")),
        )


@dataclass(frozen=True)
class DatasetReference:
    dataset_id: str
    version: int
    workspace_id: str
    format: str
    metric_contract: str
    digest: str

    def __post_init__(self) -> None:
        DatasetIdentity(
            self.dataset_id, self.version, self.workspace_id, self.format, self.metric_contract
        )
        _digest(self.digest, "digest")

    @classmethod
    def from_dict(cls, value: Any) -> DatasetReference:
        return cls(**_object(value, set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class LegacyDatasetReference:
    format: str
    dataset_id: str
    version: int
    workspace_id: str
    native_digest: str
    metric_contract: str

    def __post_init__(self) -> None:
        if self.format == "pdf-gold-v1":
            raise ValueError("PDF gold uses DatasetReference")
        for name in ("format", "dataset_id", "workspace_id", "native_digest", "metric_contract"):
            _nonempty(getattr(self, name), name)
        if type(self.version) is not int or self.version < 1:
            raise ValueError("version must be a positive integer")


@dataclass(frozen=True)
class FreezeApproval:
    owner_issuer: str
    owner_subject: str
    gold_digest: str

    def __post_init__(self) -> None:
        _nonempty(self.owner_issuer, "owner_issuer")
        _nonempty(self.owner_subject, "owner_subject")
        _digest(self.gold_digest, "gold_digest")

    @classmethod
    def from_dict(cls, value: Any) -> FreezeApproval:
        return cls(**_object(value, set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class FrozenDataset:
    gold: GoldDataset
    reference: DatasetReference
    approval: FreezeApproval

    def __post_init__(self) -> None:
        if (
            not isinstance(self.gold, GoldDataset)
            or not isinstance(self.reference, DatasetReference)
            or not isinstance(self.approval, FreezeApproval)
        ):
            raise ValueError("frozen dataset needs typed gold, reference and approval")
        if self.reference != DatasetReference(
            **asdict(self.gold.identity), digest=self.gold.digest
        ):
            raise ValueError("frozen dataset reference digest or identity mismatch")
        if self.approval.gold_digest != self.gold.digest:
            raise ValueError("freeze approval digest mismatch")

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(asdict(self))

    @classmethod
    def from_json(cls, value: str) -> FrozenDataset:
        data = _object(_read_json(value), {"gold", "reference", "approval"})
        return cls(
            GoldDataset.from_dict(data["gold"]),
            DatasetReference.from_dict(data["reference"]),
            FreezeApproval.from_dict(data["approval"]),
        )


def freeze_dataset(gold: GoldDataset, approval: FreezeApproval) -> FrozenDataset:
    if not isinstance(gold, GoldDataset) or not isinstance(approval, FreezeApproval):
        raise ValueError("freeze requires typed gold and approval")
    reference = DatasetReference(**asdict(gold.identity), digest=gold.digest)
    return FrozenDataset(gold, reference, approval)


@dataclass(frozen=True)
class DatasetSelection:
    reference: DatasetReference
    selected_case_ids: tuple[str, ...]
    context_only_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.reference, DatasetReference):
            raise ValueError("selection needs a dataset reference")
        _tuple(self.selected_case_ids, "selected_case_ids")
        _tuple(self.context_only_case_ids, "context_only_case_ids")
        if not self.selected_case_ids:
            raise ValueError("selection needs cases")
        _unique(self.selected_case_ids, "selected case ID")
        _unique(self.context_only_case_ids, "context-only case ID")
        if set(self.selected_case_ids) & set(self.context_only_case_ids):
            raise ValueError("selected cases cannot also be context-only")

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(asdict(self))

    @classmethod
    def from_json(cls, value: str, frozen: FrozenDataset) -> DatasetSelection:
        data = _object(
            _read_json(value), {"reference", "selected_case_ids", "context_only_case_ids"}
        )
        selection = cls(
            DatasetReference.from_dict(data["reference"]),
            _array(data["selected_case_ids"], "selected_case_ids"),
            _array(data["context_only_case_ids"], "context_only_case_ids"),
        )
        expected = select_cases(frozen, selection.selected_case_ids)
        if selection != expected:
            raise ValueError("selection dataset digest or context-only cases mismatch")
        return selection


def select_cases(frozen: FrozenDataset, case_ids: tuple[str, ...]) -> DatasetSelection:
    frozen.__post_init__()
    _tuple(case_ids, "case_ids")
    _unique(case_ids, "selected case ID")
    by_id = {case.case_id: case for case in frozen.gold.cases}
    if any(case_id not in by_id for case_id in case_ids):
        raise ValueError("selection references unknown case")
    selected = set(case_ids)
    context: list[str] = []
    visited: set[str] = set()

    def add_dependencies(case_id: str) -> None:
        if case_id in visited:
            return
        visited.add(case_id)
        for dependency in by_id[case_id].context_dependencies:
            add_dependencies(dependency)
            if dependency not in selected and dependency not in context:
                context.append(dependency)

    for case_id in case_ids:
        add_dependencies(case_id)
    return DatasetSelection(frozen.reference, case_ids, tuple(context))


@dataclass(frozen=True)
class RuntimeBinding:
    reference: DatasetReference
    status: Literal["MISSING", "PARTIAL", "READY", "AMBIGUOUS"]
    binding_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reference, DatasetReference):
            raise ValueError("binding needs a dataset reference")
        if self.status not in ("MISSING", "PARTIAL", "READY", "AMBIGUOUS"):
            raise ValueError("invalid binding status")
        if self.binding_id is not None:
            _nonempty(self.binding_id, "binding_id")
        if self.status == "READY" and self.binding_id is None:
            raise ValueError("ready binding needs a binding ID")
