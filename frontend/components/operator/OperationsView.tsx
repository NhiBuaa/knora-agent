import React from "react";
import type { OperatorOperationsResponse } from "../../generated/knora-openapi";
import {
  OPERATOR_METRIC_KEYS,
  presentMetric,
  safeNumber,
} from "../../lib/operator/presentation";

const LABELS: Record<(typeof OPERATOR_METRIC_KEYS)[number], string> = {
  queue_depth: "Queue depth",
  oldest_job_age: "Oldest job age (seconds)",
  claim_latency_count: "Claim latency samples",
  claim_latency_sum: "Claim latency sum (seconds)",
  retry_rate: "Retry rate",
  lease_expiry_recovery_total: "Lease expiry recoveries",
  cleanup_attempt_total: "Cleanup attempts",
  cleanup_failure_total: "Cleanup failures",
  orphan_discovery_total: "Orphan discoveries",
  orphan_reconciliation_total: "Orphan reconciliations",
};

export function OperationsView({
  operations,
}: {
  operations: OperatorOperationsResponse;
}) {
  return (
    <section aria-labelledby="operations-heading">
      <h2 id="operations-heading">Operational observations</h2>
      <p>
        Configuration: <code>{operations.configuration_version}</code>
      </p>
      <dl>
        {OPERATOR_METRIC_KEYS.map((key) => {
          const metric = presentMetric(safeNumber(operations.metrics[key]));
          return (
            <div key={key}>
              <dt>{LABELS[key]}</dt>
              <dd data-state={metric.state}>{metric.value}</dd>
            </div>
          );
        })}
      </dl>
      {Object.entries(operations.histograms).map(([name, histogram]) => {
        if (
          !histogram ||
          typeof histogram !== "object" ||
          Array.isArray(histogram)
        )
          return null;
        const projection = histogram as Record<string, unknown>;
        return (
          <details key={name}>
            <summary>{name.replaceAll("_", " ")} histogram</summary>
            <dl>
              <dt>Samples</dt>
              <dd>{presentMetric(safeNumber(projection.count)).value}</dd>
              <dt>Sum (seconds)</dt>
              <dd>{presentMetric(safeNumber(projection.sum)).value}</dd>
            </dl>
            {Array.isArray(projection.buckets) && (
              <table>
                <caption>Cumulative latency buckets</caption>
                <thead>
                  <tr>
                    <th scope="col">Upper bound</th>
                    <th scope="col">Samples</th>
                  </tr>
                </thead>
                <tbody>
                  {projection.buckets.map((bucket, index) =>
                    Array.isArray(bucket) && bucket.length === 2 ? (
                      <tr key={index}>
                        <td>
                          {typeof bucket[0] === "number"
                            ? `${bucket[0]} s`
                            : String(bucket[0])}
                        </td>
                        <td>{presentMetric(safeNumber(bucket[1])).value}</td>
                      </tr>
                    ) : null,
                  )}
                </tbody>
              </table>
            )}
          </details>
        );
      })}
      <p role="status">Alerts: Unavailable</p>
    </section>
  );
}
