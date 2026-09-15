from knora.adapters.postgres.operator_reader import PostgresOperatorReader


class FakeEvaluationReader:
    def read_trace(self, *, trace_id, workspace_id):
        return (trace_id, workspace_id)


def test_operator_reader_exposes_a_report_id_evaluation_boundary() -> None:
    reader = PostgresOperatorReader.__new__(PostgresOperatorReader)
    reader._reader = FakeEvaluationReader()
    assert reader.read_evaluation(report_id="report", workspace_id="workspace") == (
        "report",
        "workspace",
    )
