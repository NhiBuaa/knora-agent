"""Readable citation previews, without changing the immutable source range."""

import re


def citation_excerpt(
    content: str,
    *,
    start_offset: int | None = None,
    end_offset: int | None = None,
) -> str:
    """Show complete interior words and mark omitted text.

    Historical PDF chunks can start/end inside a word. Their locators do not
    contain the adjacent page characters, so conservatively omit edge words
    rather than reconstructing them. The source link retains the full range.
    This changes only the preview, never chunk content, checksum or offsets.
    """
    text = content.strip()
    leading = start_offset is not None and start_offset > 0
    trailing = end_offset is not None and not re.search(r"[.!?…。！？][\"'”’)]*$", text)
    if leading:
        boundary = re.search(r"\s+", text)
        text = text[boundary.end() :] if boundary else ""
    if trailing:
        boundaries = list(re.finditer(r"\s+", text))
        text = text[: boundaries[-1].start()] if boundaries else ""
    prefix = "… " if leading else ""
    if len(prefix) + len(text) + (2 if trailing else 0) > 500:
        limit = 500 - len(prefix) - 2
        boundaries = list(re.finditer(r"\s+", text[: limit + 1]))
        text = text[: boundaries[-1].start()] if boundaries else ""
        trailing = True
    if not text:
        return "…" if content else ""
    return prefix + text.rstrip() + (" …" if trailing else "")
