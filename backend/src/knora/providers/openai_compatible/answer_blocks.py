"""Private Cloudflare output; public answers retain the existing Markdown contract."""

from collections import Counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Anchor(_Model):
    evidence_id: str
    quote: str = Field(min_length=1)


class _Statement(_Model):
    text: str = Field(min_length=1)
    support: list[_Anchor] = Field(min_length=1)


class _Paragraph(_Statement):
    kind: Literal["paragraph"]
    bold: str | None = Field(default=None, min_length=1)


class _List(_Model):
    kind: Literal["list"]
    ordered: bool
    items: list[_Statement] = Field(min_length=2)


class _Result(_Model):
    decision: Literal["ANSWER", "REFUSAL"]
    blocks: list[Annotated[_Paragraph | _List, Field(discriminator="kind")]]
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


def _references(support: list[_Anchor], evidence: dict[str, str]) -> list[str]:
    for anchor in support:
        if (
            anchor.evidence_id not in evidence
            or not anchor.quote.strip()
            or " ".join(anchor.quote.split()) not in evidence[anchor.evidence_id]
        ):
            _invalid()
    return list(dict.fromkeys(anchor.evidence_id for anchor in support))


def compose_answer(
    payload: object, evidence: tuple[GenerationEvidence, ...]
) -> tuple[str | None, tuple[str, ...]]:
    try:
        result = _Result.model_validate(payload)
    except ValidationError:
        raise KnoraError("GENERATION_OUTPUT_INVALID") from None
    if result.decision == "REFUSAL":
        if result.blocks or result.refusal_reason != "INSUFFICIENT_EVIDENCE":
            _invalid()
        return None, ()
    if not result.blocks or result.refusal_reason is not None:
        _invalid()

    contents = {entry.evidence_id: " ".join(entry.content.split()) for entry in evidence}
    texts: list[str] = []
    aliases: list[list[str]] = []
    for block in result.blocks:
        if isinstance(block, _List):
            references = []
            positions: dict[str, int] = {}
            uses = Counter(
                pair
                for item in block.items
                for pair in {
                    (anchor.evidence_id, " ".join(anchor.quote.split())) for anchor in item.support
                }
            )
            for item in block.items:
                references.extend(_references(item.support, contents))
                if block.ordered:
                    item_positions: dict[str, int] = {}
                    for anchor in item.support:
                        if uses[(anchor.evidence_id, " ".join(anchor.quote.split()))] > 1:
                            continue
                        position = contents[anchor.evidence_id].find(" ".join(anchor.quote.split()))
                        item_positions[anchor.evidence_id] = min(
                            position, item_positions.get(anchor.evidence_id, position)
                        )
                    if not item_positions:
                        _invalid()
                    for alias, position in item_positions.items():
                        if position <= positions.get(alias, -1):
                            _invalid()
                        positions[alias] = position
            texts.append("\n".join(f"- {_line(item.text)}" for item in block.items))
        else:
            references = _references(block.support, contents)
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
        separator = "\n\n" if isinstance(result.blocks[end], _List) else " "
        texts[end] += separator + " ".join(f"[[{alias}]]" for alias in group)
        cited.extend(group)
        start = end + 1
    return "\n\n".join(texts), tuple(cited)
