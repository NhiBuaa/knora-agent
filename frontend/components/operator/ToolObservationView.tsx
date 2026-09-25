import React from "react";

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
    <section aria-labelledby="tool-observation-heading">
      <h2 id="tool-observation-heading">M4 tool observation</h2>
      <p>{label}</p>
      {detail ? (
        <p>{detail}</p>
      ) : (
        !state && (
          <p>No authorized lifecycle relation was supplied by the backend.</p>
        )
      )}
      <p>
        Read-only observation; approvals and execution remain backend-owned.
      </p>
    </section>
  );
}
