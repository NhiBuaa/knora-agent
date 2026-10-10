import React from "react";
import type { OperatorOperationsResponse } from "../../generated/knora-openapi";
import { presentMetric, safeNumber } from "../../lib/operator/presentation";

const SIGNALS = [
  ["queue_depth", "Queue depth"],
  ["retry_rate", "Retry rate"],
  ["cleanup_failure_total", "Cleanup failures"],
  ["orphan_discovery_total", "Orphan discoveries"],
] as const;
const ACCOUNTING = [
  ["oldest_job_age", "Oldest job age", " s"],
  ["claim_latency_count", "Claim latency samples", ""],
  ["claim_latency_sum", "Claim latency sum", " s"],
  ["lease_expiry_recovery_total", "Lease expiry recoveries", ""],
  ["cleanup_attempt_total", "Cleanup attempts", ""],
  ["orphan_reconciliation_total", "Orphan reconciliations", ""],
] as const;

export function OperationsView({
  operations,
}: {
  operations: OperatorOperationsResponse;
}) {
  return (
    <section
      aria-labelledby="operations-heading"
      className="m-0 border-0 bg-transparent p-0"
    >
      <p className="mt-[19px] mb-0 flex min-h-[34px] flex-wrap items-center gap-2 text-[13px] text-text-muted">
        Configuration version{" "}
        <strong className="font-semibold text-text-primary">
          {operations.configuration_version}
        </strong>
      </p>
      <h2
        id="operations-heading"
        className="mt-[22px] mb-0 font-display text-xl leading-6 font-semibold"
      >
        Operational observations
      </h2>
      <p className="mt-1.5 mb-0 text-sm leading-[17px] text-text-muted">
        Current workspace signals. Zero values remain visible; unavailable
        values stay explicitly unavailable.
      </p>
      <dl
        role="group"
        aria-label="Runtime signals"
        className="mt-[22px] mb-0 grid grid-cols-4 gap-0 border-y border-border max-md:grid-cols-2"
      >
        {SIGNALS.map(([key, label]) => {
          const raw = safeNumber(operations.metrics[key]);
          const metric = presentMetric(raw);
          const value =
            key === "retry_rate" && raw !== null
              ? `${new Intl.NumberFormat("en", { maximumFractionDigits: 6 }).format(raw * 100)}%`
              : metric.value;
          return (
            <div
              key={key}
              className="min-h-[106px] min-w-0 border-border px-5 pt-[21px] pb-4 max-md:px-1.5 [&:not(:first-child)]:border-l"
            >
              <dt className="text-[13px] leading-4 font-medium text-text-muted">
                {label}
              </dt>
              <dd
                data-state={metric.state}
                className="mt-[15px] font-display text-[26px] leading-8 font-semibold [overflow-wrap:anywhere]"
              >
                {value}
              </dd>
            </div>
          );
        })}
      </dl>
      <h3 className="mt-[30px] mb-0 font-display text-lg leading-6 font-semibold">
        Execution accounting
      </h3>
      <dl className="mt-2.5 mb-0 grid grid-cols-2 gap-x-5 gap-y-0 pr-5 max-md:grid-cols-1 max-md:pr-0 md:pb-px">
        {ACCOUNTING.map(([key, label, unit]) => {
          const metric = presentMetric(safeNumber(operations.metrics[key]));
          return (
            <div
              key={key}
              className="grid min-h-[49px] grid-cols-[minmax(0,1fr)_160px] items-start gap-3 border-b border-border pt-3.5 pb-3.5 text-sm leading-5 max-sm:grid-cols-2"
            >
              <dt className="font-normal text-text-muted">{label}</dt>
              <dd
                data-state={metric.state}
                className="min-w-0 font-semibold [overflow-wrap:anywhere]"
              >
                {metric.value}
                {metric.state === "available" ? unit : ""}
              </dd>
            </div>
          );
        })}
      </dl>
      <h3 className="mt-8 mb-0 font-display text-lg leading-6 font-semibold">
        Latency observations
      </h3>
      <div className="mt-1 grid grid-cols-[minmax(0,760px)_minmax(0,380px)] gap-[60px] max-lg:grid-cols-1 max-lg:gap-6">
        <div className="min-w-0">
          {Object.entries(operations.histograms).map(([name, histogram]) => {
            if (
              !histogram ||
              typeof histogram !== "object" ||
              Array.isArray(histogram)
            )
              return null;
            const projection = histogram as Record<string, unknown>;
            return (
              <div key={name} className="mb-3">
                <p className="mt-[2px] mb-0 text-[13px] leading-5 text-text-muted">
                  {name} · {presentMetric(safeNumber(projection.count)).value}{" "}
                  samples · {presentMetric(safeNumber(projection.sum)).value} s
                  total
                </p>
                {Array.isArray(projection.buckets) && (
                  <dl
                    aria-label="Cumulative latency buckets"
                    className="mt-2 mb-0 grid grid-cols-2 gap-x-5 gap-y-1.5 max-sm:grid-cols-1 md:pb-1.5"
                  >
                    {projection.buckets.map((bucket, index) =>
                      Array.isArray(bucket) && bucket.length === 2 ? (
                        <div
                          key={index}
                          className="grid min-h-10 grid-cols-[minmax(0,1fr)_minmax(60px,max-content)] items-start border-b border-border pt-2.5 pb-[9px] text-[13px] leading-5"
                        >
                          <dt className="font-normal text-text-muted [overflow-wrap:anywhere]">
                            {safeNumber(bucket[0]) !== null ? "≤ " : ""}
                            <span>
                              {safeNumber(bucket[0]) !== null
                                ? `${bucket[0]} s`
                                : "Bound unavailable"}
                            </span>
                          </dt>
                          <dd className="font-semibold">
                            {presentMetric(safeNumber(bucket[1])).value}
                          </dd>
                        </div>
                      ) : null,
                    )}
                  </dl>
                )}
              </div>
            );
          })}
          {!Object.keys(operations.histograms).length && (
            <p className="m-0 text-[13px] text-text-muted">
              Latency histogram unavailable.
            </p>
          )}
        </div>
        <div
          role="status"
          className="mt-[30px] h-fit min-h-[70px] rounded-lg bg-[var(--operator-alert-surface)] px-3.5 py-3"
        >
          <p className="m-0 text-[11px] leading-[15px] font-semibold text-signature">
            ALERTS
          </p>
          <p className="mt-2 mb-0 text-[13px] leading-5">
            Unavailable in the current Operator contract.
          </p>
        </div>
      </div>
    </section>
  );
}
