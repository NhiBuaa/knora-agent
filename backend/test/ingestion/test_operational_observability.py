import json
from dataclasses import dataclass, field, replace

import pytest

from knora.ingestion.operational_observability import (
    AlertPolicyV1,
    OperationalAlert,
    OperationalAlertConfigurationV1,
    OperationalAlertDefinition,
    OperationalHistogram,
    OperationalObservability,
    OperationalSnapshot,
)


@dataclass
class Store:
    value: OperationalSnapshot

    def snapshot(self) -> OperationalSnapshot:
        return self.value


@dataclass
class Telemetry:
    snapshots: list[OperationalSnapshot] = field(default_factory=list)
    alerts: list[OperationalAlert] = field(default_factory=list)

    def publish_snapshot(self, snapshot: OperationalSnapshot) -> None:
        self.snapshots.append(snapshot)

    def publish_alert(self, alert: OperationalAlert) -> None:
        self.alerts.append(alert)


def test_alert_configuration_requires_all_issue_20_classes_and_emits_typed_alert() -> None:
    classes = (
        "queue_age_contention",
        "repeated_lease_expiry_recovery",
        "cleanup_backlog",
        "unreconciled_orphan_growth",
    )
    config = OperationalAlertConfigurationV1(
        definitions=tuple(
            OperationalAlertDefinition(
                alert_class=alert_class,
                metric_name="queue_depth",
                threshold=1,
                sustain_seconds=5,
                recovery_metric_value=0,
                configuration_version="alerts-v1",
            )
            for alert_class in classes
        )
    )
    telemetry = Telemetry()
    snapshot = OperationalSnapshot(metrics={"queue_depth": 2}, configuration_version="metrics-v1")
    observability = OperationalObservability(
        store=Store(snapshot),
        telemetry=telemetry,
        alert_policy=AlertPolicyV1(),
        alert_configuration=config,
    )

    observability.collect(sustained_seconds=5)

    assert len(telemetry.snapshots) == 1
    assert {alert.name for alert in telemetry.alerts} == set(classes)


def test_operational_observability_rejects_missing_alert_configuration_when_policy_enabled(
) -> None:
    snapshot = OperationalSnapshot(metrics={"queue_depth": 0}, configuration_version="metrics-v1")

    with pytest.raises(ValueError, match="alert configuration is required"):
        OperationalObservability(
            store=Store(snapshot),
            telemetry=Telemetry(),
            alert_policy=AlertPolicyV1(),
        )


def test_alert_policy_emits_recovery_after_condition_clears() -> None:
    definition = OperationalAlertDefinition(
        alert_class="cleanup_backlog",
        metric_name="cleanup_attempt_total",
        threshold=2,
        sustain_seconds=1,
        recovery_metric_value=0,
        configuration_version="alerts-v1",
    )
    policy = AlertPolicyV1()
    firing = policy.evaluate(
        snapshot=OperationalSnapshot({"cleanup_attempt_total": 2}, "metrics-v1"),
        definition=definition,
        sustained_seconds=1,
    )
    recovered = policy.evaluate(
        snapshot=OperationalSnapshot({"cleanup_attempt_total": 0}, "metrics-v1"),
        definition=definition,
        sustained_seconds=0,
        previously_firing=True,
    )

    assert firing is not None and firing.state == "firing"
    assert recovered is not None and recovered.state == "recovered"


def test_alert_policy_uses_configured_recovery_boundary() -> None:
    definition = OperationalAlertDefinition(
        alert_class="cleanup_backlog",
        metric_name="cleanup_attempt_total",
        threshold=2,
        sustain_seconds=1,
        recovery_metric_value=0,
        configuration_version="alerts-v1",
    )
    policy = AlertPolicyV1()

    assert policy.evaluate(
        snapshot=OperationalSnapshot({"cleanup_attempt_total": 1}, "metrics-v1"),
        definition=definition,
        sustained_seconds=0,
        previously_firing=True,
    ) is None


def test_versioned_alert_configuration_loads_from_json_without_defaults() -> None:
    definitions = [
        {
            "alert_class": alert_class,
            "metric_name": "queue_depth",
            "threshold": 1,
            "sustain_seconds": 5,
            "recovery_metric_value": 0,
            "configuration_version": "alerts-v1",
        }
        for alert_class in (
            "queue_age_contention",
            "repeated_lease_expiry_recovery",
            "cleanup_backlog",
            "unreconciled_orphan_growth",
        )
    ]

    configuration = OperationalAlertConfigurationV1.from_json(
        json.dumps({"definitions": definitions})
    )

    assert {definition.alert_class for definition in configuration.definitions} == {
        "queue_age_contention",
        "repeated_lease_expiry_recovery",
        "cleanup_backlog",
        "unreconciled_orphan_growth",
    }


def test_alert_configuration_rejects_unknown_metric_and_duplicate_class() -> None:
    definitions = [
        OperationalAlertDefinition(
            alert_class=alert_class,
            metric_name="queue_depth",
            threshold=1,
            sustain_seconds=1,
            recovery_metric_value=0,
            configuration_version="alerts-v1",
        )
        for alert_class in (
            "queue_age_contention",
            "repeated_lease_expiry_recovery",
            "cleanup_backlog",
            "unreconciled_orphan_growth",
        )
    ]
    with pytest.raises(ValueError, match="unknown Operational Metrics V1 metric"):
        OperationalAlertConfigurationV1(
            definitions=(*definitions[:-1], replace(definitions[-1], metric_name="unknown"))
        )
    with pytest.raises(ValueError, match="duplicate alert definition"):
        OperationalAlertConfigurationV1(definitions=(*definitions, definitions[0]))


def test_alert_configuration_rejects_coerced_boolean_sustain_duration() -> None:
    definitions = tuple(
        OperationalAlertDefinition(
            alert_class=alert_class,
            metric_name="queue_depth",
            threshold=1,
            sustain_seconds=1,
            recovery_metric_value=0,
            configuration_version="alerts-v1",
        )
        for alert_class in (
            "queue_age_contention",
            "repeated_lease_expiry_recovery",
            "cleanup_backlog",
            "unreconciled_orphan_growth",
        )
    )

    with pytest.raises(ValueError, match="invalid OperationalAlertConfigurationV1"):
        OperationalAlertConfigurationV1(
            definitions=(*definitions[:-1], replace(definitions[-1], sustain_seconds=True))
        )


def test_alert_configuration_json_rejects_coerced_numeric_values() -> None:
    definitions = [
        {
            "alert_class": alert_class,
            "metric_name": "queue_depth",
            "threshold": 1,
            "sustain_seconds": 1,
            "recovery_metric_value": 0,
            "configuration_version": "alerts-v1",
        }
        for alert_class in (
            "queue_age_contention",
            "repeated_lease_expiry_recovery",
            "cleanup_backlog",
            "unreconciled_orphan_growth",
        )
    ]
    definitions[-1]["threshold"] = "1"

    with pytest.raises(ValueError, match="invalid OperationalAlertConfigurationV1"):
        OperationalAlertConfigurationV1.from_json(json.dumps({"definitions": definitions}))


def test_claim_latency_histogram_is_contract_visible_without_raw_samples() -> None:
    histogram = OperationalHistogram(
        count=2,
        sum=1.25,
        buckets=((0.5, 1), (1.0, 1), (float("inf"), 2)),
    )
    snapshot = OperationalSnapshot(
        metrics={"claim_latency_count": 2, "claim_latency_sum": 1.25},
        configuration_version="metrics-v1",
        histograms={"claim_latency": histogram},
    )

    assert snapshot.claim_latency == histogram
    assert snapshot.claim_latency is not None
    assert snapshot.claim_latency.count == 2
    assert snapshot.claim_latency.buckets[-1] == (float("inf"), 2)


def test_operational_histogram_rejects_non_cumulative_or_incomplete_buckets() -> None:
    with pytest.raises(ValueError, match="cumulative counts"):
        OperationalHistogram(
            count=2,
            sum=1.0,
            buckets=((1.0, 2), (2.0, 1), (float("inf"), 2)),
        )
    with pytest.raises(ValueError, match="infinite full-count"):
        OperationalHistogram(count=0, sum=0.0, buckets=((1.0, 0),))


def test_direct_alert_configuration_validation_matches_json_validation() -> None:
    definitions = tuple(
        OperationalAlertDefinition(
            alert_class=alert_class,
            metric_name="queue_depth",
            threshold=1,
            sustain_seconds=1,
            recovery_metric_value=0,
            configuration_version="alerts-v1",
        )
        for alert_class in (
            "queue_age_contention",
            "repeated_lease_expiry_recovery",
            "cleanup_backlog",
            "unreconciled_orphan_growth",
        )
    )
    with pytest.raises(ValueError, match="invalid OperationalAlertConfigurationV1"):
        OperationalAlertConfigurationV1(
            definitions=(*definitions[:-1], replace(definitions[-1], sustain_seconds=-1))
        )


def test_alert_configuration_rejects_mutable_definition_container() -> None:
    definitions = [
        OperationalAlertDefinition(
            alert_class=alert_class,
            metric_name="queue_depth",
            threshold=1,
            sustain_seconds=1,
            recovery_metric_value=0,
            configuration_version="alerts-v1",
        )
        for alert_class in (
            "queue_age_contention",
            "repeated_lease_expiry_recovery",
            "cleanup_backlog",
            "unreconciled_orphan_growth",
        )
    ]

    with pytest.raises(ValueError, match="invalid OperationalAlertConfigurationV1"):
        OperationalAlertConfigurationV1(definitions=definitions)
