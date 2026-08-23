"""Canonical value and digest contracts shared by typed M4 tool boundaries."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        raise ValueError("canonical-json-v1 forbids floating-point values")
    if isinstance(value, datetime):
        return format_timestamp(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace(
            "\r", "\n"
        )
        if "\x00" in normalized or any(
            0xD800 <= ord(character) <= 0xDFFF for character in normalized
        ):
            raise ValueError("canonical-json-v1 string is not a Unicode scalar sequence")
        return normalized
    if isinstance(value, Mapping):
        projected: dict[str, object] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("canonical-json-v1 object keys must be strings")
            canonical_key = _canonical_value(key)
            assert isinstance(canonical_key, str)
            if canonical_key in projected:
                raise ValueError("canonical-json-v1 object keys collide after normalization")
            projected[canonical_key] = _canonical_value(nested)
        return projected
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return [_canonical_value(item) for item in value]
    raise ValueError(f"unsupported canonical-json-v1 value: {type(value).__name__}")


def canonical_json_v1(value: object) -> bytes:
    """Return the exact UTF-8 canonical-json-v1 representation."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest_v1(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_v1(value)).hexdigest()


def require_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or DIGEST_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase sha256 digest")
    return value


def format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("canonical timestamp must be timezone-aware")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"{field} must use six fractional digits and Z") from exc
    if format_timestamp(parsed) != value:
        raise ValueError(f"{field} is not canonical")
    return parsed
