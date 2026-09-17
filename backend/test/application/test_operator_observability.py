from dataclasses import dataclass

import pytest

from knora.application.operator_observability import OperatorObservability
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.operational_observability import OperationalSnapshot


@dataclass
class TraceReader:
    def read_trace(self, *, trace_id, workspace_id):
        return {
            "trace_id": trace_id,
            "workspace_id": workspace_id,
            "answer": "safe",
            "provider_metadata": {
                "provider_request_id": "request-a",
                "provider_api_key": "TEST_SENTINEL",
                "nested": {
                    "raw_token": "TEST_SENTINEL",
                    "key_hash": "TEST_SENTINEL",
                    "safe": "value",
                },
            },
        }


@dataclass
class OperationsReader:
    def snapshot(self, *, workspace_id):
        return OperationalSnapshot(
            metrics={"queue_depth": 0}, configuration_version="metrics-v1"
        )


@dataclass
class LegacyOperationsReader:
    def snapshot(self):
        return OperationalSnapshot(
            metrics={"queue_depth": 0}, configuration_version="metrics-v1"
        )


def principal(capabilities=None):
    return WorkspacePrincipal("ws-a", "operator", capabilities)


@pytest.mark.parametrize("key", ["AUTHORIZATION", "API_KEY", "providerAPIKey", "RAW_TOKEN"])
def test_trace_removes_credentials_regardless_of_key_case(key):
    class Reader:
        def read_trace(self, **kwargs):
            return {"provider_metadata": [{key: "TEST_SENTINEL", "latency_ms": 2}]}

    service = OperatorObservability(trace_reader=Reader(), operations_reader=OperationsReader())
    result = service.read_trace(trace_id="t", workspace_id="ws-a", principal=principal())
    assert result == {"provider_metadata": [{"latency_ms": 2}]}


def test_trace_preserves_token_observations_while_removing_nested_credentials():
    class Reader:
        def read_trace(self, **kwargs):
            return {"token_usage": {"input_tokens": 12, "output_tokens": 3,
                                    "access_token": "TEST_SENTINEL"}}

    service = OperatorObservability(trace_reader=Reader(), operations_reader=OperationsReader())
    result = service.read_trace(trace_id="t", workspace_id="ws-a", principal=principal())
    assert result == {"token_usage": {"input_tokens": 12, "output_tokens": 3}}


def test_operator_read_requires_operator_capability():
    service = OperatorObservability(
        trace_reader=TraceReader(), operations_reader=OperationsReader()
    )
    with pytest.raises(Exception, match="CAPABILITY_ACCESS_DENIED"):
        service.read_trace(
            trace_id="trace-a", workspace_id="ws-a", principal=principal(())
        )


def test_operator_trace_preserves_workspace_provenance_and_sanitizes_secrets():
    service = OperatorObservability(
        trace_reader=TraceReader(), operations_reader=OperationsReader()
    )
    result = service.read_trace(
        trace_id="trace-a", workspace_id="ws-a", principal=principal(("operator:read",))
    )
    assert result["workspace_id"] == "ws-a"
    assert result["provider_metadata"] == {
        "provider_request_id": "request-a",
        "nested": {"safe": "value"},
    }


def test_operator_operations_distinguishes_zero_metrics_from_missing():
    service = OperatorObservability(
        trace_reader=TraceReader(), operations_reader=OperationsReader()
    )
    result = service.read_operations(workspace_id="ws-a", principal=principal())
    assert result.metrics["queue_depth"] == 0
    assert "retry_rate" not in result.metrics


def test_operator_operations_rejects_unscoped_legacy_snapshot():
    service = OperatorObservability(
        trace_reader=TraceReader(), operations_reader=LegacyOperationsReader()
    )

    with pytest.raises(Exception, match="OPERATOR_OBSERVATION_FAILED"):
        service.read_operations(workspace_id="ws-a", principal=principal())
