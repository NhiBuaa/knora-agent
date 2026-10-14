"""Strict, source-bound review candidate; loading never approves authored gold."""

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DatasetContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PdfSource:
    id: str
    path: Path
    sha256: str
    page_count: int
    category: str
    kind: str
    license: str
    source_url: str
    license_url: str


@dataclass(frozen=True, slots=True)
class SourceAnchor:
    id: str
    source_id: str
    page: int
    text: str
    region: str


@dataclass(frozen=True, slots=True)
class PdfCase:
    id: str
    category: str
    language: str
    question: str
    expected_behavior: str
    reference_answer: str
    required_facts: tuple[str, ...]
    evidence_groups: tuple[tuple[str, ...], ...]
    parent_case_id: str | None = None
    no_answer_scope: str | None = None


@dataclass(frozen=True, slots=True)
class PdfDataset:
    sources: tuple[PdfSource, ...]
    anchors: tuple[SourceAnchor, ...]
    cases: tuple[PdfCase, ...]
    corpus_sha256: str
    dataset_sha256: str


SOURCE_COUNTS = {
    "clean": 2,
    "hierarchy": 3,
    "multi_column": 2,
    "hard_table": 3,
    "scan_mixed": 3,
    "academic": 3,
}
CASE_COUNTS = {
    "simple": 8,
    "comparison": 10,
    "table_hierarchy": 10,
    "follow_up": 8,
    "typo_identifier": 10,
    "multi_hop": 6,
    "no_answer": 8,
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DatasetContractError(message)


def _text(value: object, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"invalid {field}")
    return value


def _strings(value: object, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"invalid {field}")
    return tuple(_text(item, field) for item in value)


def _records(value: object, field: str) -> list[dict]:
    _require(isinstance(value, list) and bool(value), f"invalid {field}")
    _require(all(isinstance(row, dict) for row in value), f"invalid {field}")
    ids = [_text(row.get("id"), f"{field} id") for row in value]
    _require(len(ids) == len(set(ids)), f"duplicate {field} id")
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_dataset(manifest_path: Path, dataset_path: Path) -> PdfDataset:
    """Check source files, gold closure and fixed scope before exposing the candidate."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _require(isinstance(manifest, dict), "manifest must be an object")
        _require(manifest.get("schema_version") == 1, "unsupported schema_version")
        _require(
            manifest.get("corpus_digest_scheme") == "canonical-sources-and-anchors-json-sha256-v1",
            "unsupported corpus digest scheme",
        )
        raw = dataset_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        dataset_sha = hashlib.sha256(raw).hexdigest()
        _require(manifest.get("dataset_sha256") == dataset_sha, "dataset_sha256 mismatch")
        source_rows = _records(manifest.get("sources"), "source")
        anchor_rows = _records(manifest.get("anchors"), "anchor")
        case_rows = _records(
            [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()],
            "case",
        )
        root = manifest_path.resolve().parents[1]
        sources = []
        paths = set()
        for row in source_rows:
            relative = PurePosixPath(_text(row.get("path"), "source path"))
            _require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and "\\" not in str(relative)
                and ":" not in str(relative),
                "unsafe source path",
            )
            path = (root / str(relative)).resolve()
            _require(path.is_relative_to(root) and path.suffix == ".pdf", "unsafe source path")
            _require(path not in paths, "duplicate source path")
            paths.add(path)
            sha = _text(row.get("sha256"), "source sha256")
            _require(re.fullmatch(r"[0-9a-f]{64}", sha) is not None, "invalid source sha256")
            _require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, "source sha256 drift")
            pages = row.get("page_count")
            _require(type(pages) is int and pages > 0, "invalid source page_count")
            _require(len(PdfReader(path).pages) == pages, "source page_count mismatch")
            category = _text(row.get("category"), "source category")
            kind = row.get("kind")
            _require(kind == ("real" if category == "academic" else "synthetic"), "source kind")
            _require(row.get("license") == "CC-BY-4.0", "source license")
            urls = [_text(row.get(field), field) for field in ("source_url", "license_url")]
            _require(all(url.startswith("https://") for url in urls), "invalid source license URL")
            sources.append(
                PdfSource(row["id"], path, sha, pages, category, kind, row["license"], *urls)
            )
        _require(Counter(s.category for s in sources) == SOURCE_COUNTS, "source distribution")
        by_source = {source.id: source for source in sources}
        anchors = []
        for row in anchor_rows:
            source_id = row.get("source_id")
            _require(source_id in by_source, "unknown anchor source")
            page = row.get("page")
            _require(
                type(page) is int and 1 <= page <= by_source[source_id].page_count, "anchor page"
            )
            anchors.append(
                SourceAnchor(
                    row["id"],
                    source_id,
                    page,
                    _text(row.get("text"), "anchor text"),
                    _text(row.get("region"), "anchor region"),
                )
            )
        by_anchor = {anchor.id: anchor for anchor in anchors}
        _require({a.source_id for a in anchors} == set(by_source), "anchor source closure")
        cases = []
        seen = set()
        used = set()
        for row in case_rows:
            case_id = row["id"]
            category = _text(row.get("category"), "case category")
            language = row.get("language")
            _require(language in ("vi", "en", "mixed"), "case language")
            question = _text(row.get("question"), "question")
            behavior = row.get("expected_behavior")
            _require(behavior in ("ANSWER", "REFUSAL"), "expected_behavior")
            reference = _text(row.get("reference_answer"), "reference_answer")
            facts = _strings(row.get("required_facts"), "required_facts")
            groups = row.get("evidence_groups")
            _require(isinstance(groups, list), "invalid evidence group")
            groups = tuple(_strings(group, "evidence group") for group in groups)
            parent = row.get("parent_case_id")
            if parent is not None:
                _require(
                    parent in seen and category == "follow_up",
                    "parent must exist and precede follow_up",
                )
            _require(category != "follow_up" or parent is not None, "follow_up parent missing")
            scope = row.get("no_answer_scope")
            if behavior == "REFUSAL":
                _require(
                    not facts and not groups and category == "no_answer",
                    "REFUSAL must have no positive gold",
                )
                _text(scope, "no_answer_scope")
            else:
                _require(category != "no_answer" and scope is None, "ANSWER no_answer_scope")
                _require(
                    bool(facts) and bool(groups) and all(groups),
                    "ANSWER facts and nonempty AND group required",
                )
                _require(
                    all(a in by_anchor for group in groups for a in group),
                    "unknown evidence anchor",
                )
                if category == "multi_hop":
                    source_options = [{by_anchor[a].source_id for a in group} for group in groups]
                    _require(
                        len(groups) >= 2 and not set.intersection(*source_options),
                        "multi_hop source steps",
                    )
                used.update(a for group in groups for a in group)
            cases.append(
                PdfCase(
                    case_id,
                    category,
                    language,
                    question,
                    behavior,
                    reference,
                    facts,
                    groups,
                    parent,
                    scope,
                )
            )
            seen.add(case_id)
        _require(Counter(c.category for c in cases) == CASE_COUNTS, "case distribution")
        _require(len({c.question for c in cases}) == len(cases), "duplicate question")
        _require(used == set(by_anchor), "unused anchor source closure")
        corpus_sha = _digest({"sources": source_rows, "anchors": anchor_rows})
        _require(manifest.get("corpus_sha256") == corpus_sha, "corpus_sha256 drift")
        return PdfDataset(tuple(sources), tuple(anchors), tuple(cases), corpus_sha, dataset_sha)
    except PdfReadError as exc:
        raise DatasetContractError(f"invalid source PDF: {exc}") from exc
    except (KeyError, TypeError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise DatasetContractError(f"invalid dataset: {exc}") from exc


def validate_approval(dataset: PdfDataset, approval: dict) -> None:
    _require(
        isinstance(approval, dict)
        and approval.get("status") == "approved"
        and approval.get("owner") == "NhiBuaa"
        and approval.get("corpus_sha256") == dataset.corpus_sha256
        and approval.get("dataset_sha256") == dataset.dataset_sha256,
        "owner approval missing or approval digest drift",
    )
