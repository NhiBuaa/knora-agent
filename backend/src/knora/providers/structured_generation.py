import json

from knora.providers.generation import GenerationEvidence

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
PROMPT_VERSION = "m1-cited-answer-v1"
SYSTEM_PROMPT = (
    "Return only the requested JSON. Answer only from the supplied evidence and cite its opaque "
    "aliases as inline markers such as [[E1]]. Refuse when the evidence is insufficient. "
    "For an ANSWER, use each inline marker at most once. If several facts are supported by "
    "one alias, combine those facts and place one marker after them; never repeat that marker. "
    "For example, write 'Fact A; fact B. [[E1]]', never 'Fact A [[E1]]; fact B [[E1]]'. "
    "cited_evidence_ids MUST list exactly the same aliases, exactly once each, in the same order "
    "that their markers first appear "
    "in answer text; never use evidence-list order when it differs."
)


def user_message(question: str, evidence: tuple[GenerationEvidence, ...]) -> str:
    return json.dumps(
        {
            "question": question,
            "evidence": [
                {"evidence_id": item.evidence_id, "content": item.content}
                for item in evidence
            ],
        },
        ensure_ascii=False,
    )
