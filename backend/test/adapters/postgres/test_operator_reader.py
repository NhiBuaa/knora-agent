from knora.adapters.postgres.operator_reader import PostgresOperatorReader


def test_operator_reader_exposes_unavailable_evaluation_without_trace_lookup() -> None:
    reader = PostgresOperatorReader.__new__(PostgresOperatorReader)
    reader._reader = object()
    projection = reader.read_evaluation(report_id="report", workspace_id="workspace")
    assert projection.report_id == "report"
    assert projection.workspace_id == "workspace"
    assert projection.availability == "unavailable"
    assert projection.observation_failure == "EVALUATION_REPORT_UNAVAILABLE"
