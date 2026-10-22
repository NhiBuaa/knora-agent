"""Static definition identity; request content is deliberately excluded."""

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    version: str
    system_prompt: str
    schema: dict
    serializer_id: str

    @property
    def fingerprint(self) -> str:
        content = json.dumps(
            asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
