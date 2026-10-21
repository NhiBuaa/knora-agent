"""Finite deployment selection must not trust a caller-provided manifest hash."""

from dataclasses import replace
from pathlib import Path

import pytest

from knora.answering.stores import RetrievalConfiguration
from knora.infrastructure.lexical_configuration import load_lexical_population

MANIFEST = "evals/fixtures/pdf_retrieval_v3_s2/frozen47-lexical-population-v1.json"


def configuration():
    return replace(
        RetrievalConfiguration.bm25_diagnostic_v1(),
        id="retrieval-bm25-top8-v1",
        candidate_k=8,
        lexical_policy_id="bm25-word-frozen47-population-v1",
    )


def test_dense_default_does_not_load_a_lexical_population():
    assert load_lexical_population(RetrievalConfiguration.milestone_one(), None) is None


def test_opt_in_loads_only_the_reviewed_population_pin():
    population = load_lexical_population(configuration(), MANIFEST)
    assert population.profile.id == configuration().lexical_policy_id
    assert population.profile.digest() == (
        "f54643e1d15632ebdf46739fbe3b4523aee77fe892628587498058c4bbb0b849"
    )


def test_upload_fixture_uses_its_own_config_and_population():
    config = replace(
        configuration(),
        id="retrieval-bm25-upload-fixture-top8-v1",
        lexical_policy_id="bm25-word-upload-fixture-population-v1",
    )
    population = load_lexical_population(
        config, "evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json"
    )
    assert population.profile.id == config.lexical_policy_id
    assert population.profile.avg_len == 7
    with pytest.raises(ValueError, match="population"):
        load_lexical_population(config, MANIFEST)


@pytest.mark.parametrize("path", [None, "missing-population.json"])
def test_opt_in_requires_an_existing_manifest(path):
    with pytest.raises(ValueError, match="population"):
        load_lexical_population(configuration(), path)


@pytest.mark.parametrize("change", ["counts", "source", "evidence_pin", "profile", "whitespace"])
def test_modified_manifest_cannot_self_authorize_another_population(tmp_path, change):
    original = Path(MANIFEST).read_text(encoding="utf-8")
    changed = {
        "counts": original.replace('"native_token_count":', '"altered_count":', 1),
        "source": original.replace('"source_sha256":', '"altered_source":', 1),
        "evidence_pin": original.replace("556f3733", "00000000", 1),
        "profile": original.replace("frozen47-population-v1", "unverified-population-v1"),
        "whitespace": original + " ",
    }[change]
    path = tmp_path / "population.json"
    path.write_text(changed, encoding="utf-8")
    with pytest.raises(ValueError, match="population"):
        load_lexical_population(configuration(), str(path))


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_line_ending_conversion_keeps_the_same_finite_pin(tmp_path, newline):
    path = tmp_path / "population.json"
    data = Path(MANIFEST).read_bytes().replace(b"\r\n", b"\n")
    path.write_bytes(data.replace(b"\n", newline))
    assert load_lexical_population(configuration(), str(path)).profile.id == (
        configuration().lexical_policy_id
    )


@pytest.mark.parametrize("change", ["id", "lexical_policy_id", "candidate_k"])
def test_configuration_identity_cannot_rebind_the_approved_manifest(change):
    config = replace(configuration(), **{change: 200 if change == "candidate_k" else "unknown"})
    with pytest.raises(ValueError, match="population"):
        load_lexical_population(config, MANIFEST)
