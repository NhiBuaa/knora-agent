"""Workspace-scoped object inventory feed adapter.

The feed is produced by the configured storage/inventory system; it is not an ObjectStore data-plane
capability and therefore does not add list operations to the approved S3 seam.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class JsonlObjectInventory:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def objects(self, *, workspace_id: str) -> list[tuple[str, datetime]]:
        result: list[tuple[str, datetime]] = []
        if not self._path.exists():
            return result
        with self._path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record["workspace_id"] != workspace_id:
                        continue
                    object_key = record["object_key"]
                    created_at = datetime.fromisoformat(record["created_at"])
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    raise ValueError(
                        f"invalid object inventory record at line {line_number}"
                    ) from error
                if not isinstance(object_key, str) or not object_key or created_at.tzinfo is None:
                    raise ValueError(f"invalid object inventory identity at line {line_number}")
                result.append((object_key, created_at))
        return result
