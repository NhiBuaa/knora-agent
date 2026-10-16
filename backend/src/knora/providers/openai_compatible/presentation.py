"""Private Cloudflare presentation choice; this step cannot supply answer content."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from knora.providers.prompts.policy import (
    PRESENTATION_PROMPT_VERSION as PRESENTATION_PROMPT_VERSION,
)
from knora.providers.prompts.policy import (
    PRESENTATION_SYSTEM_PROMPT as PRESENTATION_SYSTEM_PROMPT,
)

Presentation = Literal["prose", "list", "count_prose", "count_list"]


class PresentationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    presentation: Presentation


PRESENTATION_SCHEMA = PresentationChoice.model_json_schema()
