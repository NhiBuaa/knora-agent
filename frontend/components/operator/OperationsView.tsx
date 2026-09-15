import React from "react";
import type { OperatorOperationsResponse } from "../../generated/knora-openapi";
import { OPERATOR_METRIC_KEYS, presentMetric, safeNumber } from "../../lib/operator/presentation";

export function OperationsView({ operations }: { operations: OperatorOperationsResponse }) {
  return (
    <section aria-labelledby="operations-heading">
      <h2 id="operations-heading">Operational observations</h2>
      <p>Configuration: <code>{operations.configuration_version}</code></p>
      <dl>
        {OPERATOR_METRIC_KEYS.map((key) => {
          const metric = presentMetric(safeNumber(operations.metrics[key]));
          return <div key={key}><dt>{key}</dt><dd data-state={metric.state}>{metric.value}</dd></div>;
        })}
      </dl>
      <p role="status">Alerts: Unavailable</p>
    </section>
  );
}
