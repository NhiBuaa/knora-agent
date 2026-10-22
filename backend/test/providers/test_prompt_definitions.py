"""Definition identity must describe the actual static inputs sent to a provider."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from knora.providers.generation import GenerationEvidence

BASELINE = json.loads(
    (Path(__file__).parent / "fixtures/accepted-main-prompt-baseline.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", BASELINE["cases"], ids=lambda case: case["name"])
def test_definition_builds_baseline_messages_schema_and_identity(case: dict) -> None:
    from knora.providers.prompts.builder import build_prompt

    prompt = build_prompt(
        case["profile"],
        question=BASELINE["question"],
        evidence=tuple(GenerationEvidence(**entry) for entry in BASELINE["evidence"]),
        model=case["model"],
    )
    assert prompt.messages == case["request"]["body"]["messages"]
    assert prompt.definition.schema == case["definition"]["schema"]
    assert prompt.definition.version == case["definition"]["version"]
    assert prompt.definition.fingerprint == case["fingerprint"]
    changed_input = build_prompt(
        case["profile"], question="Different dynamic question", evidence=(), model=case["model"]
    )
    assert changed_input.definition.fingerprint == case["fingerprint"]
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


def test_removed_cloudflare_selector_is_not_a_profile() -> None:
    from knora.providers.prompts.builder import build_prompt

    with pytest.raises(ValueError, match="unknown prompt profile"):
        build_prompt("cloudflare-selector", question="Question", evidence=())
