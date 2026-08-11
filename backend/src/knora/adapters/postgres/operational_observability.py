"""Authoritative PostgreSQL snapshot source for Operational Metrics V1."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    IngestionJobAttemptTable,
    IngestionJobTable,
    ObjectLifecycleAttemptTable,
    ObjectLifecycleWorkTable,
)
from knora.ingestion.operational_observability import (
    CLAIM_LATENCY_BUCKET_BOUNDARIES_SECONDS,
    OperationalHistogram,
    OperationalSnapshot,
)


class PostgresOperationalMetricsStore:
    def __init__(self, session_factory: sessionmaker, *, retry_window: timedelta) -> None:
        if retry_window <= timedelta(0):
            raise ValueError("retry metric window must be positive")
        self._session_factory = session_factory
        self._retry_window = retry_window

    def snapshot(self) -> OperationalSnapshot:
        with self._session_factory() as session:
            now = session.scalar(select(func.clock_timestamp()))
            if now is None:
                raise RuntimeError("PostgreSQL did not return authoritative metric time")
            eligible = or_(
                IngestionJobTable.status == "queued",
                and_(
                    IngestionJobTable.status == "retry_scheduled",
                    IngestionJobTable.next_attempt_at <= now,
                ),
            )
            queue_depth = session.scalar(
                select(func.count()).select_from(IngestionJobTable).where(eligible)
            )
            oldest_created = session.scalar(
                select(func.min(IngestionJobTable.created_at)).where(eligible)
            )
            oldest_age = 0.0
            if oldest_created is not None:
                oldest_age = max(0.0, (now - oldest_created).total_seconds())
            window_start = now - self._retry_window
            closed_attempts = (
                session.scalar(
                    select(func.count())
                    .select_from(IngestionJobAttemptTable)
                    .where(
                        IngestionJobAttemptTable.closed_at >= window_start,
                        IngestionJobAttemptTable.closed_at <= now,
                    )
                )
                or 0
            )
            retries = (
                session.scalar(
                    select(func.count())
                    .select_from(IngestionJobAttemptTable)
                    .where(
                        IngestionJobAttemptTable.closed_at >= window_start,
                        IngestionJobAttemptTable.closed_at <= now,
                        IngestionJobAttemptTable.retry_policy_result == "schedule_retry",
                    )
                )
                or 0
            )
            metrics: dict[str, int | float] = {
                "queue_depth": int(queue_depth or 0),
                "oldest_job_age": oldest_age,
                "lease_expiry_recovery_total": int(
                    session.scalar(
                        select(func.count())
                        .select_from(IngestionJobAttemptTable)
                        .where(
                            IngestionJobAttemptTable.closed_at.is_not(None),
                            IngestionJobAttemptTable.closure_cause == "lease_expired",
                            IngestionJobAttemptTable.failure_cause == "lease_expired",
                        )
                    )
                    or 0
                ),
                "cleanup_attempt_total": int(
                    session.scalar(select(func.count()).select_from(ObjectLifecycleAttemptTable))
                    or 0
                ),
                "cleanup_failure_total": int(
                    session.scalar(
                        select(func.count())
                        .select_from(ObjectLifecycleAttemptTable)
                        .where(
                            ObjectLifecycleAttemptTable.closed_at.is_not(None),
                            ObjectLifecycleAttemptTable.disposition == "failed",
                        )
                    )
                    or 0
                ),
                "orphan_discovery_total": int(
                    session.scalar(
                        select(func.count())
                        .select_from(ObjectLifecycleWorkTable)
                        .where(
                            ObjectLifecycleWorkTable.artifact_class == "orphan",
                            ObjectLifecycleWorkTable.discovery_recorded_at.is_not(None),
                        )
                    )
                    or 0
                ),
                "orphan_reconciliation_total": int(
                    session.scalar(
                        select(func.count())
                        .select_from(ObjectLifecycleWorkTable)
                        .where(
                            or_(
                                and_(
                                    ObjectLifecycleWorkTable.artifact_class == "orphan",
                                    ObjectLifecycleWorkTable.reconciliation_disposition.in_(
                                        ("repaired", "deleted")
                                    ),
                                ),
                                and_(
                                    ObjectLifecycleWorkTable.artifact_class == "orphan_report",
                                    ObjectLifecycleWorkTable.reconciliation_disposition
                                    == "repaired",
                                ),
                            ),
                            ObjectLifecycleWorkTable.state == "succeeded",
                        )
                    )
                    or 0
                ),
            }
            if closed_attempts:
                metrics["retry_rate"] = retries / closed_attempts
            claim_latency_rows = session.execute(
                select(
                    IngestionJobAttemptTable.ingestion_job_id,
                    IngestionJobAttemptTable.attempt_number,
                    IngestionJobAttemptTable.attempt_started_at,
                    IngestionJobTable.created_at,
                    IngestionJobAttemptTable.retry_next_attempt_at,
                ).join(
                    IngestionJobTable,
                    IngestionJobTable.id == IngestionJobAttemptTable.ingestion_job_id,
                )
            ).all()
            eligibility_by_job_attempt: dict[tuple[str, int], object] = {}
            for job_id, attempt_number, _, _, retry_next in claim_latency_rows:
                eligibility_by_job_attempt[(job_id, attempt_number)] = retry_next
            claim_latencies = []
            for job_id, attempt_number, started, created, _ in claim_latency_rows:
                eligibility = created
                if attempt_number > 1:
                    eligibility = (
                        eligibility_by_job_attempt.get((job_id, attempt_number - 1)) or created
                    )
                claim_latencies.append(max(0.0, (started - eligibility).total_seconds()))
            metrics["claim_latency_count"] = len(claim_latencies)
            metrics["claim_latency_sum"] = sum(claim_latencies)
            histogram = OperationalHistogram(
                count=len(claim_latencies),
                sum=sum(claim_latencies),
                buckets=tuple(
                    (
                        bound,
                        sum(1 for latency in claim_latencies if latency <= bound),
                    )
                    for bound in CLAIM_LATENCY_BUCKET_BOUNDARIES_SECONDS
                ),
            )
            return OperationalSnapshot(
                metrics=metrics,
                configuration_version="metrics-v1",
                histograms={"claim_latency": histogram},
            )
