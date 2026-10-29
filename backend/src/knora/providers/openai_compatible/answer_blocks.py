"""Private Cloudflare output; public answers retain the existing Markdown contract."""

import re
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from knora.domain.errors import KnoraError
from knora.providers.generation import AnswerProjection, AnswerStatement, GenerationEvidence


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


def compose_answer(
    payload: object,
    evidence: tuple[GenerationEvidence, ...],
) -> tuple[str | None, tuple[str, ...]]:
    answer, cited, _ = compose_answer_projection(payload, evidence)
    return answer, cited


def compose_answer_projection(
    payload: object,
    evidence: tuple[GenerationEvidence, ...],
) -> tuple[str | None, tuple[str, ...], AnswerProjection | None]:
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
        return None, (), None
    if not (result.before or result.items or result.after) or result.refusal_reason is not None:
        _invalid()

    has_list = bool(result.items)
    if has_list and len(result.items) < 2:
        _invalid()
    blocks: list[_Paragraph | _List] = [*result.before]
    if has_list:
        blocks.append(_List(items=result.items))
    blocks.extend(result.after)
    available_ids = {entry.evidence_id for entry in evidence}
    texts: list[str] = []
    aliases: list[list[str]] = []
    spans: list[list[tuple[str, int, int, tuple[str, ...]]]] = []
    for block in blocks:
        if isinstance(block, _List):
            references = []
            lines = []
            block_spans = []
            offset = 0
            for item in block.items:
                references.extend(_references(item.support, available_ids))
                line = f"- {_line(item.text)}"
                block_spans.append(
                    (
                        item.text.strip(),
                        offset,
                        offset + len(line),
                        tuple(dict.fromkeys(item.support)),
                    )
                )
                lines.append(line)
                offset += len(line) + 1
            texts.append("\n".join(lines))
            spans.append(block_spans)
        else:
            references = _references(block.support, available_ids)
            text = _line(block.text)
            if block.bold is not None:
                phrase = block.bold.strip()
                occurrences = list(
                    re.finditer(re.escape(phrase), block.text.strip(), re.IGNORECASE)
                )
                if len(occurrences) != 1:
                    _invalid()
                match = occurrences[0]
                literal = block.text.strip()
                before, after = literal[: match.start()], literal[match.end() :]
                emphasis = _line(match[0])
                text = f"{_escape(before)}**{emphasis}**{_escape(after)}"
            texts.append(text)
            spans.append([(block.text.strip(), 0, len(text), tuple(references))])
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
    answer = "\n\n".join(texts)
    statements = []
    offset = 0
    for text, block_spans in zip(texts, spans, strict=True):
        for literal, start, end, support in block_spans:
            statements.append(
                AnswerStatement(
                    f"S{len(statements) + 1}", literal, offset + start, offset + end, support
                )
            )
        offset += len(text) + 2
    return (
        answer,
        tuple(cited),
        AnswerProjection(sha256(answer.encode("utf-8")).hexdigest(), tuple(statements)),
    )
