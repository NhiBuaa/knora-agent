"""Definition identity must describe the actual static inputs sent to a provider."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from knora.providers.generation import GenerationEvidence

BASELINE = json.loads(
    (Path(__file__).parent / "fixtures/prompt-baseline-c775a83.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", BASELINE["cases"], ids=lambda case: case["name"])
def test_definition_builds_baseline_messages_schema_and_identity(case: dict) -> None:
    from knora.providers.prompts.builder import build_prompt

    name = case["name"]
    profile = "ollama" if name.startswith("ollama") else name
    if name.startswith("cloudflare-answer-"):
        profile = "cloudflare-answer"
    prompt = build_prompt(
        profile,
        question=BASELINE["question"],
        evidence=tuple(GenerationEvidence(**entry) for entry in BASELINE["evidence"]),
        model=case.get("model", ""),
        presentation=case.get("presentation"),
    )
    assert prompt.messages == case["messages"]
    assert prompt.definition.schema == case["schema"]
    assert prompt.definition.version == case["version"]
    serializer = (
        "ollama-evidence-current-question-v1" if profile == "ollama" else "question-evidence-v1"
    )
    static = {
        "version": case["version"],
        "system_prompt": case["messages"][0]["content"],
        "schema": case["schema"],
        "serializer_id": serializer,
    }
    expected = hashlib.sha256(
        json.dumps(static, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    assert prompt.definition.fingerprint == expected
    changed_input = build_prompt(
        profile,
        question="Different dynamic question",
        evidence=(),
        model=case.get("model", ""),
        presentation=case.get("presentation"),
    )
    assert changed_input.definition.fingerprint == expected
    assert changed_input.messages != prompt.messages


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "changed"),
        ("system_prompt", "changed"),
        ("schema", {"type": "null"}),
        ("serializer_id", "changed"),
    ],
)
def test_static_definition_drift_changes_fingerprint(field: str, value: object) -> None:
    from knora.providers.prompts.builder import build_prompt

    definition = build_prompt("generic", question="Question", evidence=()).definition
    assert replace(definition, **{field: value}).fingerprint != definition.fingerprint


def test_schema_key_order_does_not_change_definition_identity() -> None:
    from knora.providers.prompts.builder import build_prompt

    definition = build_prompt("generic", question="Question", evidence=()).definition
    assert (
        replace(definition, schema=dict(reversed(list(definition.schema.items())))).fingerprint
        == definition.fingerprint
    )
