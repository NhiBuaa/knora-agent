from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select, update

from knora.adapters.postgres.conversation_store import PostgresConversationStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import (
    ConversationTurnTable,
    WorkspaceAdmissionTable,
    WorkspaceTable,
)
from knora.answering.interface import CitationProjection, QuestionResult
from knora.domain.errors import KnoraError


def create_conversation() -> tuple[PostgresConversationStore, str, str]:
    workspace_id = f"turn-workspace-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Conversation Turn Test"))
    store = PostgresConversationStore(SessionFactory)
    conversation = store.create(workspace_id, f"create-{uuid4()}")
    return store, workspace_id, conversation.id


def fingerprint(question: str) -> str:
    normalized_question = " ".join(question.split())
    return sha256(normalized_question.encode("utf-8")).hexdigest()


def submit_turn(
    store: PostgresConversationStore,
    workspace_id: str,
    conversation_id: str,
    idempotency_key: str,
    question: str,
):
    return store.submit_turn(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        idempotency_key=idempotency_key,
        question=question,
        auto_title=" ".join(question.split())[:80] or "New conversation",
        request_fingerprint=fingerprint(question),
    )


def test_turn_schema_has_scoped_idempotency_and_fenced_worker_state() -> None:
    inspector = inspect(SessionFactory.kw["bind"])
    columns = {column["name"]: column for column in inspector.get_columns("conversation_turns")}
    unique_constraints = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("conversation_turns")
    }
    indexes = {index["name"]: index for index in inspector.get_indexes("conversation_turns")}

    assert columns["idempotency_key"]["nullable"] is False
    assert columns["request_fingerprint"]["nullable"] is False
    assert columns["question"]["nullable"] is False
    assert columns["worker_id"]["nullable"] is True
    assert columns["claim_token"]["nullable"] is True
    assert columns["lease_expires_at"]["nullable"] is True
    assert columns["execution_deadline_at"]["nullable"] is True
    assert ("workspace_id", "conversation_id", "idempotency_key") in unique_constraints
    assert indexes["uq_conversation_turns_one_active_per_conversation"]["unique"] is True


def test_concurrent_same_key_submissions_return_one_turn_with_durable_question() -> None:
    store, workspace_id, conversation_id = create_conversation()
    original_question = "  Why  is this archived?  "
    key = f"same-key-{uuid4()}"

    def submit(_index: int):
        return submit_turn(store, workspace_id, conversation_id, key, original_question)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(submit, range(8)))

    turn_ids = {result.turn.id for result in results}
    reloaded = store.get_turn(workspace_id, conversation_id, next(iter(turn_ids)))

    assert len(turn_ids) == 1
    assert sum(not result.replayed for result in results) == 1
    assert reloaded.question == original_question


def test_concurrent_different_keys_admit_only_one_active_turn_per_conversation() -> None:
    store, workspace_id, conversation_id = create_conversation()
    barrier = Barrier(2)

    def submit(key: str) -> str:
        barrier.wait()
        try:
            result = submit_turn(
                store,
                workspace_id,
                conversation_id,
                key,
                f"Question for {key}",
            )
            return "202" if not result.replayed else "200"
        except KnoraError as error:
            if error.code != "CONVERSATION_BUSY":
                raise
            return "409"

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = set(executor.map(submit, (f"key-a-{uuid4()}", f"key-b-{uuid4()}")))

    assert statuses == {"202", "409"}


def test_busy_rejection_does_not_consume_the_second_idempotency_key() -> None:
    store, workspace_id, conversation_id = create_conversation()
    submit_turn(store, workspace_id, conversation_id, "first-key", "First question")

    with pytest.raises(KnoraError, match="CONVERSATION_BUSY"):
        submit_turn(store, workspace_id, conversation_id, "second-key", "Second question")

    with SessionFactory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(ConversationTurnTable)
            .where(
                ConversationTurnTable.workspace_id == workspace_id,
                ConversationTurnTable.conversation_id == conversation_id,
            )
        )

    assert count == 1


def test_different_conversations_can_admit_turns_concurrently() -> None:
    store, workspace_id, first_conversation_id = create_conversation()
    second_conversation = store.create(workspace_id, f"second-{uuid4()}")
    barrier = Barrier(2)

    def submit(conversation_id: str):
        barrier.wait()
        return submit_turn(
            store,
            workspace_id,
            conversation_id,
            f"key-{uuid4()}",
            "What is in this conversation?",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(submit, (first_conversation_id, second_conversation.id))
        )

    assert len({result.turn.id for result in results}) == 2


def test_first_turn_sets_auto_title_without_overwriting_manual_title() -> None:
    store, workspace_id, conversation_id = create_conversation()
    auto_question = "  How   many chapters?  "
    submit_turn(store, workspace_id, conversation_id, "auto-title-key", auto_question)
    auto_title = store.get(workspace_id, conversation_id)

    manual_conversation = store.create(workspace_id, f"manual-{uuid4()}")
    manually_renamed = store.mutate(
        workspace_id,
        manual_conversation.id,
        manual_conversation.revision,
        title="My title",
    )
    submit_turn(
        store,
        workspace_id,
        manual_conversation.id,
        "manual-title-key",
        auto_question,
    )
    manual_after_first_turn = store.get(workspace_id, manual_conversation.id)

    assert auto_title.title == "How many chapters?"
    assert auto_title.title_source == "auto"
    assert manually_renamed.title_source == "manual"
    assert manual_after_first_turn.title == "My title"


def test_replay_after_workspace_archive_returns_the_admitted_turn() -> None:
    store, workspace_id, conversation_id = create_conversation()
    original_question = "Why is this archived?"
    first = submit_turn(store, workspace_id, conversation_id, "archive-replay", original_question)
    with SessionFactory.begin() as session:
        session.execute(
            update(WorkspaceTable)
            .where(WorkspaceTable.id == workspace_id)
            .values(archived=True)
        )

    replay = submit_turn(store, workspace_id, conversation_id, "archive-replay", original_question)

    assert replay.replayed is True
    assert replay.turn.id == first.turn.id
    assert replay.turn.question == original_question
    with pytest.raises(KnoraError, match="IDEMPOTENCY_CONFLICT"):
        submit_turn(store, workspace_id, conversation_id, "archive-replay", "Changed payload")
    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        submit_turn(store, workspace_id, conversation_id, "new-key", "A new question")


def test_admitted_turn_finishes_after_archive_and_closes_its_admission() -> None:
    store, workspace_id, conversation_id = create_conversation()
    submission = submit_turn(
        store, workspace_id, conversation_id, "admitted-before-archive", "Why is this archived?"
    )
    with SessionFactory.begin() as session:
        session.execute(
            update(WorkspaceTable)
            .where(WorkspaceTable.id == workspace_id)
            .values(archived=True)
        )

    claim = store.claim_next_turn("worker-1", workspace_id=workspace_id)
    result = QuestionResult(
        decision="REFUSAL",
        answer=None,
        citations=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
        trace_id="trace-1",
        workspace_id=workspace_id,
    )
    finalized = store.finish_turn(
        turn_id=claim.turn.id,
        claim_token=claim.claim_token,
        result=result,
        error_code=None,
    )
    reloaded = store.get_turn(workspace_id, conversation_id, submission.turn.id)
    with SessionFactory() as session:
        admission = session.scalar(
            select(WorkspaceAdmissionTable).where(
                WorkspaceAdmissionTable.workspace_id == workspace_id,
                WorkspaceAdmissionTable.operation == "conversation_turn",
                WorkspaceAdmissionTable.operation_id == submission.turn.id,
            )
        )

    assert claim.turn.id == submission.turn.id
    assert finalized is True
    assert reloaded.question == "Why is this archived?"
    assert reloaded.status == "refused"
    assert admission.terminal_at is not None


def test_stale_claim_token_cannot_finalize_turn() -> None:
    store, workspace_id, conversation_id = create_conversation()
    submission = submit_turn(store, workspace_id, conversation_id, "fenced-key", "Question")
    claim = store.claim_next_turn("worker-1", workspace_id=workspace_id)
    result = QuestionResult(
        decision="REFUSAL",
        answer=None,
        citations=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
        trace_id="trace-2",
        workspace_id=workspace_id,
    )

    stale_completion = store.finish_turn(
        turn_id=submission.turn.id,
        claim_token="stale-token",
        result=result,
        error_code=None,
    )
    current_completion = store.finish_turn(
        turn_id=claim.turn.id,
        claim_token=claim.claim_token,
        result=result,
        error_code=None,
    )

    assert stale_completion is False
    assert current_completion is True


def test_terminal_turn_round_trips_the_validated_citation_projection() -> None:
    store, workspace_id, conversation_id = create_conversation()
    submission = submit_turn(
        store,
        workspace_id,
        conversation_id,
        "citation-key",
        "How many chapters?",
    )
    claim = store.claim_next_turn("worker-1", workspace_id=workspace_id)
    result = QuestionResult(
        decision="ANSWER",
        answer="The report is suggested to have seven chapters.",
        citations=(
            CitationProjection(
                evidence_id="E1",
                document_id="document-1",
                document_version_id="version-1",
                source_key="guidelines.pdf",
                source_name="Guidelines.pdf",
                heading_path=("Report structure",),
                start_line=12,
                end_line=14,
                excerpt="The report is suggested to have seven chapters.",
                content_checksum="sha256:chunk-1",
            ),
        ),
        refusal_reason=None,
        trace_id="trace-citation-1",
        workspace_id=workspace_id,
    )

    assert store.finish_turn(
        turn_id=claim.turn.id,
        claim_token=claim.claim_token,
        result=result,
        error_code=None,
    ) is True
    reloaded = store.get_turn(workspace_id, conversation_id, submission.turn.id)

    assert reloaded.result == result


def test_archiving_and_restoring_conversation_preserves_turn_history() -> None:
    store, workspace_id, conversation_id = create_conversation()
    submission = submit_turn(
        store, workspace_id, conversation_id, "restore-key", "Original question"
    )
    archived = store.mutate(workspace_id, conversation_id, 0, archived=True)
    restored = store.mutate(
        workspace_id,
        conversation_id,
        archived.revision,
        archived=False,
    )
    history = store.list_turns(workspace_id, conversation_id)

    assert restored.archived is False
    assert [turn.id for turn in history.items] == [submission.turn.id]
    assert history.items[0].question == "Original question"


def test_expired_worker_lease_is_interrupted_and_busy_slot_is_released() -> None:
    store, workspace_id, conversation_id = create_conversation()
    submission = submit_turn(store, workspace_id, conversation_id, "expired-key", "Question")
    claim = store.claim_next_turn("worker-1", workspace_id=workspace_id)
    with SessionFactory.begin() as session:
        session.execute(
            update(ConversationTurnTable)
            .where(ConversationTurnTable.id == submission.turn.id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
        )

    observations = store.expired_turns()
    recovered = sum(
        store.apply_expired_turn_recovery(observation, None) for observation in observations
    )
    interrupted = store.get_turn(workspace_id, conversation_id, submission.turn.id)
    with SessionFactory() as session:
        admission = session.scalar(
            select(WorkspaceAdmissionTable).where(
                WorkspaceAdmissionTable.workspace_id == workspace_id,
                WorkspaceAdmissionTable.operation == "conversation_turn",
                WorkspaceAdmissionTable.operation_id == submission.turn.id,
            )
        )
    next_turn = submit_turn(
        store,
        workspace_id,
        conversation_id,
        "after-interruption",
        "A new explicit question",
    )

    assert recovered == 1
    assert interrupted.status == "interrupted"
    assert interrupted.error_code == "EXECUTION_OUTCOME_UNKNOWN"
    assert admission.terminal_at is not None
    assert next_turn.turn.id != claim.turn.id
    assert next_turn.turn.status == "queued"
