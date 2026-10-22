"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";

type Metric = {
  status: string;
  score?: number | null;
  rationale?: string | null;
  error?: string;
};
type Result = {
  status: string;
  trace_id?: string;
  reason?: string;
  metrics: Record<string, Metric>;
};
type Profile = { profile_id: string; model: string; kind: string };
type Batch = {
  id: string;
  status: string;
  quality_status: string;
  input_digest?: string;
  scorer?: { model: string; prompt_version: string };
  results: Record<string, Result>;
};
type Readiness = {
  preflight_id: string;
  status: string;
  reasons: string[];
  input_digest: string;
  cases: (Result & { case_id: string })[];
};
type Props = {
  workspaceId: string;
  runId: string;
  caseIds: string[];
  canScore: boolean;
};

export function DeepEvalScoring(props: Props) {
  return (
    <SavedScoring
      key={JSON.stringify([props.workspaceId, props.runId])}
      {...props}
    />
  );
}

async function readJson<T>(path: string, payload?: unknown): Promise<T> {
  const response = await fetch(
    path,
    payload === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
          cache: "no-store",
        },
  );
  if (!response.ok)
    throw new Error(`Saved scoring request failed (${response.status})`);
  return response.json() as Promise<T>;
}

function SavedScoring({ workspaceId, runId, caseIds, canScore }: Props) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [profileId, setProfileId] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const query = `?workspaceId=${encodeURIComponent(workspaceId)}`;
  const path = `/api/operator/evaluation/runs/${encodeURIComponent(runId)}/scoring`;
  useEffect(() => {
    let active = true;
    void readJson<{ profiles: Profile[]; batches: Batch[] }>(path + query)
      .then((data) => {
        if (!active) return;
        if (!Array.isArray(data.profiles) || !Array.isArray(data.batches))
          throw new Error("Saved scoring response is invalid");
        setProfiles(data.profiles);
        setBatches(data.batches);
        setProfileId(
          (current) => current || data.profiles[0]?.profile_id || "",
        );
      })
      .catch((cause) => {
        if (active) setError(String(cause));
      });
    return () => {
      active = false;
    };
  }, [path, query, refresh]);

  function invalidate() {
    setReadiness(null);
    setRequestId(null);
  }
  async function preflight() {
    setBusy(true);
    setError(null);
    invalidate();
    try {
      setReadiness(
        await readJson<Readiness>(`${path}/preflight${query}`, {
          case_ids: selected,
          profile_id: profileId,
        }),
      );
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }
  async function score() {
    if (!canScore || readiness?.status !== "READY") return;
    setBusy(true);
    setError(null);
    const id = requestId ?? crypto.randomUUID();
    setRequestId(id);
    try {
      const batch = await readJson<Batch>(path + query, {
        preflight_id: readiness.preflight_id,
        request_id: id,
      });
      setBatches((current) => [
        ...current.filter((item) => item.id !== batch.id),
        batch,
      ]);
      setReadiness(null);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="DeepEval saved-answer scoring">
      <h3>DeepEval scoring</h3>
      <p>
        Scores saved captures; never runs Q&amp;A again. Scores are uncalibrated
        judgments and do not change release gates or deterministic reports.
      </p>
      {error && <p role="alert">{error}</p>}
      {profiles.length === 0 && (
        <p>
          No judge profile is configured. Live scoring requires separate
          approval and verified zero paid budget.
        </p>
      )}
      {canScore && profiles.length > 0 && (
        <>
          <fieldset disabled={busy}>
            <legend>Select saved cases for scoring</legend>
            {caseIds.map((id) => (
              <label key={id} className="block">
                <input
                  type="checkbox"
                  checked={selected.includes(id)}
                  onChange={() => {
                    setSelected((current) =>
                      current.includes(id)
                        ? current.filter((c) => c !== id)
                        : [...current, id],
                    );
                    invalidate();
                  }}
                />{" "}
                {id}
              </label>
            ))}
          </fieldset>
          <label>
            Judge profile{" "}
            <select
              value={profileId}
              disabled={busy}
              onChange={(event) => {
                setProfileId(event.target.value);
                invalidate();
              }}
            >
              {profiles.map((p) => (
                <option key={p.profile_id} value={p.profile_id}>
                  {p.profile_id} — {p.model} ({p.kind})
                </option>
              ))}
            </select>
          </label>
          <p>
            <button
              type="button"
              disabled={busy || selected.length === 0}
              onClick={() => void preflight()}
            >
              Check scoring readiness
            </button>
          </p>
          {readiness && (
            <div>
              <p role="status">
                Readiness: {readiness.status} {readiness.reasons.join(", ")}
              </p>
              <p>Saved input digest: {readiness.input_digest}</p>
              <ul>
                {readiness.cases.map((c) => (
                  <li key={c.case_id}>
                    {c.case_id}: {c.status} {c.reason};{" "}
                    {Object.entries(c.metrics)
                      .map(([name, metric]) => `${name}: ${metric.status}`)
                      .join(", ")}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <button
            type="button"
            disabled={busy || readiness?.status !== "READY"}
            onClick={() => void score()}
          >
            Score saved answers
          </button>
        </>
      )}
      {!canScore && <p>Read-only scoring access.</p>}
      <p>
        <button
          type="button"
          disabled={busy}
          onClick={() => setRefresh((v) => v + 1)}
        >
          Refresh saved scoring
        </button>
      </p>
      {batches.map((batch) => (
        <article key={batch.id}>
          <h4>Scoring {batch.id}</h4>
          <p>
            Execution: {batch.status}; Quality: {batch.quality_status}
          </p>
          <p>
            Model: {batch.scorer?.model}; prompt: {batch.scorer?.prompt_version}
          </p>
          <p>Input digest: {batch.input_digest}</p>
          {Object.entries(batch.results).map(([caseId, result]) => (
            <section key={caseId} aria-label={`Scoring ${caseId}`}>
              <h5>
                <Link
                  href={`/operator/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}${query}`}
                >
                  {caseId}
                </Link>
              </h5>
              <p>
                {result.status} {result.reason}
              </p>
              {result.trace_id && (
                <Link
                  href={`/operator/traces/${encodeURIComponent(result.trace_id)}${query}`}
                >
                  Trace {result.trace_id}
                </Link>
              )}
              <ul>
                {Object.entries(result.metrics).map(([name, metric]) => (
                  <li key={name}>
                    {name}: {metric.status} — {metric.score ?? "N/A"}
                    {metric.rationale && <p>{metric.rationale}</p>}
                    {metric.error && <p>{metric.error}</p>}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </article>
      ))}
    </section>
  );
}
