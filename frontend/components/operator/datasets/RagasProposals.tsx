"use client";

import React, { useEffect, useMemo, useState } from "react";

type Source = {
  id: string;
  filename: string;
  status: string;
  document_version_id?: string;
};
type Proposal = {
  draft_id: string;
  status: string;
  reason?: string;
  case?: {
    question: string;
    reference_answer: string | null;
    evidence_groups: {
      alternatives: {
        document_version_id: string;
        physical_page: number;
        quote: string;
      }[];
    }[];
  };
};
type Batch = {
  id: string;
  status: string;
  result?: {
    generator?: Record<string, string>;
    diagnostics?: { code: string }[];
    drafts?: Proposal[];
  };
};
type Profile = {
  profile_id: string;
  kind: "offline" | "live";
  model: string;
  prompt_version: string;
};

const base = "/api/operator/evaluation/datasets";

export function RagasProposals({
  workspaceId,
  datasetId,
  revision,
  status,
  sources,
  canWrite,
  onChanged,
}: {
  workspaceId: string;
  datasetId: string;
  revision: number;
  status: string;
  sources: Source[];
  canWrite: boolean;
  onChanged: () => Promise<void>;
}) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [profileId, setProfileId] = useState("");
  const [language, setLanguage] = useState<"vi" | "en">("vi");
  const [count, setCount] = useState(1);
  const [readiness, setReadiness] = useState<Record<string, unknown> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [edits, setEdits] = useState<
    Record<string, { question: string; reference: string }>
  >({});
  const readySources = useMemo(
    () => sources.filter((source) => source.status === "READY"),
    [sources],
  );

  async function load() {
    const response = await fetch(
      `${base}/${encodeURIComponent(datasetId)}/proposals?workspaceId=${encodeURIComponent(workspaceId)}`,
      { cache: "no-store" },
    );
    if (!response.ok) throw new Error("Unable to load Ragas proposals.");
    const data = (await response.json()) as {
      profiles?: Profile[];
      batches?: Batch[];
    };
    const nextProfiles = data.profiles ?? [];
    setProfiles(nextProfiles);
    setBatches(data.batches ?? []);
    setProfileId((current) => current || nextProfiles[0]?.profile_id || "");
  }
  useEffect(() => {
    void load().catch((cause) =>
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to load Ragas proposals.",
      ),
    );
  }, [datasetId, workspaceId]);

  async function preflight() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(datasetId)}/proposals/preflight?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            source_ids: selected,
            profile_id: profileId,
            language,
            count,
          }),
        },
      );
      if (!response.ok) throw new Error("Proposal readiness check failed.");
      setReadiness(await response.json());
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Proposal readiness check failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function generate() {
    if (!readiness || readiness.status !== "READY") return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(datasetId)}/proposals?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            source_ids: selected,
            profile_id: profileId,
            language,
            count,
            expected_revision: revision,
            input_digest: readiness.input_digest,
            request_id: crypto.randomUUID(),
          }),
        },
      );
      if (!response.ok) throw new Error("Proposal generation failed.");
      await load();
      setReadiness(null);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Proposal generation failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function importDraft(batchId: string, draft: Proposal) {
    if (!draft.case) return;
    const edit = edits[draft.draft_id] ?? {
      question: draft.case.question,
      reference: draft.case.reference_answer ?? "",
    };
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(datasetId)}/proposals/${encodeURIComponent(batchId)}/drafts/${encodeURIComponent(draft.draft_id)}/import?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            expected_revision: revision,
            question: edit.question,
            reference_answer: edit.reference,
          }),
        },
      );
      if (!response.ok) throw new Error("Unable to import proposal as a case.");
      await onChanged();
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to import proposal as a case.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-label="Ragas proposals"
      className="space-y-3 border border-border p-4"
    >
      <h3 className="text-lg font-semibold">Ragas question proposals</h3>
      <p className="text-sm text-text-muted">
        Ragas proposes ANSWER multi-hop drafts only. Each draft needs two
        necessary evidence steps and owner review before it can enter the
        canonical Gold Dataset. Single-hop, no-answer, tables and follow-up
        remain unsupported here.
      </p>
      {error && <p role="alert">{error}</p>}
      {!profiles.length ? (
        <p>No proposal provider is configured. Generation stays off.</p>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="grid gap-1">
              Profile
              <select
                value={profileId}
                onChange={(event) => {
                  setProfileId(event.target.value);
                  setReadiness(null);
                }}
              >
                <option value="">Select profile</option>
                {profiles.map((profile) => (
                  <option key={profile.profile_id} value={profile.profile_id}>
                    {profile.profile_id} · {profile.kind}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1">
              Language
              <select
                value={language}
                onChange={(event) =>
                  setLanguage(event.target.value as "vi" | "en")
                }
              >
                <option value="vi">Vietnamese</option>
                <option value="en">English</option>
              </select>
            </label>
            <label className="grid gap-1">
              Draft count
              <input
                type="number"
                min={1}
                max={12}
                value={count}
                onChange={(event) =>
                  setCount(
                    Math.max(1, Math.min(12, Number(event.target.value))),
                  )
                }
              />
            </label>
          </div>
          <fieldset className="space-y-1">
            <legend>PDF sources</legend>
            {readySources.map((source) => (
              <label
                key={source.id}
                className="mr-4 inline-flex items-center gap-2"
              >
                <input
                  type="checkbox"
                  aria-label={source.filename}
                  checked={selected.includes(source.id)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, source.id]
                        : current.filter((id) => id !== source.id),
                    )
                  }
                />
                {source.filename}
              </label>
            ))}
          </fieldset>
          {canWrite && status === "DRAFT" && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={busy || !profileId || !selected.length}
                onClick={() => void preflight()}
              >
                Check proposal readiness
              </button>
              {readiness && (
                <span role="status">
                  {String(readiness.status)}
                  {Array.isArray(readiness.reasons) && readiness.reasons.length
                    ? ` · ${readiness.reasons.join(", ")}`
                    : ""}
                </span>
              )}
              <button
                type="button"
                disabled={busy || readiness?.status !== "READY"}
                onClick={() => void generate()}
              >
                Generate proposals
              </button>
            </div>
          )}
        </>
      )}
      {!!batches.length && (
        <div className="space-y-3">
          <h4 className="font-semibold">Saved proposal batches</h4>
          {batches.map((batch) => (
            <article
              key={batch.id}
              className="space-y-2 border border-border p-3"
            >
              <p>
                Batch {batch.id} · {batch.status}
              </p>
              {batch.result?.generator && (
                <p className="text-sm text-text-muted">
                  Generator:{" "}
                  {batch.result.generator.model ??
                    batch.result.generator.declared_model ??
                    "unknown"}{" "}
                  ·{" "}
                  {batch.result.generator.prompt_version ??
                    batch.result.generator.declared_prompt_version ??
                    "unknown"}
                </p>
              )}
              {batch.result?.diagnostics?.map((item) => (
                <p key={item.code} role="status">
                  {item.code}
                </p>
              ))}
              {batch.result?.drafts?.map((draft) => {
                const item = draft.case;
                if (!item)
                  return (
                    <p key={draft.draft_id} role="status">
                      {draft.draft_id} · {draft.reason ?? draft.status}
                    </p>
                  );
                const edit = edits[draft.draft_id] ?? {
                  question: item.question,
                  reference: item.reference_answer ?? "",
                };
                const anchor = item.evidence_groups[0]?.alternatives[0];
                const source =
                  sources.find(
                    (candidate) =>
                      candidate.document_version_id ===
                      anchor?.document_version_id,
                  ) ?? sources[0];
                return (
                  <div
                    key={draft.draft_id}
                    className="space-y-2 border-t border-border pt-2"
                  >
                    <label className="grid gap-1">
                      Proposal question
                      <input
                        aria-label="Proposal question"
                        value={edit.question}
                        onChange={(event) =>
                          setEdits((current) => ({
                            ...current,
                            [draft.draft_id]: {
                              ...edit,
                              question: event.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                    <label className="grid gap-1">
                      Reference answer
                      <textarea
                        value={edit.reference}
                        onChange={(event) =>
                          setEdits((current) => ({
                            ...current,
                            [draft.draft_id]: {
                              ...edit,
                              reference: event.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                    {anchor && source && (
                      <a
                        className="text-action-text underline"
                        href={`${base}/${encodeURIComponent(datasetId)}/sources/${encodeURIComponent(source.id)}/original?workspaceId=${encodeURIComponent(workspaceId)}#page=${anchor.physical_page}`}
                      >
                        PDF page {anchor.physical_page}
                      </a>
                    )}
                    <p className="text-sm">Status: {draft.status}</p>
                    {canWrite &&
                      status === "DRAFT" &&
                      draft.status === "READY_FOR_REVIEW" && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void importDraft(batch.id, draft)}
                        >
                          Import as unreviewed case
                        </button>
                      )}
                  </div>
                );
              })}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
