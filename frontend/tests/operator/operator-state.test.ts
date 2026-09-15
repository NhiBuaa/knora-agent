import { describe, expect, it } from "vitest";
import { observationState, presentMetric } from "../../lib/operator/presentation";

describe("operator observation presentation", () => {
  it("renders unavailable distinctly from a measured zero", () => {
    expect(presentMetric(0)).toEqual({ value: "0", state: "available" });
    expect(presentMetric(null)).toEqual({ value: "Unavailable", state: "unavailable" });
  });

  it("shows observation failures as failures rather than blank dashboard values", () => {
    expect(observationState({ availability: "unavailable", observation_failure: "TRACE_NOT_FOUND" })).toEqual(
      { label: "Observation unavailable", detail: "TRACE_NOT_FOUND", tone: "warning" },
    );
  });
});
