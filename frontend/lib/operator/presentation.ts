export type MetricPresentation = {
  value: string;
  state: "available" | "unavailable";
};

export function presentMetric(
  value: number | null | undefined,
): MetricPresentation {
  return typeof value === "number" && Number.isFinite(value)
    ? { value: String(value), state: "available" }
    : { value: "Unavailable", state: "unavailable" };
}

export function observationState(value: {
  availability?: string;
  observation_failure?: string;
}): {
  label: string;
  detail?: string;
  tone: "warning" | "error" | "normal";
} {
  if (value.observation_failure) {
    return {
      label: "Observation unavailable",
      detail: value.observation_failure,
      tone: "warning",
    };
  }
  if (value.availability !== "available")
    return { label: "Observation unavailable", tone: "warning" };
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

export function projectedAccounting(value: unknown): {
  amount: string;
  pricingVersion: string;
  usage: string;
} {
  const section = isRecord(value) ? value : {};
  const cost = isRecord(section.cost) ? section.cost : {};
  const usage = isRecord(section.usage) ? section.usage : {};
  const amount =
    (typeof cost.amount_usd === "string" ||
      typeof cost.amount_usd === "number") &&
    typeof cost.currency === "string"
      ? `${cost.amount_usd} ${cost.currency}`
      : "Unavailable";
  const tokens = ["prompt_tokens", "completion_tokens", "total_tokens"]
    .filter((key) => safeNumber(usage[key]) !== null)
    .map((key) => `${key}: ${usage[key]}`);
  return {
    amount,
    pricingVersion:
      typeof cost.pricing_version === "string"
        ? cost.pricing_version
        : "Unavailable",
    usage: tokens.length ? tokens.join(", ") : "Unavailable",
  };
}

export function projectedTiming(value: unknown): {
  resolution: string;
  phases: Array<{ name: string; duration: string }>;
} {
  const timing = isRecord(value) ? value : {};
  const phases = isRecord(timing.phases) ? timing.phases : {};
  return {
    resolution:
      safeNumber(timing.clock_resolution_ms) !== null
        ? `${timing.clock_resolution_ms} ms`
        : "Unavailable",
    phases: Object.entries(phases).map(([name, phase]) => ({
      name,
      duration:
        isRecord(phase) && safeNumber(phase.duration_ms) !== null
          ? `${phase.duration_ms} ms`
          : "Unavailable",
    })),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
