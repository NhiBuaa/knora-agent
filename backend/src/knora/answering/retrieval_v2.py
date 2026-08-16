import unicodedata
from dataclasses import dataclass

_STOPWORDS = frozenset(
    [
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in",
        "is", "it", "of", "on", "or", "that", "the", "to", "was", "what", "when",
        "where", "which", "who", "why", "with",
    ]
)


@dataclass(frozen=True, slots=True)
class LexicalNormalization:
    normalized_lexemes: tuple[str, ...]
    omitted_lexemes: tuple[str, ...]


def normalize_fts_m3_or_v2_details(query_text: str) -> LexicalNormalization:
    """Return the immutable lexical policy output and omitted token observations."""

    normalized = unicodedata.normalize("NFKC", query_text).casefold()
    characters = [
        character if unicodedata.category(character)[0] not in {"P", "Z", "C", "S"} else " "
        for character in normalized
    ]
    tokens = tuple("".join(characters).split())
    lexemes: list[str] = []
    omitted: list[str] = []
    seen_lexemes: set[str] = set()
    seen_omitted: set[str] = set()
    for token in tokens:
        if not token:
            continue
        if token not in _STOPWORDS and token.isalnum():
            if token not in seen_lexemes:
                lexemes.append(token)
                seen_lexemes.add(token)
            continue
        if token not in seen_omitted:
            omitted.append(token)
            seen_omitted.add(token)
    return LexicalNormalization(tuple(lexemes), tuple(omitted))


def normalize_fts_m3_or_v2(query_text: str) -> tuple[str, ...]:
    """Return the immutable fts-m3-or-v2 lexeme sequence."""

    return normalize_fts_m3_or_v2_details(query_text).normalized_lexemes
