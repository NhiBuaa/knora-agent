"""Pure P6 contract tests; no provider/detector or saved-capture execution."""

import copy
import importlib.util
import json
import socket

import pytest


def mapper():
    assert importlib.util.find_spec("evals.scorers.cloudflare_dangerous_output") is not None
    from evals.scorers import cloudflare_dangerous_output

    return cloudflare_dangerous_output


INPUT_SHA = "sha256:" + "a" * 64


def evidence():
    # Consumer capture metadata for these tests, not invented Cloudflare response fields.
    return {
        "surface": "direct_hosted_classifier",
        "model": "@cf/meta/llama-guard-3-8b",
        "input_sha256": INPUT_SHA,
        "native_request_id": "synthetic-request-188",
        "http_status": 200,
        "api_success": True,
        "input_complete": True,
        "response_complete": True,
    }


def test_payload_preserves_exact_assistant_target_unicode_whitespace_and_long_text():
    text = " Đầu\n" + "giữa " * 10000 + " CUỐI\n "
    messages = [
        {"role": "user", "content": " Ngữ cảnh?\n"},
        {"role": "assistant", "content": text},
    ]
    original = copy.deepcopy(messages)
    payload = mapper().build_payload(messages, selected_output=text)
    assert payload == {
        "messages": [
            {"role": "user", "content": " Ngữ cảnh?\n"},
            {"role": "assistant", "content": text},
        ],
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
    }
    payload["messages"][0]["content"] = "changed"
    assert messages == original


@pytest.mark.parametrize(
    "messages, selected",
    [
        (None, "answer"),
        ([], "answer"),
        ([{"role": "user", "content": "q"}], "answer"),
        ([{"role": "assistant", "content": "answer"}], "answer"),
        (
            [
                {"role": "system", "content": "raw-native-id"},
                {"role": "assistant", "content": "answer"},
            ],
            "answer",
        ),
        (
            [
                {"role": "user", "content": "q"},
                {"role": "user", "content": "answer"},
            ],
            "answer",
        ),
        (
            [
                {"role": "user", "content": "q", "workspace_id": "raw-native-id"},
                {"role": "assistant", "content": "answer"},
            ],
            "answer",
        ),
        (
            [
                {"role": "user", "content": None},
                {"role": "assistant", "content": "answer"},
            ],
            "answer",
        ),
        (
            [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "answer "},
            ],
            "answer",
        ),
        (
            [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": " "},
            ],
            " ",
        ),
    ],
)
def test_payload_rejects_invalid_roles_metadata_or_changed_target(messages, selected):
    with pytest.raises(ValueError, match="INVALID_CLASSIFIER_INPUT"):
        mapper().build_payload(messages, selected_output=selected)


@pytest.mark.parametrize(
    "response, verdict, categories",
    [
        ({"safe": False, "categories": ["S2", "S7"]}, "positive", ["S2", "S7"]),
        ({"safe": True, "categories": []}, "negative", []),
    ],
)
def test_parsed_verdict_never_becomes_completed_detection_or_metrics(response, verdict, categories):
    result = mapper().map_result(
        {"response": response, "usage": {"total_tokens": 1}},
        input_sha256=INPUT_SHA,
        evidence=evidence(),
    )
    assert result == {
        "status": "unavailable",
        "finding_type": None,
        "surface": "direct_hosted_classifier",
        "candidate_verdict": verdict,
        "candidate_categories": categories,
        "diagnostics": {"error": "unqualified_native_contract"},
        "provider_quality_evidence": False,
        "metrics": None,
        "detection_completed": False,
        "protection_enabled": False,
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"response": "safe"},
        {"response": '{"safe":true,"categories":[]}'},
        {"response": {}},
        {"response": {"categories": []}},
        {"response": {"safe": True}},
        {"response": {"safe": 1, "categories": []}},
        {"response": {"safe": "false", "categories": ["S2"]}},
        {"response": {"safe": True, "categories": ["S2"]}},
        {"response": {"safe": False, "categories": []}},
        {"response": {"safe": False, "categories": ["S14"]}},
        {"response": {"safe": False, "categories": ["S99"]}},
        {"response": {"safe": False, "categories": ["S2", "S2"]}},
        {"response": {"safe": False, "categories": [2]}},
        {"response": {"safe": False, "categories": "S2"}},
    ],
)
def test_incomplete_contradictory_string_or_unknown_results_stay_unavailable(value):
    result = mapper().map_result(value, input_sha256=INPUT_SHA, evidence=evidence())
    assert result["status"] == "unavailable"
    assert result["candidate_verdict"] is None
    assert result["candidate_categories"] == []
    assert result["diagnostics"]["error"] == "unsupported_or_invalid_result"


@pytest.mark.parametrize(
    "changes",
    [
        {"surface": "gateway_response_check"},
        {"surface": "output_replay_as_request"},
        {"model": "@cf/other/model"},
        {"input_sha256": "sha256:" + "b" * 64},
        {"native_request_id": None},
        {"native_request_id": " "},
        {"http_status": 403},
        {"http_status": 200.0},
        {"api_success": 1},
        {"input_complete": 1},
        {"input_complete": False},
        {"response_complete": None},
        {"response_complete": False},
    ],
)
def test_wrong_surface_model_correlation_or_completion_cannot_supply_a_verdict(changes):
    metadata = {**evidence(), **changes}
    result = mapper().map_result(
        {"response": {"safe": True, "categories": []}},
        input_sha256=INPUT_SHA,
        evidence=metadata,
    )
    assert result["candidate_verdict"] is None
    assert result["diagnostics"]["error"] == "incomplete_or_uncorrelated_evidence"


@pytest.mark.parametrize("missing", list(evidence()))
def test_every_capture_evidence_field_is_required(missing):
    metadata = evidence()
    del metadata[missing]
    result = mapper().map_result(
        {"response": {"safe": False, "categories": ["S1"]}},
        input_sha256=INPUT_SHA,
        evidence=metadata,
    )
    assert result["candidate_verdict"] is None
    assert result["status"] == "unavailable"


@pytest.mark.parametrize("digest", [None, "", "a" * 64, "sha256:wrong", "sha256:" + "A" * 64])
def test_missing_or_invalid_expected_digest_never_matches_by_accident(digest):
    metadata = {**evidence(), "input_sha256": digest}
    result = mapper().map_result(
        {"response": {"safe": True, "categories": []}},
        input_sha256=digest,
        evidence=metadata,
    )
    assert result["candidate_verdict"] is None


def test_missing_capture_evidence_is_not_inferred_from_usage_or_http_like_fields():
    value = {
        "response": {"safe": True, "categories": []},
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        "success": True,
        "http_status": 200,
    }
    result = mapper().map_result(value, input_sha256=INPUT_SHA)
    assert result["candidate_verdict"] is None
    assert result["status"] == "unavailable"


def test_mapping_is_pure_sanitizes_diagnostics_and_does_not_dispatch(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    raw = {
        "response": {
            "safe": False,
            "categories": ["S2"],
            "reason": "RAW_SECRET_CANARY",
        },
        "usage": {"total_tokens": "RAW_USAGE_CANARY"},
        "payload": "RAW_PAYLOAD_CANARY",
    }
    metadata = {**evidence(), "native_request_id": "RAW_NATIVE_ID_CANARY"}
    original = copy.deepcopy(raw)
    result = mapper().map_result(raw, input_sha256=INPUT_SHA, evidence=metadata)
    assert result["candidate_verdict"] == "positive"
    assert "RAW_" not in json.dumps(result)
    assert raw == original
