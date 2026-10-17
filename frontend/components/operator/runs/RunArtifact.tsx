"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { browserRequest } from "@/lib/api/browser-client";

type ArtifactProps = { workspaceId?: string; runId: string; caseId?: string };

type Coverage = {
  name?: string;
  scope?: string;
  k?: number | null;
  numerator?: number;
  denominator?: number | null;
  applicable_denominator?: number;
  value?: number | null;
};
type EvidenceAnchor = {
  document_version_id: string;
  physical_page: number;
  quote?: string | null;
  extraction_snapshot_id?: string | null;
  extraction_sha256?: string | null;
  start_offset?: number | null;
  end_offset?: number | null;
};
type Source = {
  source_id: string;
  document_version_id: string;
  status: string;
  failure_code?: string | null;
};
type Artifact = {
  dataset?: {
    dataset_id: string;
    version: number;
    digest?: string;
    native_digest?: string;
  };
  population?: Record<string, number>;
  retrieval?: Coverage;
  generation_evidence_coverage?: Coverage;
  cases?: {
    case_id: string;
    status: string;
    evaluable?: boolean;
    reasons?: string[];
  }[];
  question?: string;
  expected?: string;
  reference_answer?: string;
  required_facts?: string[];
  evidence_groups?: { alternatives: EvidenceAnchor[] }[];
  no_answer_scope?: unknown;
  context_dependencies?: string[];
  candidate_chunk_ids?: string[];
  generation_chunk_ids?: string[];
  generation_evidence?: [string, string][];
  public_citations?: unknown[];
  reasons?: string[];
  source_preparation?: Source[];
  refusal_correctness?: boolean | null;
  citation_correctness?: boolean | null;
};

function CoverageDetail({
  title,
  metric,
}: {
  title: string;
  metric: Coverage;
}) {
  return (
    <section aria-label={title}>
      <h3>{title}</h3>
      <p>
        Scope: {metric.scope}; K: {metric.k ?? "not applied"}
      </p>
      <p>
        Coverage: {metric.value ?? "N/A"} ({metric.numerator}/
        {metric.denominator})
      </p>
      <p>Applicable groups: {metric.applicable_denominator}</p>
    </section>
  );
}

function GoldDetail({
  artifact,
  workspaceId,
}: {
  artifact: Artifact;
  workspaceId?: string;
}) {
  return (
    <>
      {artifact.question && <p>Question: {artifact.question}</p>}
      {artifact.expected && <p>Expected: {artifact.expected}</p>}
      {artifact.reference_answer && (
        <p>Reference answer: {artifact.reference_answer}</p>
      )}
      {artifact.required_facts && (
        <ul aria-label="Required facts">
          {artifact.required_facts.map((fact, index) => (
            <li key={index}>{fact}</li>
          ))}
        </ul>
      )}
      {artifact.evidence_groups && (
        <section aria-label="Gold evidence">
          <h3>Gold evidence — all groups required</h3>
          {artifact.evidence_groups.map((group, index) => (
            <section key={index}>
              <h4>Group {index + 1} — any reviewed alternative</h4>
              <ul>
                {group.alternatives.map((anchor, alternative) => {
                  const source = artifact.source_preparation?.find(
                    (item) =>
                      item.document_version_id === anchor.document_version_id,
                  );
                  const dataset = artifact.dataset;
                  return (
                    <li key={alternative}>
                      <p>
                        {anchor.document_version_id}, page{" "}
                        {anchor.physical_page}
                      </p>
                      {anchor.quote && <blockquote>{anchor.quote}</blockquote>}
                      {anchor.extraction_snapshot_id && (
                        <p>
                          Extraction snapshot: {anchor.extraction_snapshot_id};
                          SHA-256: {anchor.extraction_sha256}; offsets:{" "}
                          {anchor.start_offset}–{anchor.end_offset}
                        </p>
                      )}
                      {source?.source_id && dataset && workspaceId && (
                        <a
                          href={`/api/operator/evaluation/datasets/${encodeURIComponent(dataset.dataset_id)}/sources/${encodeURIComponent(source.source_id)}/original?workspaceId=${encodeURIComponent(workspaceId)}#page=${anchor.physical_page}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Original PDF — page {anchor.physical_page}
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </section>
      )}
      {artifact.no_answer_scope != null && (
        <section>
          <h3>Reviewed no-answer scope</h3>
          <pre>{JSON.stringify(artifact.no_answer_scope, null, 2)}</pre>
        </section>
      )}
      {artifact.context_dependencies?.length ? (
        <p>Context dependencies: {artifact.context_dependencies.join(", ")}</p>
      ) : null}
      {artifact.candidate_chunk_ids && (
        <p>
          Retrieved chunks: {artifact.candidate_chunk_ids.join(", ") || "none"}
        </p>
      )}
      {artifact.generation_chunk_ids && (
        <p>
          Generation chunks:{" "}
          {artifact.generation_chunk_ids.join(", ") || "none"}
        </p>
      )}
      {artifact.generation_evidence && (
        <section>
          <h3>Evidence sent to generation</h3>
          {artifact.generation_evidence.map(([alias, content]) => (
            <blockquote key={alias}>
              {alias}: {content}
            </blockquote>
          ))}
        </section>
      )}
      {artifact.public_citations && (
        <details>
          <summary>Public citations</summary>
          <pre>{JSON.stringify(artifact.public_citations, null, 2)}</pre>
        </details>
      )}
      {artifact.refusal_correctness != null && (
        <p>Expected decision match: {String(artifact.refusal_correctness)}</p>
      )}
      {artifact.citation_correctness != null && (
        <p>
          Citation structure/provenance: {String(artifact.citation_correctness)}
        </p>
      )}
      {!!artifact.reasons?.length && (
        <p>Unscorable reasons: {artifact.reasons.join(", ")}</p>
      )}
      {artifact.retrieval?.name === "evidence_group_coverage" && (
        <CoverageDetail
          title="Retrieval evidence-group coverage"
          metric={artifact.retrieval}
        />
      )}
      {artifact.generation_evidence_coverage && (
        <CoverageDetail
          title="Generation evidence coverage (diagnostic)"
          metric={artifact.generation_evidence_coverage}
        />
      )}
    </>
  );
}

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
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(true);
  const query = workspaceId
    ? `?workspaceId=${encodeURIComponent(workspaceId)}`
    : "";
  const artifact = data as Artifact | null;
  useEffect(() => {
    let active = true;
    setBusy(true);
    setError(null);
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
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [runId, caseId, query, refresh]);
  return (
    <section aria-label={caseId ? "Evaluation case" : "Evaluation report"}>
      <p>
        <Link href={`/operator/runs/${encodeURIComponent(runId)}${query}`}>
          Run detail
        </Link>
      </p>
      <h2>{caseId ? `Case ${caseId}` : `Report for ${runId}`}</h2>
      <p>
        This is a saved result snapshot. Follow progress in Run detail and
        refresh after new checkpoints.
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={() => setRefresh((value) => value + 1)}
      >
        Refresh saved result
      </button>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading…</p>}
      {data && (
        <>
          <p>Quality: {String(data.quality_status ?? "UNAVAILABLE")}</p>
          {artifact?.dataset && (
            <p>
              Dataset: {artifact.dataset.dataset_id}, version{" "}
              {artifact.dataset.version}, digest{" "}
              {artifact.dataset.digest ?? artifact.dataset.native_digest}
            </p>
          )}
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
          {caseId && artifact && (
            <GoldDetail artifact={artifact} workspaceId={workspaceId} />
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
              {artifact?.population && (
                <ul aria-label="Evaluation population">
                  {Object.entries(artifact.population).map(([name, count]) => (
                    <li key={name}>
                      {name}: {count}
                    </li>
                  ))}
                </ul>
              )}
              {artifact?.retrieval?.name === "evidence_group_coverage" && (
                <CoverageDetail
                  title="Retrieval evidence-group coverage"
                  metric={artifact.retrieval}
                />
              )}
              {artifact?.generation_evidence_coverage && (
                <CoverageDetail
                  title="Generation evidence coverage (diagnostic)"
                  metric={artifact.generation_evidence_coverage}
                />
              )}
              {artifact?.cases && (
                <table>
                  <caption>All selected cases</caption>
                  <thead>
                    <tr>
                      <th>Case</th>
                      <th>Execution</th>
                      <th>Scorable</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {artifact.cases.map((item) => (
                      <tr key={item.case_id}>
                        <td>
                          <Link
                            href={`/operator/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(item.case_id)}${query}`}
                          >
                            {item.case_id}
                          </Link>
                        </td>
                        <td>{item.status}</td>
                        <td>
                          {item.evaluable == null
                            ? "N/A"
                            : String(item.evaluable)}
                        </td>
                        <td>{item.reasons?.join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {artifact?.source_preparation?.map((source) => (
                <p key={source.source_id}>
                  Source preparation {source.document_version_id}:{" "}
                  {source.status} {source.failure_code}
                </p>
              ))}
              <details>
                <summary>Saved report JSON</summary>
                <pre className="overflow-auto text-xs">
                  {JSON.stringify(data, null, 2)}
                </pre>
              </details>
            </>
          )}
        </>
      )}
    </section>
  );
}
