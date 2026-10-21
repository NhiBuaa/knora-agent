"""Operator diagnostics retain invalid generation without weakening evaluation."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from backend.test.answering import test_bm25_contract as contract

from knora.adapters.postgres import evaluation_reader as evaluation
from knora.adapters.postgres.operator_reader import PostgresOperatorReader
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult


async def invalid_trace(monkeypatch, answer="Fact [[E99]]"):
    async def invalid(self, *, question, evidence):
        return GenerationResult(
            decision="ANSWER",
            answer=answer,
            cited_evidence_ids=("E99",),
            refusal_reason=None,
            provider="deterministic-local",
            model="offline-stub",
            prompt_version="offline-observation",
        )

    monkeypatch.setattr(contract.LocalGenerator, "generate", invalid)
    store = contract.LexicalStore()
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await contract.execute(store)
    return store


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["Fact [[E99]]", "Fact [[E1]]"])
async def test_operator_opt_in_keeps_real_invalid_trace_labeled_invalid(monkeypatch, answer):
    store = await invalid_trace(monkeypatch, answer)
    arguments = dict(
        trace_id="trace-1",
        record=store.traces[0],
        candidates=contract.projections(store),
        authorized_generations=(contract.generation(),),
    )
    with pytest.raises(LookupError, match="lexical"):
        evaluation.project_bm25_trace(**arguments)
    projected = evaluation.project_bm25_trace(**arguments, include_invalid_generation=True)
    assert projected.validation_outcome == "invalid"
    assert projected.answer == answer
    assert projected.alias_mapping == {"E1": "chunk-1"}
    assert projected.parsed_markers == store.traces[0].parsed_markers


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["workspace", "authority", "alias", "state", "markers"])
async def test_invalid_operator_trace_still_rejects_provenance_drift(monkeypatch, drift):
    store = await invalid_trace(monkeypatch)
    record = store.traces[0]
    authority = (contract.generation(),)
    if drift == "workspace":
        record = replace(record, workspace_id="foreign")
    elif drift == "authority":
        authority = (replace(authority[0], index_generation_id="different"),)
    elif drift == "alias":
        record = replace(record, alias_mapping={"E1": "foreign"})
    elif drift == "state":
        record = replace(record, generation_status="not_called")
    else:
        record = replace(record, parsed_markers=("E1",))
    with pytest.raises(LookupError, match="lexical"):
        evaluation.project_bm25_trace(
            trace_id="trace-1",
            record=record,
            candidates=contract.projections(store),
            authorized_generations=authority,
            include_invalid_generation=True,
        )


@pytest.mark.asyncio
async def test_operator_selects_invalid_mode_while_evaluation_default_remains_strict(monkeypatch):
    store = await invalid_trace(monkeypatch)

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def scalar(self, statement):
            return SimpleNamespace(trace_schema_version=3)

    def read_snapshot(self, session, trace, workspace_id):
        assert workspace_id == "workspace"
        return evaluation.project_bm25_trace(
            trace_id="trace-1",
            record=store.traces[0],
            candidates=contract.projections(store),
            authorized_generations=(contract.generation(),),
            include_invalid_generation=self._include_invalid_generation,
        )

    monkeypatch.setattr(evaluation.PostgresEvaluationReader, "_read_bm25_trace", read_snapshot)
    operator = PostgresOperatorReader(Session)
    assert (
        operator.read_trace(trace_id="trace-1", workspace_id="workspace").validation_outcome
        == "invalid"
    )
    with pytest.raises(LookupError, match="lexical"):
        evaluation.PostgresEvaluationReader(Session).read_trace(
            trace_id="trace-1", workspace_id="workspace"
        )
