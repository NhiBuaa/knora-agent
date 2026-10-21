"""Scale diagnostic dataset loader and validator for ANN and quantization benchmarking."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


class ScaleDatasetContractError(ValueError):
    """Raised when scale dataset violates schema or validation invariants."""

    pass


@dataclass(frozen=True, slots=True)
class ScalePoint:
    point_id: str
    workspace_id: str
    document_version_id: str
    vector: tuple[float, ...]
    is_tenant: bool


@dataclass(frozen=True, slots=True)
class ScaleQuery:
    query_id: str
    workspace_id: str
    vector: tuple[float, ...]
    exact_top200: tuple[str, ...]
    exact_top200_scores: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DenseSearchScaleDataset:
    schema_version: int
    version: str
    dimensions: int
    metric: str
    total_population: int
    eligible_population: int
    decoy_population: int
    dataset_sha256: str
    points: tuple[ScalePoint, ...]
    points_by_id: dict[str, ScalePoint]
    queries: tuple[ScaleQuery, ...]
    diagnostic_policy: dict[str, object]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScaleDatasetContractError(message)


def _text(value: object, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"invalid {field}")
    return value


def _sha(value: object, field: str) -> str:
    _require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        f"invalid {field}",
    )
    return value


def load_dense_scale_dataset(manifest_path: Path, dataset_path: Path) -> DenseSearchScaleDataset:
    """Load and validate the dense search scale diagnostic dataset."""
    try:
        manifest_raw = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_raw)
        _require(isinstance(manifest, dict), "manifest must be an object")
        _require(manifest.get("schema_version") == 1, "unsupported schema_version")

        dimensions = manifest.get("dimensions")
        _require(type(dimensions) is int and dimensions > 0, "invalid dimensions")

        metric = _text(manifest.get("metric"), "metric")
        _require(metric in ("Cosine", "Dot", "Euclidean"), f"unsupported metric {metric}")

        raw_bytes = dataset_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = _sha(manifest.get("dataset_sha256"), "dataset_sha256")
        _require(actual_sha == expected_sha, "dataset_sha256 drift")

        points = []
        points_by_id = {}
        tenant_ids = set()

        for line_num, line in enumerate(raw_bytes.decode("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            rec = json.loads(line)
            _require(isinstance(rec, dict), f"point at line {line_num} must be an object")

            pid = _text(rec.get("point_id"), f"point_id at line {line_num}")
            _require(pid not in points_by_id, f"duplicate point_id: {pid}")

            vec_raw = rec.get("vector")
            _require(
                isinstance(vec_raw, list) and len(vec_raw) == dimensions,
                f"point {pid} vector must have exactly {dimensions} dimensions",
            )
            vec = tuple(float(x) for x in vec_raw)

            pt = ScalePoint(
                point_id=pid,
                workspace_id=_text(rec.get("workspace_id"), "workspace_id"),
                document_version_id=_text(rec.get("document_version_id"), "document_version_id"),
                vector=vec,
                is_tenant=bool(rec.get("is_tenant", True)),
            )
            points.append(pt)
            points_by_id[pid] = pt
            tenant_ids.add(pt.workspace_id)

        queries_raw = manifest.get("queries")
        _require(isinstance(queries_raw, list) and bool(queries_raw), "queries missing")

        # Invariant: ANN Recall@200 claims require eligible population > 200
        first_q_tenant = _text(queries_raw[0].get("workspace_id"), "workspace_id")
        eligible_count = sum(1 for p in points if p.workspace_id == first_q_tenant)
        policy = manifest.get("diagnostic_policy", {})
        min_pop = policy.get("min_eligible_population_for_ann", 201)
        _require(
            eligible_count >= min_pop,
            (
                f"eligible population ({eligible_count}) must be >= {min_pop} "
                "for ANN Recall@200 claims"
            ),
        )

        queries = []

        for q_row in queries_raw:
            qid = _text(q_row.get("query_id"), "query_id")
            q_tenant = _text(q_row.get("workspace_id"), "workspace_id")
            _require(q_tenant in tenant_ids, f"query {qid} tenant {q_tenant} not in points")

            q_vec_raw = q_row.get("vector")
            _require(
                isinstance(q_vec_raw, list) and len(q_vec_raw) == dimensions,
                f"query {qid} vector must have {dimensions} dimensions",
            )
            q_vec = tuple(float(x) for x in q_vec_raw)

            top200 = tuple(_text(p, "exact_top200") for p in q_row.get("exact_top200", []))
            _require(len(top200) == 200, f"query {qid} exact_top200 must have 200 items")
            _require(len(set(top200)) == 200, f"query {qid} exact_top200 contains duplicates")

            # Validate that every neighbor in exact_top200 belongs to the query tenant
            for p_id in top200:
                _require(p_id in points_by_id, f"query {qid} neighbor {p_id} not in points")
                _require(
                    points_by_id[p_id].workspace_id == q_tenant,
                    f"query {qid} neighbor {p_id} belongs to foreign tenant",
                )

            scores = tuple(float(s) for s in q_row.get("exact_top200_scores", []))
            _require(len(scores) == 200, f"query {qid} exact_top200_scores must have 200 items")

            queries.append(
                ScaleQuery(
                    query_id=qid,
                    workspace_id=q_tenant,
                    vector=q_vec,
                    exact_top200=top200,
                    exact_top200_scores=scores,
                )
            )

        return DenseSearchScaleDataset(
            schema_version=1,
            version=manifest.get("version", "dense-search-scale-v1"),
            dimensions=dimensions,
            metric=metric,
            total_population=len(points),
            eligible_population=eligible_count,
            decoy_population=len(points) - eligible_count,
            dataset_sha256=actual_sha,
            points=tuple(points),
            points_by_id=points_by_id,
            queries=tuple(queries),
            diagnostic_policy=policy,
        )
    except (KeyError, TypeError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise ScaleDatasetContractError(f"invalid scale dataset: {exc}") from exc


def validate_scale_approval(dataset: DenseSearchScaleDataset, approval: dict[str, object]) -> None:
    """Validate that the dense scale dataset has authoritative owner approval."""
    _require(
        isinstance(approval, dict)
        and approval.get("status") == "approved"
        and approval.get("owner") == "NhiBuaa"
        and approval.get("dataset_sha256") == dataset.dataset_sha256,
        "owner scale approval missing or approval digest drift",
    )
