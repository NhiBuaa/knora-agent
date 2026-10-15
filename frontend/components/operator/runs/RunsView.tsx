"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { browserRequest } from "@/lib/api/browser-client";

type Case = { id: string; question: string; expected_behavior: string };
type Dataset = {
  id: string;
  format: string;
  reference: { format: string; [key: string]: unknown } | null;
  cases: Case[];
};
type Profile = { profile_id: string; kind: string; status: string };
type Preflight = {
  preflight_id: string;
  status: string;
  reasons: string[];
  context_only_case_ids?: string[];
  case_readiness?: {
    case_id: string;
    status: string;
    reasons: string[];
    warnings: string[];
  }[];
  source_preparation?: {
    document_version_id: string;
    status: string;
    failure_code: string | null;
  }[];
};
type Observation = {
  status: string;
  failure_code?: string;
  trace_id?: string;
  decision?: string;
  public_answer?: string;
  refusal_reason?: string;
};
type Run = {
  run_id: string;
  execution_status: string;
  quality_status: string;
  selection: { selected_case_ids: string[] };
  observations: Record<string, Observation>;
  report: {
    retrieval?: { denominator: number | null };
    quality_status?: string;
  } | null;
};

const base = "/operator/evaluation";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await browserRequest(path, init);
  if (!response.ok)
    throw new Error(`Evaluation request failed (${response.status})`);
  return response.json() as Promise<T>;
}

type RunsProps = {
  workspaceId?: string;
  runId?: string;
  capabilities?: string[];
};

export function RunsView(props: RunsProps) {
  return (
    <WorkspaceRuns
      key={JSON.stringify([props.workspaceId, props.runId])}
      {...props}
    />
  );
}

function WorkspaceRuns({ workspaceId, runId, capabilities = [] }: RunsProps) {
  const canRun = ["operator:read", "evaluations:run", "questions:ask"].every(
    (capability) => capabilities.includes(capability),
  );
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [profileId, setProfileId] = useState("live");
  const [selected, setSelected] = useState<string[]>([]);
  const [preflight, setPreflight] = useState<Preflight | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const query = workspaceId
    ? `?workspaceId=${encodeURIComponent(workspaceId)}`
    : "";

  useEffect(() => {
    if (!workspaceId) return;
    let active = true;
    if (runId) {
      const read = () =>
        json<Run>(`${base}/runs/${encodeURIComponent(runId)}${query}`)
          .then((value) => {
            if (active) setRun(value);
          })
          .catch((cause) => {
            if (active) setError(String(cause));
          });
      void read();
      const interval = setInterval(() => {
        if (
          active &&
          run?.execution_status !== "COMPLETED" &&
          run?.execution_status !== "BLOCKED" &&
          run?.execution_status !== "INDETERMINATE"
        )
          void read();
      }, 2000);
      return () => {
        active = false;
        clearInterval(interval);
      };
    }
    void Promise.all([
      json<{ items: Dataset[] }>(`${base}/datasets${query}`),
      json<Profile[]>(`${base}/profiles${query}`),
      json<Run[]>(`${base}/runs${query}`),
    ])
      .then(([catalog, availableProfiles, savedRuns]) => {
        if (!active) return;
        const available = catalog.items.filter(
          (item) =>
            item.reference?.format === "m3-native-v1" ||
            item.reference?.format === "pdf-gold-v1",
        );
        setDatasets(available);
        setDatasetId(available[0]?.id ?? "");
        setProfiles(availableProfiles);
        setRuns(savedRuns);
      })
      .catch((cause) => {
        if (active) setError(String(cause));
      });
    return () => {
      active = false;
    };
  }, [workspaceId, runId, query, run?.execution_status]);

  const dataset = datasets.find((item) => item.id === datasetId);
  function toggleCase(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
    setPreflight(null);
  }
  async function checkReadiness() {
    if (!canRun) return;
    setBusy(true);
    setError(null);
    try {
      setPreflight(
        await json<Preflight>(`${base}/preflight${query}`, {
          method: "POST",
          body: JSON.stringify({
            dataset_id: datasetId,
            case_ids: selected,
            profile_id: profileId,
            ...(dataset?.reference?.format === "pdf-gold-v1"
              ? { dataset_reference: dataset.reference }
              : {}),
          }),
        }),
      );
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    if (!canRun || preflight?.status !== "READY") return;
    setBusy(true);
    setError(null);
    try {
      const idempotencyKey = crypto.randomUUID();
      const started = await json<Run>(`${base}/runs${query}`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ preflight_id: preflight.preflight_id }),
      });
      window.location.assign(
        `/operator/runs/${encodeURIComponent(started.run_id)}${query}`,
      );
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }
  if (!workspaceId)
    return <p role="status">Select a Workspace to inspect evaluation runs.</p>;
  if (runId)
    return (
      <section aria-label="Evaluation run detail">
        <p>
          <Link href={`/operator/runs${query}`}>All runs</Link>
        </p>
        {error && <p role="alert">{error}</p>}
        {!run ? (
          <p role="status">Loading run…</p>
        ) : (
          <>
            <h2>Run {run.run_id}</h2>
            <p>Execution: {run.execution_status}</p>
            <p>Quality: {run.quality_status}</p>
            <p>Selected cases: {run.selection.selected_case_ids.length}</p>
            <ul>
              {run.selection.selected_case_ids.map((id) => {
                const observation = run.observations[id];
                return (
                  <li key={id}>
                    <Link
                      href={`/operator/runs/${encodeURIComponent(run.run_id)}/cases/${encodeURIComponent(id)}${query}`}
                    >
                      {id}
                    </Link>
                    : {observation?.status ?? "NOT_RUN"}{" "}
                    {observation?.failure_code ?? ""}
                    {observation?.trace_id && (
                      <>
                        {" "}
                        ·{" "}
                        <Link
                          href={`/operator/traces/${encodeURIComponent(observation.trace_id)}${query}`}
                        >
                          Trace {observation.trace_id}
                        </Link>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
            {run.report && (
              <p>
                <Link
                  href={`/operator/runs/${encodeURIComponent(run.run_id)}/report${query}`}
                >
                  Report
                </Link>
              </p>
            )}
          </>
        )}
      </section>
    );
  return (
    <section aria-label="Evaluation runs">
      <h2>New evaluation run</h2>
      {!canRun && (
        <p>
          Read-only access. Starting evaluation requires run and Q&amp;A
          permissions.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {!dataset && (
        <p role="status">
          No frozen supported dataset is available for this Workspace.
        </p>
      )}
      {dataset && (
        <>
          <label>
            Dataset{" "}
            <select
              disabled={busy}
              value={datasetId}
              onChange={(event) => {
                setDatasetId(event.target.value);
                setSelected([]);
                setPreflight(null);
              }}
            >
              {datasets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.id}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend>Select cases</legend>
            {dataset.cases.map((item) => (
              <label key={item.id} className="block">
                <input
                  type="checkbox"
                  disabled={busy}
                  checked={selected.includes(item.id)}
                  onChange={() => toggleCase(item.id)}
                />{" "}
                {item.id}: {item.question} ({item.expected_behavior})
              </label>
            ))}
          </fieldset>
          <label>
            Runtime profile{" "}
            <select
              disabled={busy}
              value={profileId}
              onChange={(event) => {
                setProfileId(event.target.value);
                setPreflight(null);
              }}
            >
              {profiles.map((item) => (
                <option key={item.profile_id} value={item.profile_id}>
                  {item.profile_id} — {item.status}
                </option>
              ))}
            </select>
          </label>
          <p>
            <button
              type="button"
              disabled={!canRun || busy || selected.length === 0}
              onClick={() => void checkReadiness()}
            >
              Check readiness
            </button>
          </p>
          {preflight && (
            <div>
              <p role="status">
                Readiness: {preflight.status} {preflight.reasons.join(", ")}
              </p>
              <p>
                Context-only cases:{" "}
                {preflight.context_only_case_ids?.join(", ") || "none"}
              </p>
              <ul>
                {preflight.case_readiness?.map((item) => (
                  <li key={item.case_id}>
                    {item.case_id}: {item.status} {item.reasons.join(", ")}{" "}
                    {item.warnings.join(", ")}
                  </li>
                ))}
              </ul>
              <ul>
                {preflight.source_preparation?.map((item) => (
                  <li key={item.document_version_id}>
                    Source preparation {item.document_version_id}: {item.status}{" "}
                    {item.failure_code}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <button
            type="button"
            disabled={!canRun || busy || preflight?.status !== "READY"}
            onClick={() => void start()}
          >
            Start run
          </button>
        </>
      )}
      <h2>Saved runs</h2>
      <ul>
        {runs.map((item) => (
          <li key={item.run_id}>
            <Link
              href={`/operator/runs/${encodeURIComponent(item.run_id)}${query}`}
            >
              {item.run_id}
            </Link>{" "}
            — {item.execution_status}
          </li>
        ))}
      </ul>
    </section>
  );
}
