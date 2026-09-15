from dataclasses import dataclass

import pytest

from knora.application.operator_observability import OperatorObservability
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.operational_observability import OperationalSnapshot


@dataclass
class TraceReader:
    def read_trace(self, *, trace_id, workspace_id):
        return {"trace_id": trace_id, "workspace_id": workspace_id, "answer": "safe"}


@dataclass
class OperationsReader:
    def snapshot(self):
        return OperationalSnapshot(
            metrics={"queue_depth": 0}, configuration_version="metrics-v1"
        )


def principal(capabilities=None):
    return WorkspacePrincipal("ws-a", "operator", capabilities)


def test_operator_read_requires_operator_capability():
    service = OperatorObservability(trace_reader=TraceReader(), operations_reader=OperationsReader())
    with pytest.raises(Exception, match="CAPABILITY_ACCESS_DENIED"):
        service.read_trace(
            trace_id="trace-a", workspace_id="ws-a", principal=principal(())
        )


def test_operator_trace_preserves_workspace_provenance_and_sanitizes_secrets():
    service = OperatorObservability(trace_reader=TraceReader(), operations_reader=OperationsReader())
    result = service.read_trace(
        trace_id="trace-a", workspace_id="ws-a", principal=principal(("operator:read",))
    )
    assert result["workspace_id"] == "ws-a"
    assert "api_key" not in result


def test_operator_operations_distinguishes_zero_metrics_from_missing():
    service = OperatorObservability(trace_reader=TraceReader(), operations_reader=OperationsReader())
    result = service.read_operations(workspace_id="ws-a", principal=principal())
    assert result.metrics["queue_depth"] == 0
    assert "retry_rate" not in result.metrics
