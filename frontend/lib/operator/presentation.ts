export type MetricPresentation = { value: string; state: "available" | "unavailable" };

export function presentMetric(value: number | null | undefined): MetricPresentation {
  return typeof value === "number" && Number.isFinite(value)
    ? { value: String(value), state: "available" }
    : { value: "Unavailable", state: "unavailable" };
}

export function observationState(value: { availability?: string; observation_failure?: string }): {
  label: string;
  detail?: string;
  tone: "warning" | "error" | "normal";
} {
  if (value.observation_failure) {
    return { label: "Observation unavailable", detail: value.observation_failure, tone: "warning" };
  }
  if (value.availability !== "available") return { label: "Observation unavailable", tone: "warning" };
  return { label: "Observation available", tone: "normal" };
}

export const OPERATOR_METRIC_KEYS = [
  "retrieval_latency_ms",
  "end_to_end_latency_ms",
  "token_count",
  "estimated_cost_usd",
  "failure_count",
] as const;

export function safeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
