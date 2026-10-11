import React from "react";
import { StatusBadge } from "@/components/ui/StatusBadge";

const LABELS: Record<string, string> = {
  proposed: "Proposed",
  approved: "Approved",
  rejected: "Rejected",
  executing: "Executing",
  succeeded: "Succeeded",
  failed: "Failed",
  reconciliation: "Reconciliation",
  indeterminate_external_outcome: "Indeterminate external outcome",
};

export function ToolObservationView({
  state,
  detail,
}: {
  state?: string;
  detail?: string;
}) {
  const label = state
    ? (LABELS[state] ?? "Observation unavailable")
    : "M4 observation unavailable";
  return (
    <section
      aria-labelledby="tool-observation-heading"
      className="m-0 border-0 bg-transparent p-0 text-sm"
    >
      <h2
        id="tool-observation-heading"
        className="my-3 font-display text-lg font-semibold"
      >
        M4 tool observation
      </h2>
      <StatusBadge
        kind={
          state === "succeeded"
            ? "success"
            : state === "failed"
              ? "error"
              : "warning"
        }
      >
        {label}
      </StatusBadge>
      {detail ? (
        <p className="my-2 leading-5">{detail}</p>
      ) : (
        !state && (
          <p className="my-2 text-text-muted">
            No authorized lifecycle relation was supplied by the backend.
          </p>
        )
      )}
      <p className="my-2 text-xs text-text-muted">
        Read-only observation; approvals and execution remain backend-owned.
      </p>
    </section>
  );
}
