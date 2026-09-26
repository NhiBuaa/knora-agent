from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from importlib import import_module
from types import SimpleNamespace

import pytest

from knora.answering.interface import QuestionResult
from knora.conversations.types import ClaimedTurn, TurnView
from knora.workspaces.ports import WorkspaceAdmission


class ExpiredConversationStore:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.observation = SimpleNamespace(
            turn_id="turn-expired",
            workspace_id="workspace-1",
            conversation_id="conversation-1",
            claim_token="claim-expired",
            observed_lease_expires_at=datetime(2026, 9, 26, tzinfo=UTC),
            observed_execution_deadline_at=datetime(2026, 9, 26, tzinfo=UTC),
        )

    def expired_turns(self, limit: int = 100):
        self.calls.append(("expired_turns", limit))
        return (self.observation,)

    def apply_expired_turn_recovery(self, observation, result) -> bool:
        self.calls.append(("apply_expired_turn_recovery", observation, result))
        return True

    def claim_next_turn(self, worker_id: str, workspace_id: str | None = None):
        self.calls.append(("claim_next_turn", worker_id, workspace_id))
        return None


class AnswerQuestionMustNotRun:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("expired uncertain work must not call the provider again")


def conversation_runner_class():
    try:
        return import_module("knora.conversations.runner").ConversationRunner
    except ModuleNotFoundError as error:
        pytest.fail(f"Conversation runner is not implemented: {error}", pytrace=False)


@pytest.mark.asyncio
async def test_expired_uncertain_turn_is_recovered_without_provider_retry() -> None:
    store = ExpiredConversationStore()
    answer_question = AnswerQuestionMustNotRun()
    runner = conversation_runner_class()(
        store=store,
        answer_question=answer_question,
    )

    await runner.run_once(worker_id="worker-1")

    assert store.calls == [
        ("expired_turns", 100),
        ("apply_expired_turn_recovery", store.observation, None),
        ("claim_next_turn", "worker-1", None),
    ]
    assert answer_question.calls == []


class ClaimedTurnStore:
    def __init__(self, claim: ClaimedTurn) -> None:
        self.claim = claim
        self.calls: list[tuple] = []

    def expired_turns(self, limit: int = 100):
        self.calls.append(("expired_turns", limit))
        return ()

    def apply_expired_turn_recovery(self, observation, result) -> bool:
        self.calls.append(("apply_expired_turn_recovery", observation, result))
        return True

    def claim_next_turn(self, worker_id: str, workspace_id: str | None = None):
        self.calls.append(("claim_next_turn", worker_id, workspace_id))
        return self.claim

    def set_turn_stage(self, turn_id: str, claim_token: str, stage: str) -> bool:
        self.calls.append(("set_turn_stage", turn_id, claim_token, stage))
        return True

    def finish_turn(
        self,
        turn_id: str,
        claim_token: str,
        result: QuestionResult | None,
        error_code: str | None,
    ) -> bool:
        self.calls.append(("finish_turn", turn_id, claim_token, result, error_code))
        return True


class RecordingAnswerQuestion:
    def __init__(self, result: QuestionResult) -> None:
        self.result = result
        self.calls: list[tuple] = []

    async def execute(self, command, principal, *, workspace_admission, stage_callback):
        self.calls.append((command, principal, workspace_admission))
        stage_callback("retrieving")
        return self.result


@pytest.mark.asyncio
async def test_claimed_turn_passes_existing_admission_and_persists_validated_result() -> None:
    now = datetime(2026, 9, 26, tzinfo=UTC)
    admission = WorkspaceAdmission(
        id="admission-1",
        workspace_id="workspace-1",
        operation="conversation_turn",
        operation_id="turn-1",
        admitted_at=now,
    )
    turn = TurnView(
        id="turn-1",
        conversation_id="conversation-1",
        sequence=1,
        question="What is the first question?",
        status="processing",
        stage=None,
        result=None,
        error_code=None,
    )
    claim = ClaimedTurn(
        turn=turn,
        workspace_id="workspace-1",
        worker_id="worker-1",
        claim_token="claim-1",
        lease_expires_at=now + timedelta(seconds=60),
        execution_deadline_at=now + timedelta(seconds=120),
        workspace_admission=admission,
    )
    result = QuestionResult(
        decision="REFUSAL",
        answer=None,
        citations=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
        trace_id="trace-1",
        workspace_id="workspace-1",
    )
    store = ClaimedTurnStore(claim)
    answer_question = RecordingAnswerQuestion(result)
    runner = conversation_runner_class()(store=store, answer_question=answer_question)

    completed = await runner.run_once(worker_id="worker-1")

    command, principal, forwarded_admission = answer_question.calls[0]
    assert completed is True
    assert command.turn_id == "turn-1"
    assert command.question == "What is the first question?"
    assert principal.workspace_id == "workspace-1"
    assert forwarded_admission is admission
    assert store.calls[-1] == ("finish_turn", "turn-1", "claim-1", result, None)


@pytest.mark.asyncio
async def test_expired_turn_recovers_validated_trace_without_provider_retry() -> None:
    store = ExpiredConversationStore()
    result = QuestionResult(
        decision="ANSWER",
        answer="A validated answer.",
        citations=(),
        refusal_reason=None,
        trace_id="trace-1",
        workspace_id="workspace-1",
    )

    class ResultReader:
        def read_conversation_result(self, workspace_id: str, turn_id: str):
            assert workspace_id == "workspace-1"
            assert turn_id == "turn-expired"
            return result

    answer_question = AnswerQuestionMustNotRun()
    runner = conversation_runner_class()(
        store=store,
        answer_question=answer_question,
        result_reader=ResultReader(),
    )

    await runner.run_once(worker_id="worker-1")

    assert store.calls[1] == ("apply_expired_turn_recovery", store.observation, result)
    assert answer_question.calls == []


@pytest.mark.asyncio
async def test_heartbeat_loss_uses_two_phase_recovery_and_discards_late_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_module = import_module("knora.conversations.runner")
    monkeypatch.setattr(runner_module, "_HEARTBEAT_SECONDS", 0)
    now = datetime(2026, 9, 26, tzinfo=UTC)
    admission = WorkspaceAdmission(
        id="admission-2",
        workspace_id="workspace-1",
        operation="conversation_turn",
        operation_id="turn-2",
        admitted_at=now,
    )
    turn = TurnView(
        id="turn-2",
        conversation_id="conversation-1",
        sequence=2,
        question="Late answer question",
        status="processing",
        stage="generating",
        result=None,
        error_code=None,
    )
    claim = ClaimedTurn(
        turn=turn,
        workspace_id="workspace-1",
        worker_id="worker-1",
        claim_token="claim-2",
        lease_expires_at=now + timedelta(seconds=60),
        execution_deadline_at=now + timedelta(seconds=120),
        workspace_admission=admission,
    )
    observation = SimpleNamespace(
        turn_id="turn-2",
        workspace_id="workspace-1",
        conversation_id="conversation-1",
        claim_token="claim-2",
        observed_lease_expires_at=now,
        observed_execution_deadline_at=now,
    )

    class LostHeartbeatStore:
        def __init__(self) -> None:
            self.calls: list[tuple] = []
            self.expiry_reads = 0

        def expired_turns(self, limit: int = 100):
            self.expiry_reads += 1
            self.calls.append(("expired_turns", limit))
            return () if self.expiry_reads == 1 else (observation,)

        def apply_expired_turn_recovery(self, expired, result) -> bool:
            self.calls.append(("apply_expired_turn_recovery", expired, result))
            return True

        def claim_next_turn(self, worker_id: str, workspace_id: str | None = None):
            self.calls.append(("claim_next_turn", worker_id, workspace_id))
            return claim

        def heartbeat_turn(self, turn_id: str, claim_token: str) -> bool:
            self.calls.append(("heartbeat_turn", turn_id, claim_token))
            return False

        def finish_turn(self, *args, **kwargs):
            raise AssertionError("late result must not finalize a fenced Turn")

    class LateAnswerQuestion:
        async def execute(self, command, principal, *, workspace_admission, stage_callback):
            await asyncio.sleep(0.05)
            return QuestionResult(
                decision="ANSWER",
                answer="Late result",
                citations=(),
                refusal_reason=None,
                trace_id="trace-late",
                workspace_id=command.workspace_id,
            )

    store = LostHeartbeatStore()
    runner = runner_module.ConversationRunner(
        store=store,
        answer_question=LateAnswerQuestion(),
    )

    completed = await runner.run_once(worker_id="worker-1")

    assert completed is False
    assert any(call[0] == "apply_expired_turn_recovery" for call in store.calls)
    assert not any(call[0] == "finish_turn" for call in store.calls)
