from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_pdf_runs import binding_for, frozen_dataset

from knora.evaluation import pdf_runtime


def corpus_for(frozen):
    return SimpleNamespace(
        workspace_id=frozen.reference.workspace_id,
        documents=(
            SimpleNamespace(
                source_key="evaluation/pdf-set/source-1",
                document_version_id="version-1",
                raw_sha256="a" * 64,
                chunk_set_id="set-1",
                embedding_set_id="embedding-set-1",
                embedding_configuration_id="embedding-test",
                chunk_ids=("chunk-1",),
            ),
        ),
    )


def test_reviewed_preparation_rechecks_corpus_and_isolates_approval_snapshot():
    frozen = frozen_dataset()
    binding = binding_for(frozen)
    original = deepcopy(binding)
    corpus = corpus_for(frozen)
    reads = []

    def read_active_corpus(*, workspace_id):
        reads.append(workspace_id)
        return corpus

    prepare = pdf_runtime.reviewed_pdf_preparation(
        binding=binding, corpus_reader=SimpleNamespace(read_active_corpus=read_active_corpus)
    )
    assert reads == []
    binding["sources"]["version-1"]["chunk_ids"].append("unreviewed")
    first = prepare(frozen)
    assert first == original
    first["approval"]["owner_subject"] = "rewritten"
    assert prepare(frozen) == original
    assert reads == [frozen.reference.workspace_id] * 2

    corpus.documents[0].chunk_ids = ("replaced-chunk",)
    with pytest.raises(ValueError, match="corpus"):
        prepare(frozen)


@pytest.mark.parametrize(
    "source_key", ["documents/other-source", "evaluation/other-dataset/source"]
)
def test_reviewed_preparation_rejects_other_active_workspace_sources(source_key):
    frozen = frozen_dataset()
    corpus = corpus_for(frozen)
    unrelated = deepcopy(corpus.documents[0])
    unrelated.source_key = source_key
    unrelated.document_version_id = "other-version"
    corpus.documents += (unrelated,)
    prepare = pdf_runtime.reviewed_pdf_preparation(
        binding=binding_for(frozen),
        corpus_reader=SimpleNamespace(read_active_corpus=lambda **_: corpus),
    )
    with pytest.raises(ValueError, match="corpus population mismatch"):
        prepare(frozen)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_version_id", "another-version"),
        ("raw_sha256", "b" * 64),
        ("chunk_set_id", "another-chunk-set"),
        ("embedding_set_id", "another-embedding-set"),
        ("embedding_configuration_id", "another-configuration"),
        ("chunk_ids", ("chunk-1", "unreviewed")),
        ("chunk_ids", ("chunk-1", "chunk-1")),
    ],
)
def test_reviewed_preparation_rejects_runtime_identity_drift(field, value):
    frozen = frozen_dataset()
    corpus = corpus_for(frozen)
    setattr(corpus.documents[0], field, value)
    prepare = pdf_runtime.reviewed_pdf_preparation(
        binding=binding_for(frozen),
        corpus_reader=SimpleNamespace(read_active_corpus=lambda **_: corpus),
    )
    with pytest.raises(ValueError, match="corpus"):
        prepare(frozen)


@pytest.mark.parametrize("change", ["workspace", "missing", "extra", "duplicate"])
def test_reviewed_preparation_rejects_unreviewed_corpus_population(change):
    frozen = frozen_dataset()
    corpus = corpus_for(frozen)
    if change == "workspace":
        corpus.workspace_id = "other-workspace"
    elif change == "missing":
        corpus.documents = ()
    else:
        extra = deepcopy(corpus.documents[0])
        if change == "extra":
            extra.document_version_id = "unreviewed-version"
        corpus.documents += (extra,)
    prepare = pdf_runtime.reviewed_pdf_preparation(
        binding=binding_for(frozen),
        corpus_reader=SimpleNamespace(read_active_corpus=lambda **_: corpus),
    )
    with pytest.raises(ValueError, match="corpus"):
        prepare(frozen)


def test_reviewed_preparation_never_rebinds_a_different_frozen_version():
    frozen = frozen_dataset()
    prepare = pdf_runtime.reviewed_pdf_preparation(
        binding=binding_for(frozen),
        corpus_reader=SimpleNamespace(
            read_active_corpus=lambda **_: pytest.fail("Must reject gold before reading runtime")
        ),
    )
    with pytest.raises(ValueError, match="reference"):
        prepare(replace(frozen, reference=replace(frozen.reference, version=2)))
