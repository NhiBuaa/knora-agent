from __future__ import annotations

import asyncio
from contextlib import suppress

from knora.answering.interface import QuestionCommand, QuestionResult
from knora.answering.module import AnswerQuestion
from knora.conversations.ports import ConversationResultReader, ConversationStore
from knora.conversations.types import ClaimedTurn
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError

_HEARTBEAT_SECONDS = 10
_EXECUTION_DEADLINE_SECONDS = 120
_IDLE_SLEEP_SECONDS = 0.5


class ConversationRunner:
    """Claim and execute durable Conversation Turns without holding DB locks."""

    def __init__(
        self,
        *,
        store: ConversationStore,
        answer_question: AnswerQuestion,
        result_reader: ConversationResultReader | None = None,
    ) -> None:
        self._store = store
        self._answer_question = answer_question
        self._result_reader = result_reader

    async def run_once(self, *, worker_id: str, workspace_id: str | None = None) -> bool:
        await self._recover_expired_turns()
        claim = await asyncio.to_thread(
            self._store.claim_next_turn,
            worker_id,
            workspace_id,
        )
        if claim is None:
            return False
        return await self._execute_claim(claim)

    async def run_forever(self, *, worker_id: str, workspace_id: str | None = None) -> None:
        while True:
            worked = await self.run_once(worker_id=worker_id, workspace_id=workspace_id)
            if not worked:
                await asyncio.sleep(_IDLE_SLEEP_SECONDS)

    async def _execute_claim(self, claim: ClaimedTurn) -> bool:
        command = QuestionCommand(
            workspace_id=claim.workspace_id,
            question=claim.turn.question,
            turn_id=claim.turn.id,
        )
        principal = WorkspacePrincipal(
            workspace_id=claim.workspace_id,
            key_id=f"conversation-worker:{claim.worker_id}",
            capabilities=("questions:ask",),
        )
        stage_tasks: set[asyncio.Task[bool]] = set()

        def stage_callback(stage: str) -> None:
            task = asyncio.create_task(
                asyncio.to_thread(
                    self._store.set_turn_stage,
                    claim.turn.id,
                    claim.claim_token,
                    stage,
                )
            )
            stage_tasks.add(task)

            def consume_stage_update(completed: asyncio.Task[bool]) -> None:
                stage_tasks.discard(completed)
                with suppress(Exception):
                    completed.result()

            task.add_done_callback(consume_stage_update)

        answer_task = asyncio.create_task(
            self._answer_question.execute(
                command,
                principal,
                workspace_admission=claim.workspace_admission,
                stage_callback=stage_callback,
            )
        )
        heartbeat_task = asyncio.create_task(self._heartbeat(claim))
        done, _ = await asyncio.wait(
            (answer_task, heartbeat_task),
            timeout=_EXECUTION_DEADLINE_SECONDS,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if answer_task in done:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            await self._wait_for_stage_updates(stage_tasks)
            return await self._finalize_answer(claim, answer_task)

        if heartbeat_task in done:
            with suppress(Exception):
                heartbeat_task.result()
            await self._recover_expired_turns()
            await self._drain_answer(answer_task)
            await self._wait_for_stage_updates(stage_tasks)
            return False

        # The deadline is advisory; PostgreSQL decides when the lease/deadline has expired.
        # Keep this worker slot until the provider call physically returns, but never publish
        # a late result after recovery has terminalized the Turn.
        await self._wait_until_terminal(claim)
        await self._drain_answer(answer_task)
        await self._wait_for_stage_updates(stage_tasks)
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task
        return False

    async def _heartbeat(self, claim: ClaimedTurn) -> bool:
        while True:
            await asyncio.sleep(_HEARTBEAT_SECONDS)
            extended = await asyncio.to_thread(
                self._store.heartbeat_turn,
                claim.turn.id,
                claim.claim_token,
            )
            if not extended:
                return False

    async def _finalize_answer(
        self,
        claim: ClaimedTurn,
        answer_task: asyncio.Task[QuestionResult],
    ) -> bool:
        try:
            result = answer_task.result()
        except KnoraError as error:
            return await asyncio.to_thread(
                self._store.finish_turn,
                claim.turn.id,
                claim.claim_token,
                None,
                error.code,
            )
        except Exception:
            return await asyncio.to_thread(
                self._store.finish_turn,
                claim.turn.id,
                claim.claim_token,
                None,
                "CONVERSATION_EXECUTION_FAILED",
            )
        return await asyncio.to_thread(
            self._store.finish_turn,
            claim.turn.id,
            claim.claim_token,
            result,
            None,
        )

    async def _wait_until_terminal(self, claim: ClaimedTurn) -> None:
        while True:
            await self._recover_expired_turns()
            current = await asyncio.to_thread(
                self._store.get_turn,
                claim.workspace_id,
                claim.turn.conversation_id,
                claim.turn.id,
            )
            if current is None or current.status != "processing":
                return
            await asyncio.sleep(0.1)

    async def _recover_expired_turns(self) -> None:
        observations = await asyncio.to_thread(self._store.expired_turns)
        for observation in observations:
            result = None
            if self._result_reader is not None:
                result = await asyncio.to_thread(
                    self._result_reader.read_conversation_result,
                    observation.workspace_id,
                    observation.turn_id,
                )
            await asyncio.to_thread(
                self._store.apply_expired_turn_recovery,
                observation,
                result,
            )

    @staticmethod
    async def _drain_answer(answer_task: asyncio.Task[QuestionResult]) -> None:
        with suppress(asyncio.CancelledError, Exception):
            await answer_task

    @staticmethod
    async def _wait_for_stage_updates(stage_tasks: set[asyncio.Task[bool]]) -> None:
        if stage_tasks:
            await asyncio.gather(*tuple(stage_tasks), return_exceptions=True)
