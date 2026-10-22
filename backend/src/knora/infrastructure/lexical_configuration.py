"""Load the reviewed finite S2 population at the deployment composition boundary."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from knora.answering.stores import RetrievalConfiguration
from knora.ingestion.lexical_population import VerifiedLexicalPopulation

_POPULATIONS = {
    "retrieval-bm25-top8-v1": (
        "bm25-word-frozen47-population-v1",
        "5d9ddeec5aca02d0ceabaaebe7ae867ba895fc1e8cf67e13859fbd0923b7fe60",
    ),
    "retrieval-bm25-upload-fixture-top8-v1": (
        "bm25-word-upload-fixture-population-v1",
        "e29bd9a22e6cabbf5e2ffd8580f006801470886859801469b3fe68ae422869a0",
    ),
}


def load_lexical_population(
    configuration: RetrievalConfiguration, manifest_path: str | None
) -> VerifiedLexicalPopulation | None:
    if configuration.strategy != "bm25-only" and configuration.id not in _POPULATIONS:
        return None
    pin = _POPULATIONS.get(configuration.id)
    if pin is None or not manifest_path:
        raise ValueError("reviewed lexical population configuration is required")
    expected = replace(
        RetrievalConfiguration.bm25_diagnostic_v1(),
        id=configuration.id,
        candidate_k=8,
        lexical_policy_id=pin[0],
    )
    if configuration != expected:
        raise ValueError("reviewed lexical population configuration is required")
    try:
        data = Path(manifest_path).read_bytes().replace(b"\r\n", b"\n")
    except OSError as exc:
        raise ValueError("lexical population manifest is unavailable") from exc
    if hashlib.sha256(data).hexdigest() != pin[1]:
        raise ValueError("lexical population manifest does not match the reviewed pin")
    return VerifiedLexicalPopulation.from_mapping(json.loads(data))
