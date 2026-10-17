"""Private Cloudflare output; public answers retain the existing Markdown contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.presentation import Presentation, SourceCondition


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Statement(_Model):
    text: str = Field(min_length=1)
    support: list[str] = Field(min_length=1)


class _Paragraph(_Statement):
    bold: str | None = Field(min_length=1)


class _List(_Model):
    items: list[_Statement] = Field(min_length=2)


class _Result(_Model):
    decision: Literal["ANSWER", "REFUSAL"]
    before: list[_Paragraph]
    items: list[_Statement]
    after: list[_Paragraph]
    refusal_reason: Literal["INSUFFICIENT_EVIDENCE"] | None


ANSWER_BLOCK_SCHEMA = _Result.model_json_schema()


def _invalid() -> None:
    raise KnoraError("GENERATION_OUTPUT_INVALID")


def _line(text: str) -> str:
    if not text.strip() or any(token in text for token in ("\n", "\r", "[[", "]]")):
        _invalid()
    return _escape(text.strip())


def _escape(text: str) -> str:
    escaped = text.translate(str.maketrans({char: "\\" + char for char in "\\`*_{}[]<>()&#+-|~"}))
    number, dot, rest = escaped.partition(".")
    if dot and number.isdigit() and rest.startswith((" ", "\t")):
        escaped = number + "\\." + rest
    return escaped


def _references(support: list[str], evidence: set[str]) -> list[str]:
    if any(alias not in evidence for alias in support):
        _invalid()
    return list(dict.fromkeys(support))


def condition_paragraphs(
    conditions: list[SourceCondition],
    evidence: tuple[GenerationEvidence, ...],
) -> tuple[_Paragraph, ...]:
    paragraphs = tuple(_Paragraph(**condition.model_dump(), bold=None) for condition in conditions)
    available_ids = {entry.evidence_id for entry in evidence}
    for paragraph in paragraphs:
        _line(paragraph.text)
        _references(paragraph.support, available_ids)
    return paragraphs


def compose_answer(
    payload: object,
    evidence: tuple[GenerationEvidence, ...],
    *,
    presentation: Presentation | None = None,
    conditions: tuple[_Paragraph, ...] = (),
) -> tuple[str | None, tuple[str, ...]]:
    try:
        result = _Result.model_validate(payload)
    except ValidationError:
        raise KnoraError("GENERATION_OUTPUT_INVALID") from None
    if result.decision == "REFUSAL":
        if (
            result.before
            or result.items
            or result.after
            or result.refusal_reason != "INSUFFICIENT_EVIDENCE"
        ):
            _invalid()
        return None, ()
    if not (result.before or result.items or result.after) or result.refusal_reason is not None:
        _invalid()

    has_list = bool(result.items)
    if has_list and len(result.items) < 2:
        _invalid()
    if presentation is not None:
        if has_list != (presentation in ("list", "count_list")):
            _invalid()
        if presentation in ("count_prose", "count_list") and (
            not result.before or "bold" not in result.before[0].model_fields_set
        ):
            _invalid()

    if conditions and presentation not in ("list", "count_list"):
        _invalid()
    result.after.extend(conditions)

    blocks: list[_Paragraph | _List] = [*result.before]
    if has_list:
        blocks.append(_List(items=result.items))
    blocks.extend(result.after)
    available_ids = {entry.evidence_id for entry in evidence}
    texts: list[str] = []
    aliases: list[list[str]] = []
    for block in blocks:
        if isinstance(block, _List):
            references = []
            for item in block.items:
                references.extend(_references(item.support, available_ids))
            texts.append("\n".join(f"- {_line(item.text)}" for item in block.items))
        else:
            references = _references(block.support, available_ids)
            text = _line(block.text)
            if block.bold is not None:
                phrase = block.bold.strip()
                emphasis = _line(phrase)
                if block.text.strip().count(phrase) != 1:
                    _invalid()
                before, _, after = block.text.strip().partition(phrase)
                text = f"{_escape(before)}**{emphasis}**{_escape(after)}"
            texts.append(text)
        aliases.append(list(dict.fromkeys(references)))

    # Keep every source and the accepted unique-alias contract when sources recur.
    last_use = {alias: index for index, group in enumerate(aliases) for alias in group}
    cited: list[str] = []
    start = 0
    while start < len(texts):
        end = start
        cursor = start
        group: list[str] = []
        while cursor <= end:
            for alias in aliases[cursor]:
                end = max(end, last_use[alias])
                if alias not in group:
                    group.append(alias)
            cursor += 1
        separator = "\n\n" if isinstance(blocks[end], _List) else " "
        texts[end] += separator + " ".join(f"[[{alias}]]" for alias in group)
        cited.extend(group)
        start = end + 1
    return "\n\n".join(texts), tuple(cited)
