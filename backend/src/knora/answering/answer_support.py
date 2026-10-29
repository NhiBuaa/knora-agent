"""Bind a semantic verdict to the exact composed answer and authorized source snapshot."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from knora.domain.errors import KnoraError
from knora.providers.generation import AnswerProjection, AnswerStatement, GenerationEvidence

POLICY_ID = "answer-support-verification-v3-r4-v1"
PROMPT_ID = "cloudflare-gpt-oss-answer-support-v3"


def required_answer_groups(groups: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    """Keep coordinated questions separate even when retrieval used one broad intent."""
    separator = re.compile(
        r"(?:[,;?]\s*(?:(?:và|and)\s+)?|\s+(?:và|and)\s+)"
        r"(?=(?:cần|phải|bao|những|gồm|khi|ở|tại|vì|ai|có|dùng|sử dụng|trình bày|"
        r"mô tả|giải thích|lựa chọn|chọn|what|how|when|where|why|"
        r"which|who|must|should|is|are|do|does|can)\b)",
        re.IGNORECASE,
    )
    result = []
    for key, question in groups:
        parts = tuple(part.strip() for part in separator.split(question) if part.strip())
        result.extend(
            (f"{key}.{i}" if len(parts) > 1 else key, part) for i, part in enumerate(parts, 1)
        )
    return tuple(result)


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class SourceRef(_Strict):
    alias: str
    exact_quote: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    reason: Literal["ENTAILMENT", "EXPLICIT_CONVERSION", "ENUMERATION"]


class StatementVerdict(_Strict):
    id: str
    verdict: Literal["SUPPORTED", "CONTRADICTED", "UNKNOWN"]
    source_refs: list[SourceRef]


class GroupVerdict(_Strict):
    id: str
    verdict: Literal["ANSWERED", "MISSING", "UNKNOWN"]
    statement_ids: list[str]


class SupportVerdict(_Strict):
    answer_digest: str
    snapshot_digest: str
    statements: list[StatementVerdict]
    groups: list[GroupVerdict]


@dataclass(frozen=True, slots=True)
class AnswerSupportProof:
    answer_digest: str
    snapshot_digest: str
    verdict_json: str


class AnswerSupportFailure(KnoraError):
    def __init__(self, code: str, observation: dict) -> None:
        super().__init__(code)
        self.observation = observation


class AnswerSupportVerifier(Protocol):
    async def verify(
        self,
        *,
        question: str,
        groups: tuple[tuple[str, str], ...],
        answer: str,
        answer_projection: AnswerProjection,
        evidence: tuple[GenerationEvidence, ...],
        snapshot_digest: str,
        feedback: dict | None = None,
    ) -> tuple[AnswerSupportProof, dict]: ...


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def validate_projection(
    answer: str, projection: AnswerProjection, evidence: tuple[GenerationEvidence, ...]
) -> None:
    from knora.providers.openai_compatible.answer_blocks import _escape

    def invalid():
        raise KnoraError("GENERATION_OUTPUT_INVALID")

    if (
        hashlib.sha256(answer.encode("utf-8")).hexdigest() != projection.answer_digest
        or not 1 <= len(projection.statements) <= 32
    ):
        invalid()
    cursor = 0
    available = {e.evidence_id for e in evidence}
    referenced = {a for s in projection.statements for a in s.aliases}
    if set(re.findall(r"\[\[(E[1-9][0-9]*)\]\]", answer)) != referenced:
        invalid()
    for index, statement in enumerate(projection.statements, 1):
        if not statement.text.strip():
            invalid()
        if statement.id != f"S{index}" or not cursor <= statement.start < statement.end <= len(
            answer
        ):
            invalid()
        gap = answer[cursor : statement.start]
        if re.sub(r"\[\[E[1-9][0-9]*\]\]", "", gap).strip():
            invalid()
        rendered = answer[statement.start : statement.end]
        if rendered.startswith("- "):
            rendered = rendered[2:]
        if rendered.replace("**", "") != _escape(statement.text):
            invalid()
        if (
            not statement.aliases
            or len(set(statement.aliases)) != len(statement.aliases)
            or not set(statement.aliases) <= available
        ):
            invalid()
        # Each item's own aliases must appear in its following enclosing citation group.
        following = answer[statement.end :]
        next_markers = re.search(r"(?:\[\[E[1-9][0-9]*\]\]\s*)+", following)
        if next_markers is None or not set(statement.aliases) <= set(
            re.findall(r"\[\[(E[1-9][0-9]*)\]\]", next_markers[0])
        ):
            invalid()
        cursor = statement.end
    if re.sub(r"\[\[E[1-9][0-9]*\]\]", "", answer[cursor:]).strip():
        invalid()


def validate_support(
    payload: object,
    *,
    answer: str,
    projection: AnswerProjection,
    evidence: tuple[GenerationEvidence, ...],
    snapshot_digest: str,
    group_ids: tuple[str, ...],
) -> AnswerSupportProof:
    validate_projection(answer, projection, evidence)
    failure = "invalid_verifier_proof"
    failed_id = None
    try:
        verdict = SupportVerdict.model_validate(payload)
        if (
            verdict.answer_digest != projection.answer_digest
            or verdict.snapshot_digest != snapshot_digest
        ):
            raise ValueError
        statements = {s.id: s for s in projection.statements}
        if len(verdict.statements) != len(statements) or {s.id for s in verdict.statements} != set(
            statements
        ):
            raise ValueError
        sources = {e.evidence_id: e.content for e in evidence}
        for item in verdict.statements:
            failed_id = item.id
            failure = (
                "unsupported_answer" if item.verdict != "SUPPORTED" else "invalid_verifier_proof"
            )
            if item.verdict != "SUPPORTED" or not item.source_refs:
                raise ValueError
            for ref in item.source_refs:
                if (
                    ref.alias not in statements[item.id].aliases
                    or not 0 <= ref.start < ref.end <= len(sources[ref.alias])
                    or sources[ref.alias][ref.start : ref.end] != ref.exact_quote
                ):
                    raise ValueError
            failure = "unsupported_answer"
            _validate_explicit_facts(
                statements[item.id].text, "\n".join(ref.exact_quote for ref in item.source_refs)
            )
        failure = "invalid_verifier_proof"
        failed_id = None
        if len(verdict.groups) != len(group_ids) or {g.id for g in verdict.groups} != set(
            group_ids
        ):
            raise ValueError
        for group in verdict.groups:
            failed_id = group.id
            failure = (
                "unsupported_answer" if group.verdict != "ANSWERED" else "invalid_verifier_proof"
            )
            if (
                group.verdict != "ANSWERED"
                or not group.statement_ids
                or len(set(group.statement_ids)) != len(group.statement_ids)
                or not set(group.statement_ids) <= set(statements)
            ):
                raise ValueError
        return AnswerSupportProof(
            projection.answer_digest, snapshot_digest, verdict.model_dump_json()
        )
    except (ValidationError, KeyError, TypeError, ValueError):
        raise AnswerSupportFailure(
            "GENERATION_OUTPUT_INVALID",
            {
                "failure": failure,
                "failed_id": failed_id,
            },
        ) from None


def _validate_explicit_facts(statement: str, source: str) -> None:
    """Reject provable mismatches only; uncertain relations remain the verifier's task."""

    def negative_requirements(text):
        result = {}
        normalized = " ".join(text.casefold().split())
        for force, action in re.findall(
            r"\b(không nên|không được|should not|must not)\s+([^.!?;]+)", normalized
        ):
            result.setdefault(action.strip(), set()).add(
                "prohibited" if force in {"không được", "must not"} else "discouraged"
            )
        return result

    # Compare the same explicit action, never a prohibition elsewhere in the source.
    source_requirements = negative_requirements(source)
    for action, forces in negative_requirements(statement).items():
        if "prohibited" in forces and source_requirements.get(action) == {"discouraged"}:
            raise ValueError

    def tuples(text):
        units = {
            "days": ("day", 1),
            "day": ("day", 1),
            "ngày": ("day", 1),
            "weeks": ("day", 7),
            "week": ("day", 7),
            "tuần": ("day", 7),
        }
        result = {}
        for number, unit in re.findall(
            r"(?<![\w./-])(\d+(?:[.,]\d+)?)\s*(ngày|tuần|days?|weeks?|tháng|năm|months?|years?|usd|vnd|đồng|kg|km|mb|gb|chương)\b",
            text.casefold(),
        ):
            key, factor = units.get(unit, (unit, 1))
            result.setdefault(key, set()).add(Decimal(number.replace(",", ".")) * factor)
        return result

    source_facts = tuples(source)
    for unit, values in tuples(statement).items():
        if unit in source_facts and not values <= source_facts[unit]:
            raise ValueError

    def dates(text):
        return {
            (int(y), int(m), int(d))
            for d, m, y in re.findall(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text)
        } | {
            (int(y), int(m), int(d))
            for y, m, d in re.findall(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
        }

    if dates(source) and not dates(statement) <= dates(source):
        raise ValueError

    def codes(text):
        result = {}
        for prefix, number in re.findall(r"\b([A-Z]{1,8})[ _-]?(\d+(?:[._-]\d+)*)\b", text):
            result.setdefault(prefix, set()).add(number)
        return result

    source_codes = codes(source)
    for prefix, values in codes(statement).items():
        if prefix in source_codes and not values <= source_codes[prefix]:
            raise ValueError


def proof_observation(
    proof: AnswerSupportProof,
    projection: AnswerProjection,
    groups: tuple[tuple[str, str], ...],
    metadata: dict,
) -> dict:
    return {
        "policy_id": POLICY_ID,
        "status": "supported",
        "projection": asdict(projection),
        "groups": [list(group) for group in groups],
        "verdict": json.loads(proof.verdict_json),
        "provider": metadata,
    }


def validate_trace_support(trace, sources: dict[str, tuple[str, str]]) -> None:
    """Version-4 decoder; source text/checksums must come from PostgreSQL, not the trace."""
    try:
        observation = trace.provider_metadata["answer_support"]
        binding = observation["snapshot_binding"]
        if (
            observation["policy_id"] != POLICY_ID
            or observation["status"] != "supported"
            or binding["workspace_id"] != trace.workspace_id
            or binding["original_question"] != trace.question
            or binding["lexical_generations"]
            != trace.provider_metadata["retrieval"]["lexical_generations"]
            or observation["groups"] != binding["groups"]
        ):
            raise ValueError
        expected_sources = [
            {"alias": alias, "chunk_id": chunk_id, "content_checksum": sources[chunk_id][1]}
            for alias, chunk_id in trace.alias_mapping.items()
        ]
        if binding["sources"] != expected_sources:
            raise ValueError
        raw = observation["projection"]
        projection = AnswerProjection(
            raw["answer_digest"],
            tuple(
                AnswerStatement(s["id"], s["text"], s["start"], s["end"], tuple(s["aliases"]))
                for s in raw["statements"]
            ),
        )
        evidence = tuple(
            GenerationEvidence(alias, sources[cid][0]) for alias, cid in trace.alias_mapping.items()
        )
        validate_support(
            observation["verdict"],
            answer=trace.answer,
            projection=projection,
            evidence=evidence,
            snapshot_digest=digest(binding),
            group_ids=tuple(g[0] for g in binding["groups"]),
        )
    except (KeyError, TypeError, AttributeError, ValueError):
        raise KnoraError("GENERATION_OUTPUT_INVALID") from None
