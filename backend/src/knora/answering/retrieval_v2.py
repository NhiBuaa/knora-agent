import unicodedata

_STOPWORDS = frozenset(
    [
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in",
        "is", "it", "of", "on", "or", "that", "the", "to", "was", "what", "when",
        "where", "which", "who", "why", "with",
    ]
)


def normalize_fts_m3_or_v2(query_text: str) -> tuple[str, ...]:
    """Return the immutable fts-m3-or-v2 lexeme sequence."""

    normalized = unicodedata.normalize("NFKC", query_text).casefold()
    characters = [
        character if unicodedata.category(character)[0] not in {"P", "Z", "C", "S"} else " "
        for character in normalized
    ]
    lexemes = {
        token
        for token in "".join(characters).split()
        if token and token not in _STOPWORDS and token.isalnum()
    }
    return tuple(sorted(lexemes))
