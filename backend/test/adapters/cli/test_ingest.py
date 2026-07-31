from pathlib import Path

import pytest

from knora.adapters.cli.ingest import media_type_for_path
from knora.domain.errors import KnoraError


@pytest.mark.parametrize("name", ["policy.md", "policy.markdown"])
def test_cli_accepts_markdown_paths(name: str) -> None:
    assert media_type_for_path(Path(name)) == "text/markdown"


@pytest.mark.parametrize("name", ["policy.txt", "policy.text", "policy"])
def test_cli_accepts_plain_text_paths(name: str) -> None:
    assert media_type_for_path(Path(name)) == "text/plain"


def test_cli_rejects_unsupported_path_extensions() -> None:
    with pytest.raises(KnoraError, match="UNSUPPORTED_DOCUMENT_TYPE"):
        media_type_for_path(Path("policy.json"))
