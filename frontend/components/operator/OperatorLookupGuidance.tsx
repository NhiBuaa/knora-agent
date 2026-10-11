import React from "react";

const GUIDANCE = {
  trace: {
    heading: "What this trace shows",
    introduction:
      "Open an exact Trace ID to inspect one question’s recorded retrieval and validation evidence.",
    items: [
      {
        label: "DECISION & VALIDATION",
        body: "Final answer or refusal, plus the validation outcome.",
        labelSpacing: "mt-[6px]",
      },
      {
        label: "CANDIDATE PROVENANCE",
        body: "Ranked evidence with source, chunk, score, and selection decision.",
        labelSpacing: "mt-[12px]",
      },
      {
        label: "CITATIONS & TIMING",
        body: "Citation mapping and per-phase timing for the request.",
        labelSpacing: "mt-[13px]",
      },
    ],
  },
  report: {
    heading: "What this report provides",
    introduction:
      "Open an exact Report ID. Knora only shows persisted evaluation data that the backend actually provides.",
    items: [
      {
        label: "PERSISTED REPORT",
        body: "Evaluation data appears only when a persisted report is available.",
        labelSpacing: "mt-[13px]",
      },
      {
        label: "WORKSPACE SCOPED",
        body: "Report context stays tied to the workspace it was observed for.",
        labelSpacing: "mt-[6px]",
      },
      {
        label: "NO INVENTED METRICS",
        body: "Missing reports remain explicitly unavailable instead of becoming synthetic scores.",
        labelSpacing: "mt-[12px]",
      },
    ],
  },
} as const;

export function OperatorLookupGuidance({ kind }: { kind: "trace" | "report" }) {
  const guidance = GUIDANCE[kind];
  const headingId = `operator-${kind}-guidance-heading`;
  return (
    <section aria-labelledby={headingId} className="mt-[59px] min-h-[230px]">
      <h2
        id={headingId}
        className="m-0 font-display text-lg leading-6 font-semibold text-text-primary"
      >
        {guidance.heading}
      </h2>
      <p className="mt-[11px] mb-0 max-w-[820px] text-sm leading-5 text-text-muted">
        {guidance.introduction}
      </p>
      <ul className="mt-[37px] mb-0 grid list-none grid-cols-1 gap-6 p-0 min-[960px]:grid-cols-3 min-[960px]:gap-[60px]">
        {guidance.items.map(({ label, body, labelSpacing }) => (
          <li
            key={label}
            className="m-0 grid min-h-[112px] min-w-0 grid-rows-[43px_auto] content-start border-t border-border text-text-muted"
          >
            <h3
              className={`mb-0 max-w-[330px] font-sans text-xs leading-[15px] font-semibold ${labelSpacing}`}
            >
              {label}
            </h3>
            <p className="m-0 max-w-[340px] text-sm leading-5">{body}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
