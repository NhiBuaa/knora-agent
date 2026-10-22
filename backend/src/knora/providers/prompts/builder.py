"""Pure production message building; adapters own transport and response handling."""

import json
from dataclasses import dataclass
from typing import Literal

from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.answer_blocks import ANSWER_BLOCK_SCHEMA
from knora.providers.prompts import policy
from knora.providers.prompts.versioning import PromptDefinition
from knora.providers.structured_generation import STRUCTURED_RESULT_SCHEMA

Profile = Literal["generic", "ollama", "cloudflare-answer"]


@dataclass(frozen=True, slots=True)
class BuiltPrompt:
    definition: PromptDefinition
    messages: list[dict[str, str]]


def build_prompt(
    profile: Profile,
    *,
    question: str,
    evidence: tuple[GenerationEvidence, ...],
    model: str = "",
) -> BuiltPrompt:
    schema = STRUCTURED_RESULT_SCHEMA
    serializer = policy.user_message
    serializer_id = "question-evidence-v1"
    if profile == "generic":
        version, system = policy.PROMPT_VERSION, policy.SYSTEM_PROMPT
    elif profile == "ollama":
        version, system = policy.OLLAMA_PROMPT_VERSION, policy.OLLAMA_SYSTEM_PROMPT
        serializer, serializer_id = (
            policy.ollama_user_message,
            "ollama-evidence-current-question-v1",
        )
        if model == "gpt-oss:20b":
            version = f"ollama-gpt-oss-low-schema-v3:{version}"
            system += policy.OLLAMA_GPT_OSS_SUFFIX
            system += "\nRequired response JSON schema:\n" + json.dumps(schema, sort_keys=True)
    elif profile == "cloudflare-answer":
        version = policy.CLOUDFLARE_PROMPT_VERSION
        system = policy.CLOUDFLARE_SYSTEM_PROMPT
        schema = ANSWER_BLOCK_SCHEMA
    else:
        raise ValueError(f"unknown prompt profile: {profile}")
    definition = PromptDefinition(version, system, schema, serializer_id)
    return BuiltPrompt(
        definition,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": serializer(question, evidence)},
        ],
    )
