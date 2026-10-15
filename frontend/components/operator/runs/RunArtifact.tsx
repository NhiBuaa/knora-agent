"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { browserRequest } from "@/lib/api/browser-client";

type ArtifactProps = { workspaceId?: string; runId: string; caseId?: string };

export function RunArtifact(props: ArtifactProps) {
  return (
    <WorkspaceArtifact
      key={JSON.stringify([props.workspaceId, props.runId, props.caseId])}
      {...props}
    />
  );
}

function WorkspaceArtifact({ workspaceId, runId, caseId }: ArtifactProps) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const query = workspaceId
    ? `?workspaceId=${encodeURIComponent(workspaceId)}`
    : "";
  useEffect(() => {
    let active = true;
    const path = `/operator/evaluation/runs/${encodeURIComponent(runId)}/${caseId ? `cases/${encodeURIComponent(caseId)}` : "report"}${query}`;
    void browserRequest(path)
      .then(async (response) => {
        if (!response.ok)
          throw new Error(
            `Evaluation artifact unavailable (${response.status})`,
          );
        return response.json() as Promise<Record<string, unknown>>;
      })
      .then((value) => {
        if (active) setData(value);
      })
      .catch((cause) => {
        if (active) setError(String(cause));
      });
    return () => {
      active = false;
    };
  }, [runId, caseId, query]);
  return (
    <section aria-label={caseId ? "Evaluation case" : "Evaluation report"}>
      <p>
        <Link href={`/operator/runs/${encodeURIComponent(runId)}${query}`}>
          Run detail
        </Link>
      </p>
      <h2>{caseId ? `Case ${caseId}` : `Report for ${runId}`}</h2>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading…</p>}
      {data && (
        <>
          <p>Quality: {String(data.quality_status ?? "UNAVAILABLE")}</p>
          {caseId && <p>Status: {String(data.status ?? "UNAVAILABLE")}</p>}
          {caseId && data.failure_code && (
            <p>Failure: {String(data.failure_code)}</p>
          )}
          {caseId && data.decision && <p>Decision: {String(data.decision)}</p>}
          {caseId && data.public_answer && (
            <p>Answer: {String(data.public_answer)}</p>
          )}
          {caseId && data.refusal_reason && (
            <p>Refusal: {String(data.refusal_reason)}</p>
          )}
          {caseId && typeof data.trace_id === "string" && (
            <p>
              <Link
                href={`/operator/traces/${encodeURIComponent(data.trace_id)}${query}`}
              >
                Trace {data.trace_id}
              </Link>
            </p>
          )}
          {!caseId && (
            <>
              <p>Semantic review: pending or unavailable.</p>
              <p>
                Retrieval denominator:{" "}
                {String(
                  (
                    data.retrieval as
                      | { denominator?: number | null }
                      | undefined
                  )?.denominator ?? "unavailable",
                )}
              </p>
              <p>
                Selected population:{" "}
                {String(
                  (data.population as { selected?: number } | undefined)
                    ?.selected ?? "unavailable",
                )}
              </p>
              <pre className="overflow-auto text-xs">
                {JSON.stringify(data, null, 2)}
              </pre>
            </>
          )}
        </>
      )}
    </section>
  );
}
