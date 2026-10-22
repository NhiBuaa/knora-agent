from knora.providers.prompts.policy import (
    PROMPT_VERSION as PROMPT_VERSION,
)
from knora.providers.prompts.policy import (
    SYSTEM_PROMPT as SYSTEM_PROMPT,
)
from knora.providers.prompts.policy import (
    user_message as user_message,
)

STRUCTURED_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["ANSWER", "REFUSAL"]},
        "answer": {"type": ["string", "null"]},
        "cited_evidence_ids": {"type": "array", "items": {"type": "string"}},
        "refusal_reason": {
            "type": ["string", "null"],
            "enum": ["INSUFFICIENT_EVIDENCE", None],
        },
    },
    "required": ["decision", "answer", "cited_evidence_ids", "refusal_reason"],
    "additionalProperties": False,
}
