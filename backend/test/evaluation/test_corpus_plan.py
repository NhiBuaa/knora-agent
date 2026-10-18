from dataclasses import replace

import pytest
from test_pdf_runs import frozen_dataset

from knora.evaluation.contracts import PdfSource, digest_json, freeze_dataset
from knora.ingestion.jobs import PdfSubmissionConfiguration
from knora.providers.embedding import EmbeddingConfiguration


def plan_fixture():
    from knora.evaluation.corpus_preparation import CorpusPreparationPlan, CorpusSourcePin

    original = frozen_dataset()
    gold = replace(
        original.gold,
        sources=(*original.gold.sources, PdfSource("document-2", "version-2", "b" * 64)),
    )
    frozen = freeze_dataset(gold, replace(original.approval, gold_digest=gold.digest))
    pins = tuple(
        CorpusSourcePin(
            source_id=f"source-{n}",
            job_id=f"job-{n}",
            document_id=f"document-{n}",
            document_version_id=f"version-{n}",
            source_key=f"evaluation/pdf-set/source-{n}",
            raw_sha256=checksum * 64,
            byte_size=100,
            object_key=f"object-{n}",
            original_source_object_id=f"original-{n}",
            snapshot_id=f"snapshot-{n}",
            snapshot_sha256="d" * 64,
            snapshot_configuration_sha256="c" * 64,
            expected_revision=0,
            expected_current_version_id=None,
            expected_active_set_id=None,
        )
        for n, checksum in ((1, "a"), (2, "b"))
    )
    return CorpusPreparationPlan(
        "corpus-test",
        frozen.to_json(),
        8,
        0,
        "issuer",
        "owner",
        pins,
        PdfSubmissionConfiguration.milestone_two(
            embedding_configuration=EmbeddingConfiguration.cloudflare_qwen3_06b()
        ),
        (digest_json({"documents": ["The sky is blue."]}),),
        2,
    )


def test_plan_requires_exactly_two_ready_gold_sources_and_pins_config():
    plan = plan_fixture()
    assert plan.scope()["purpose"] == "corpus_prepare"
    assert plan.payload()["job_attempts_per_source"] == 1
    for pins in (
        plan.sources[:1],
        (plan.sources[0], plan.sources[0]),
        (replace(plan.sources[0], raw_sha256="f" * 64), plan.sources[1]),
        (replace(plan.sources[0], source_key="unrelated"), plan.sources[1]),
    ):
        with pytest.raises(ValueError, match="CORPUS_PLAN_INVALID"):
            replace(plan, sources=pins)
    assert replace(plan, workspace_revision=1).scope() != plan.scope()
    assert (
        replace(
            plan, sources=(replace(plan.sources[0], expected_revision=1), plan.sources[1])
        ).scope()
        != plan.scope()
    )


def test_plan_cannot_replace_frozen_owner():
    plan = plan_fixture()
    with pytest.raises(ValueError, match="CORPUS_PLAN_INVALID"):
        replace(plan, owner_subject="foreign")


def test_preparation_denies_wrong_scope_before_store_or_handler(tmp_path):
    from types import SimpleNamespace

    from test_live_admission import NOW, approval

    from knora.evaluation.corpus_preparation import prepare_corpus
    from knora.evaluation.live_admission import LiveAdmission

    plan = plan_fixture()
    admission = LiveAdmission(approval(), tmp_path / "journal.sqlite", clock=lambda: NOW)
    with pytest.raises(ValueError, match="LIVE_SCOPE_MISMATCH"):
        prepare_corpus(
            plan,
            admission=admission,
            store=None,
            handler=None,
            provider_client=SimpleNamespace(_knora_live_admission=admission),
            runtime=None,
        )


def test_preparation_denies_handler_using_a_different_provider_client(tmp_path):
    from types import SimpleNamespace

    from test_corpus_preparation import corpus_gate
    from test_live_admission import NOW

    from knora.evaluation.corpus_preparation import prepare_corpus

    plan = plan_fixture()
    seed, _, _ = corpus_gate(tmp_path)
    from knora.evaluation.live_admission import LiveAdmission

    admission = LiveAdmission(
        {**seed._policy, "scope": plan.scope()}, tmp_path / "provider.sqlite", clock=lambda: NOW
    )
    client = SimpleNamespace(_knora_live_admission=admission)
    handler = SimpleNamespace(_embedding_provider=SimpleNamespace(_client=SimpleNamespace()))
    with pytest.raises(ValueError, match="LIVE_APPROVAL_REQUIRED"):
        prepare_corpus(
            plan,
            admission=admission,
            store=None,
            handler=handler,
            provider_client=client,
            runtime=None,
        )
