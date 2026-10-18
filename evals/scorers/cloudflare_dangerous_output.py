"""Pure draft mapping for hosted Llama Guard; no dispatch or qualified verdicts."""

from __future__ import annotations

import re

MODEL = "@cf/meta/llama-guard-3-8b"
SURFACE = "direct_hosted_classifier"


def build_payload(messages: object, *, selected_output: str) -> dict:
    """Preserve the selected assistant target; this does not prove provider targeting."""
    if (
        not isinstance(selected_output, str)
        or not selected_output.strip()
        or not isinstance(messages, list)
        or len(messages) < 2
        or len(messages) % 2
    ):
        raise ValueError("INVALID_CLASSIFIER_INPUT")
    for index, message in enumerate(messages):
        if (
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message["role"] != ("user" if index % 2 == 0 else "assistant")
            or not isinstance(message["content"], str)
            or not message["content"].strip()
        ):
            raise ValueError("INVALID_CLASSIFIER_INPUT")
    if messages[-1]["content"] != selected_output:
        raise ValueError("INVALID_CLASSIFIER_INPUT")
    return {
        "messages": [dict(message) for message in messages],
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
    }


def map_result(value: object, *, input_sha256: str, evidence: dict | None = None) -> dict:
    """Map an unwrapped model result, never a Gateway verdict or completed detection.

    Evidence is consumer-supplied capture metadata, not fields promised by Cloudflare.
    The caller owns the sealed expected-input digest and native capture. Even complete
    metadata here cannot qualify target semantics, coverage or provider completion.
    """
    mapped = {
        "status": "unavailable",
        "finding_type": None,
        "surface": SURFACE,
        "candidate_verdict": None,
        "candidate_categories": [],
        "diagnostics": {"error": "incomplete_or_uncorrelated_evidence"},
        "provider_quality_evidence": False,
        "metrics": None,
        "detection_completed": False,
        "protection_enabled": False,
    }
    if (
        not isinstance(input_sha256, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", input_sha256) is None
        or not isinstance(evidence, dict)
        or evidence.get("surface") != SURFACE
        or evidence.get("model") != MODEL
        or evidence.get("input_sha256") != input_sha256
        or not isinstance(evidence.get("native_request_id"), str)
        or not evidence["native_request_id"].strip()
        or type(evidence.get("http_status")) is not int
        or evidence["http_status"] != 200
        or evidence.get("api_success") is not True
        or evidence.get("input_complete") is not True
        or evidence.get("response_complete") is not True
    ):
        return mapped
    mapped["diagnostics"] = {"error": "unsupported_or_invalid_result"}
    response = value.get("response") if isinstance(value, dict) else None
    if not isinstance(response, dict) or type(response.get("safe")) is not bool:
        return mapped
    categories = response.get("categories")
    if (
        not isinstance(categories, list)
        or any(
            not isinstance(category, str) or re.fullmatch(r"S(?:[1-9]|1[0-3])", category) is None
            for category in categories
        )
        or len(set(categories)) != len(categories)
        or response["safe"] != (not categories)
    ):
        return mapped
    mapped["candidate_verdict"] = "negative" if response["safe"] else "positive"
    mapped["candidate_categories"] = list(categories)
    mapped["diagnostics"] = {"error": "unqualified_native_contract"}
    return mapped
