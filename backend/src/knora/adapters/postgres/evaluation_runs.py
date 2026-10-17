"""PostgreSQL run persistence with one fenced execution attempt per run."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from knora.adapters.postgres.evaluation_runs_tables import (
    EvaluationPreflightTable,
    EvaluationRunTable,
)
from knora.domain.errors import KnoraError


class PostgresEvaluationRunStore:
    def __init__(self, session_factory) -> None:
        self._sessions = session_factory

    def save_preflight(self, value: dict) -> None:
        with self._sessions.begin() as session:
            session.add(
                EvaluationPreflightTable(
                    preflight_id=value["preflight_id"],
                    workspace_id=value["workspace_id"],
                    payload=value,
                    expires_at=datetime.fromisoformat(value["expires_at"]),
                )
            )

    def get_preflight(self, workspace_id: str, preflight_id: str) -> dict | None:
        with self._sessions() as session:
            row = session.get(EvaluationPreflightTable, preflight_id)
            return row.payload if row is not None and row.workspace_id == workspace_id else None

    @staticmethod
    def _project(row: EvaluationRunTable, now=None) -> dict:
        status = row.execution_status
        if status == "RUNNING" and now is not None and row.started_at is not None:
            started = row.started_at
            if (
                getattr(now, "tzinfo", None) is None
                and getattr(started, "tzinfo", None) is not None
            ):
                started = started.replace(tzinfo=None)
            if now - started > timedelta(minutes=10):
                status = "INDETERMINATE"
        return {
            "run_id": row.run_id,
            "workspace_id": row.workspace_id,
            "request_digest": row.request_digest,
            "selection_digest": row.selection_digest,
            "selection": row.selection,
            "profile_id": row.profile_id,
            "binding": row.binding,
            "execution_status": status,
            "quality_status": row.quality_status,
            "observations": row.observations,
            "report": row.report,
            "scoring_batches": row.scoring_batches,
        }

    def create(self, run: dict, key: str) -> dict:
        with self._sessions.begin() as session:
            existing = session.scalar(
                select(EvaluationRunTable).where(
                    EvaluationRunTable.workspace_id == run["workspace_id"],
                    EvaluationRunTable.idempotency_key == key,
                )
            )
            if existing is not None:
                if existing.request_digest != run["request_digest"]:
                    raise KnoraError("EVALUATION_IDEMPOTENCY_CONFLICT")
                return self._project(existing)
            session.add(EvaluationRunTable(idempotency_key=key, **run))
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                with self._sessions() as retry:
                    existing = retry.scalar(
                        select(EvaluationRunTable).where(
                            EvaluationRunTable.workspace_id == run["workspace_id"],
                            EvaluationRunTable.idempotency_key == key,
                        )
                    )
                    if existing is None:
                        raise
                    if existing.request_digest != run["request_digest"]:
                        raise KnoraError("EVALUATION_IDEMPOTENCY_CONFLICT") from None
                    return self._project(existing)
            return run

    def get(self, workspace_id: str, run_id: str) -> dict | None:
        with self._sessions() as session:
            row = session.get(EvaluationRunTable, run_id)
            if row is None or row.workspace_id != workspace_id:
                return None
            return self._project(row, session.scalar(select(func.now())))

    def list(self, workspace_id: str) -> list[dict]:
        with self._sessions() as session:
            now = session.scalar(select(func.now()))
            rows = session.scalars(
                select(EvaluationRunTable)
                .where(EvaluationRunTable.workspace_id == workspace_id)
                .order_by(EvaluationRunTable.created_at.desc(), EvaluationRunTable.run_id.desc())
                .limit(100)
            ).all()
            return [self._project(row, now) for row in rows]

    def claim(self, workspace_id: str, run_id: str) -> str | None:
        attempt_id = uuid4().hex
        with self._sessions.begin() as session:
            result = session.execute(
                update(EvaluationRunTable)
                .where(
                    EvaluationRunTable.workspace_id == workspace_id,
                    EvaluationRunTable.run_id == run_id,
                    EvaluationRunTable.execution_status == "QUEUED",
                )
                .values(execution_status="RUNNING", attempt_id=attempt_id, started_at=func.now())
            )
            return attempt_id if result.rowcount == 1 else None

    def checkpoint(
        self, workspace_id: str, run_id: str, attempt_id: str, case_id: str, observation: dict
    ) -> None:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(EvaluationRunTable)
                .where(
                    EvaluationRunTable.workspace_id == workspace_id,
                    EvaluationRunTable.run_id == run_id,
                )
                .with_for_update()
            )
            if row is None or row.execution_status != "RUNNING" or row.attempt_id != attempt_id:
                raise KnoraError("EVALUATION_ATTEMPT_STALE")
            if case_id not in row.observations or row.observations[case_id]["status"] != "NOT_RUN":
                raise KnoraError("EVALUATION_CHECKPOINT_CONFLICT")
            row.observations = {**row.observations, case_id: observation}

    def finish(
        self, workspace_id: str, run_id: str, attempt_id: str, status: str, report: dict | None
    ) -> None:
        if status not in {"COMPLETED", "BLOCKED", "INDETERMINATE"}:
            raise ValueError("Invalid terminal run status")
        with self._sessions.begin() as session:
            row = session.scalar(
                select(EvaluationRunTable)
                .where(
                    EvaluationRunTable.workspace_id == workspace_id,
                    EvaluationRunTable.run_id == run_id,
                )
                .with_for_update()
            )
            if row is None or row.execution_status != "RUNNING" or row.attempt_id != attempt_id:
                raise KnoraError("EVALUATION_ATTEMPT_STALE")
            row.execution_status = status
            row.quality_status = report["quality_status"] if report else "UNAVAILABLE"
            row.report = report
            row.finished_at = func.now()

    def reserve_scoring_batch(
        self, workspace_id: str, run_id: str, batch: dict
    ) -> tuple[dict, bool]:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(EvaluationRunTable)
                .where(
                    EvaluationRunTable.workspace_id == workspace_id,
                    EvaluationRunTable.run_id == run_id,
                )
                .with_for_update()
            )
            if row is None:
                raise KnoraError("EVALUATION_RUN_NOT_FOUND")
            for previous in row.scoring_batches:
                if previous["request_id"] == batch["request_id"]:
                    if previous["request_digest"] != batch["request_digest"]:
                        raise KnoraError("EVALUATION_IDEMPOTENCY_CONFLICT")
                    return previous, False
            row.scoring_batches = [*row.scoring_batches, batch]
            return batch, True

    def checkpoint_scoring_batch(self, workspace_id: str, run_id: str, batch: dict) -> dict:
        with self._sessions.begin() as session:
            row = session.scalar(
                select(EvaluationRunTable)
                .where(
                    EvaluationRunTable.workspace_id == workspace_id,
                    EvaluationRunTable.run_id == run_id,
                )
                .with_for_update()
            )
            if row is None:
                raise KnoraError("EVALUATION_RUN_NOT_FOUND")
            previous = next((b for b in row.scoring_batches if b["id"] == batch["id"]), None)
            if (
                previous is None
                or previous["status"] != "INDETERMINATE"
                or previous["request_digest"] != batch["request_digest"]
            ):
                raise KnoraError("EVALUATION_CHECKPOINT_CONFLICT")
            row.scoring_batches = [
                batch if b["id"] == batch["id"] else b for b in row.scoring_batches
            ]
            return batch
