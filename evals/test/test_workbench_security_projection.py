import hashlib
import json

import pytest
from evals.runners.workbench_security_projection import project_saved_observations


def project(value):
    raw = json.dumps(value, ensure_ascii=False).encode()
    return project_saved_observations(raw, expected_sha256=hashlib.sha256(raw).hexdigest())


def record():
    return {
        "case_id": "c",
        "run_id": "r",
        "workspace_id": "w",
        "attempt_id": "a",
        "trace_id": "t",
        "status": "OBSERVED",
        "decision": "ANSWER",
        "public_answer": "Giờ 09:00 [[E1]]",
        "generation_evidence_status": "exact",
        "generation_evidence": [["E1", " Giờ 09:00\n"], ["E2", "uncited"]],
    }


def test_pairs_preserve_order_bytes_and_native_identity_without_mutation():
    source = record()
    rows = project({"execution_status": "COMPLETED", "observations": {"c": source}})
    assert rows[0]["generation_evidence"] == [
        {"alias": "E1", "content": " Giờ 09:00\n"},
        {"alias": "E2", "content": "uncited"},
    ]
    assert rows[0]["trace_id"] == "t"
    assert len(rows[0]["source_artifact_sha256"]) == 64
    assert isinstance(source["generation_evidence"][0], list)


def test_hash_checked_before_json_parse():
    with pytest.raises(ValueError, match="DIGEST"):
        project_saved_observations(b"not JSON", expected_sha256="0" * 64)


@pytest.mark.parametrize("field", ["trace_id", "attempt_id", "workspace_id", "run_id"])
def test_missing_native_binding_is_unavailable(field):
    source = record()
    del source[field]
    row = project({"execution_status": "COMPLETED", "observations": {"c": source}})[0]
    assert row["generation_evidence_status"] == "unavailable"
    assert row["output_status"] == "unavailable"
    assert row[field] is None


@pytest.mark.parametrize(
    "decision,status", [("REFUSAL", "OBSERVED"), (None, "FAILED"), (None, "NOT_RUN")]
)
def test_refusal_error_and_missing_populations_retained(decision, status):
    source = record() | {
        "decision": decision,
        "status": status,
        "public_answer": None,
        "generation_evidence_status": "unavailable",
        "generation_evidence": [],
    }
    row = project({"execution_status": "COMPLETED", "observations": {"c": source}})[0]
    assert row["decision"] == decision
    assert row["status"] == status
    assert row["output_status"] == "unavailable"


@pytest.mark.parametrize(
    "evidence",
    [[["E1", "a"], ["E1", "b"]], [["E2", "a"]], [{"alias": "E1", "content": "a"}], [["E1", None]]],
)
def test_unsupported_or_duplicate_evidence_rejected(evidence):
    with pytest.raises(ValueError):
        project(
            {
                "execution_status": "COMPLETED",
                "observations": {"c": record() | {"generation_evidence": evidence}},
            }
        )


def test_identity_conflict_and_unsupported_shape_rejected():
    with pytest.raises(ValueError):
        project(
            {"execution_status": "COMPLETED", "run_id": "other", "observations": {"c": record()}}
        )
    with pytest.raises(ValueError):
        project({"observations": [record()]})


def test_synthetic_fully_bound_shape_retains_not_run():
    source = record()
    for key in ("workspace_id", "run_id", "attempt_id", "generation_evidence_status"):
        del source[key]
    rows = project(
        {
            "execution_status": "COMPLETED",
            "workspace_id": "w",
            "run_id": "r",
            "attempt_id": "a",
            "observations": {"c": source, "pending": {"status": "NOT_RUN"}},
        }
    )
    assert rows[0]["generation_evidence_status"] == "exact"
    assert rows[1]["case_id"] == "pending"
    assert rows[1]["trace_id"] is None
    assert rows[1]["output_status"] == "unavailable"


def test_actual_pinned_read_run_lacks_attempt_and_stays_unavailable():
    source = record()
    for key in ("workspace_id", "run_id", "attempt_id", "generation_evidence_status"):
        del source[key]
    rows = project(
        {
            "execution_status": "COMPLETED",
            "workspace_id": "w",
            "run_id": "r",
            "observations": {"c": source},
        }
    )
    assert rows[0]["attempt_id"] is None
    assert rows[0]["generation_evidence_status"] == "unavailable"
    assert rows[0]["output_status"] == "unavailable"


def test_map_case_identity_conflict_rejected():
    with pytest.raises(ValueError, match="IDENTITY_CONFLICT"):
        project({"execution_status": "COMPLETED", "observations": {"other": record()}})
