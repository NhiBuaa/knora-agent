"""Typed operational metric and alert seams."""

import json
import logging
from dataclasses import dataclass, field
from math import inf, isfinite
from typing import Protocol

REQUIRED_ALERT_CLASSES = frozenset(
    {
        "queue_age_contention",
        "repeated_lease_expiry_recovery",
        "cleanup_backlog",
        "unreconciled_orphan_growth",
    }
)
KNOWN_METRICS = frozenset(
    {
        "queue_depth",
        "oldest_job_age",
        "claim_latency_count",
        "claim_latency_sum",
        "retry_rate",
        "lease_expiry_recovery_total",
        "cleanup_attempt_total",
        "cleanup_failure_total",
        "orphan_discovery_total",
        "orphan_reconciliation_total",
    }
)
KNOWN_HISTOGRAMS = frozenset({"claim_latency"})

# The bucket boundaries are an output encoding for the approved claim-latency histogram.  They
# carry no lifecycle policy or alert threshold; the authoritative sample semantics remain the
# durable count and sum plus the cumulative bucket effects.
CLAIM_LATENCY_BUCKET_BOUNDARIES_SECONDS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
    inf,
)


@dataclass(frozen=True, slots=True)
class OperationalHistogram:
    """Low-cardinality cumulative histogram emitted at the observability boundary."""

    count: int
    sum: float
    buckets: tuple[tuple[float, int], ...]

    def __post_init__(self) -> None:
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 0:
            raise ValueError("operational histogram count must be a non-negative integer")
        if not isfinite(float(self.sum)) or self.sum < 0:
            raise ValueError("operational histogram sum must be non-negative and finite")
        if not self.buckets:
            raise ValueError("operational histogram requires at least one bucket")
        previous_bound = float("-inf")
        previous_count = 0
        for bound, bucket_count in self.buckets:
            if previous_bound == inf:
                raise ValueError("operational histogram cannot have buckets after infinity")
            if bound != inf and (not isfinite(bound) or bound <= previous_bound):
                raise ValueError("operational histogram bounds must be strictly increasing")
            if (
                isinstance(bucket_count, bool)
                or not isinstance(bucket_count, int)
                or bucket_count < previous_count
                or bucket_count > self.count
            ):
                raise ValueError("operational histogram buckets must be cumulative counts")
            previous_bound = bound
            previous_count = bucket_count
        if self.buckets[-1][0] != inf or self.buckets[-1][1] != self.count:
            raise ValueError("operational histogram must end with an infinite full-count bucket")


@dataclass(frozen=True, slots=True)
class OperationalSnapshot:
    metrics: dict[str, int | float]
    configuration_version: str
    histograms: dict[str, OperationalHistogram] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.configuration_version:
            raise ValueError("operational metric configuration version is required")
        unknown = set(self.metrics) - KNOWN_METRICS
        if unknown:
            raise ValueError(f"unknown Operational Metrics V1 names: {sorted(unknown)}")
        if any(
            isinstance(value, bool) or not isfinite(float(value))
            for value in self.metrics.values()
        ):
            raise ValueError("operational metrics must be numeric")
        if any(
            name != "retry_rate" and value < 0
            for name, value in self.metrics.items()
        ):
            raise ValueError("Operational Metrics V1 counters and durations must be non-negative")
        unknown_histograms = set(self.histograms) - KNOWN_HISTOGRAMS
        if unknown_histograms:
            raise ValueError(
                f"unknown Operational Metrics V1 histograms: {sorted(unknown_histograms)}"
            )
        retry_rate = self.metrics.get("retry_rate")
        if retry_rate is not None and not 0 <= retry_rate <= 1:
            raise ValueError("retry_rate must be within [0, 1]")

    @property
    def claim_latency(self) -> OperationalHistogram | None:
        """Return the contract-visible claim-latency histogram, when observations exist."""

        return self.histograms.get("claim_latency")


@dataclass(frozen=True, slots=True)
class OperationalAlert:
    name: str
    state: str
    configuration_version: str


@dataclass(frozen=True, slots=True)
class OperationalAlertDefinition:
    alert_class: str
    metric_name: str
    threshold: float
    sustain_seconds: int
    recovery_metric_value: float
    configuration_version: str


@dataclass(frozen=True, slots=True)
class OperationalAlertConfigurationV1:
    definitions: tuple[OperationalAlertDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.definitions, tuple) or any(
            not isinstance(definition, OperationalAlertDefinition)
            for definition in self.definitions
        ):
            raise ValueError("invalid OperationalAlertConfigurationV1 definition")
        if any(
            not isinstance(definition.alert_class, str)
            or not isinstance(definition.metric_name, str)
            or not isinstance(definition.configuration_version, str)
            or not definition.alert_class
            or not definition.metric_name
            or not definition.configuration_version
            for definition in self.definitions
        ):
            raise ValueError("invalid OperationalAlertConfigurationV1 definition")
        classes = {definition.alert_class for definition in self.definitions}
        missing = REQUIRED_ALERT_CLASSES - classes
        if missing:
            raise ValueError(f"missing required alert definitions: {sorted(missing)}")
        if len(classes) != len(self.definitions):
            raise ValueError("duplicate alert definition")
        unknown_metrics = {
            definition.metric_name
            for definition in self.definitions
            if definition.metric_name not in KNOWN_METRICS
        }
        if unknown_metrics:
            raise ValueError(
                f"unknown Operational Metrics V1 metric names: {sorted(unknown_metrics)}"
            )
        if any(
            not isinstance(definition.sustain_seconds, int)
            or isinstance(definition.sustain_seconds, bool)
            or definition.sustain_seconds < 0
            or isinstance(definition.threshold, bool)
            or not isinstance(definition.threshold, (int, float))
            or not isfinite(float(definition.threshold))
            or isinstance(definition.recovery_metric_value, bool)
            or not isinstance(definition.recovery_metric_value, (int, float))
            or not isfinite(float(definition.recovery_metric_value))
            for definition in self.definitions
        ):
            raise ValueError("invalid OperationalAlertConfigurationV1 definition")

    @classmethod
    def from_json(cls, value: str) -> "OperationalAlertConfigurationV1":
        try:
            payload = json.loads(value)
            definitions = tuple(
                OperationalAlertDefinition(
                    alert_class=item["alert_class"],
                    metric_name=item["metric_name"],
                    threshold=item["threshold"],
                    sustain_seconds=item["sustain_seconds"],
                    recovery_metric_value=item["recovery_metric_value"],
                    configuration_version=item["configuration_version"],
                )
                for item in payload["definitions"]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("invalid OperationalAlertConfigurationV1 JSON") from error
        return cls(definitions=definitions)


class OperationalMetricsStore(Protocol):
    def snapshot(self) -> OperationalSnapshot: ...


class OperationalTelemetry(Protocol):
    def publish_snapshot(self, snapshot: OperationalSnapshot) -> None: ...

    def publish_alert(self, alert: OperationalAlert) -> None: ...


class LoggingOperationalTelemetry:
    """Production-safe telemetry sink with only low-cardinality fields."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("knora.operational")

    def publish_snapshot(self, snapshot: OperationalSnapshot) -> None:
        self._logger.info(
            "operational snapshot configuration=%s metrics=%s",
            snapshot.configuration_version,
            {"metrics": snapshot.metrics, "histograms": snapshot.histograms},
        )

    def publish_alert(self, alert: OperationalAlert) -> None:
        self._logger.warning(
            "operational alert name=%s state=%s configuration=%s",
            alert.name,
            alert.state,
            alert.configuration_version,
        )


class AlertPolicyV1:
    def evaluate(
        self,
        *,
        snapshot: OperationalSnapshot,
        definition: OperationalAlertDefinition,
        sustained_seconds: int,
        previously_firing: bool = False,
    ) -> OperationalAlert | None:
        if isinstance(sustained_seconds, bool) or not isinstance(sustained_seconds, int):
            raise ValueError("alert sustain duration must be an integer")
        if sustained_seconds < 0:
            raise ValueError("alert sustain duration must be non-negative")
        value = snapshot.metrics.get(definition.metric_name)
        if previously_firing:
            if value is None or value <= definition.recovery_metric_value:
                return OperationalAlert(
                    name=definition.alert_class,
                    state="recovered",
                    configuration_version=definition.configuration_version,
                )
            return None
        if value is None or value < definition.threshold:
            return None
        if sustained_seconds < definition.sustain_seconds:
            return None
        return OperationalAlert(
            name=definition.alert_class,
            state="firing",
            configuration_version=definition.configuration_version,
        )


class OperationalObservability:
    def __init__(
        self,
        *,
        store: OperationalMetricsStore,
        telemetry: OperationalTelemetry,
        alert_policy: AlertPolicyV1 | None = None,
        alert_configuration: OperationalAlertConfigurationV1 | None = None,
    ) -> None:
        if alert_policy is not None and alert_configuration is None:
            raise ValueError(
                "versioned alert configuration is required when alert policy is enabled"
            )
        self._store = store
        self._telemetry = telemetry
        self._alert_policy = alert_policy
        self._alert_configuration = alert_configuration
        self._alert_states: dict[str, tuple[str, bool]] = {}

    def collect(self, *, sustained_seconds: int = 0) -> OperationalSnapshot:
        snapshot = self._store.snapshot()
        self._telemetry.publish_snapshot(snapshot)
        if self._alert_policy is not None and self._alert_configuration is not None:
            for definition in self._alert_configuration.definitions:
                previous_state = self._alert_states.get(definition.alert_class)
                alert = self._alert_policy.evaluate(
                    snapshot=snapshot,
                    definition=definition,
                    sustained_seconds=sustained_seconds,
                    previously_firing=(
                        previous_state is not None
                        and previous_state[0] == definition.configuration_version
                        and previous_state[1]
                    ),
                )
                if alert is not None:
                    self._telemetry.publish_alert(alert)
                    self._alert_states[definition.alert_class] = (
                        definition.configuration_version,
                        alert.state == "firing",
                    )
        return snapshot
