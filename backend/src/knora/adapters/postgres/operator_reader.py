"""PostgreSQL adapter for operator-facing read projections."""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.application.operator_observability import OperatorEvaluationResponse
from knora.ingestion.lexical_population import VerifiedLexicalPopulation


class PostgresOperatorReader:
    """Expose the operator read seam without coupling it to evaluation internals."""

    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        lexical_population: VerifiedLexicalPopulation | None = None,
    ) -> None:
        self._reader = PostgresEvaluationReader(
            session_factory, lexical_population=lexical_population
        )

    def read_trace(self, *, trace_id: str, workspace_id: str) -> object:
        return self._reader.read_trace(trace_id=trace_id, workspace_id=workspace_id)

    def read_evaluation(self, *, report_id: str, workspace_id: str) -> object:
        return OperatorEvaluationResponse(report_id=report_id, workspace_id=workspace_id)
