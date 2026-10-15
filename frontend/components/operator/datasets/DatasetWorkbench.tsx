"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { RagasProposals } from "@/components/operator/datasets/RagasProposals";

type Dataset = {
  id: string;
  workspace_id: string;
  name: string;
  status: string;
  format?: string;
  revision?: number;
  cases?: CaseRecord[];
  reviews?: {
    case_id: string;
    decision: "ACCEPTED" | "REJECTED";
    owner_issuer: string;
    owner_subject: string;
    reviewed_at: string;
    note: string;
  }[];
  reference?: Record<string, unknown> | null;
  proposal_batches?: Record<string, unknown>[];
};

type CaseRecord = {
  case_id: string;
  question: string;
  expected: "ANSWER" | "REFUSAL";
  reference_answer: string | null;
  required_facts: string[];
  language: string;
  category: string;
  evidence_groups: {
    alternatives: {
      document_version_id: string;
      physical_page: number;
      quote: string;
      extraction_snapshot_id: string | null;
      extraction_sha256: string | null;
      start_offset: number | null;
      end_offset: number | null;
    }[];
  }[];
  context_dependencies: string[];
  no_answer_scope: {
    checked_document_version_ids: string[];
    verification_note: string;
  } | null;
};

type Source = {
  id: string;
  dataset_id: string;
  document_id: string;
  document_version_id: string;
  filename: string;
  raw_sha256: string;
  byte_size: number;
  status: "PROCESSING" | "READY" | "FAILED";
  failure_code: string | null;
  snapshot_id: string | null;
};

type Page = {
  source_id: string;
  document_version_id: string;
  snapshot_id: string;
  extraction_sha256: string;
  configuration_sha256: string;
  physical_page: number;
  text: string;
  content_checksum: string;
};

const base = "/api/operator/evaluation/datasets";

function detailPath(datasetId: string, workspaceId: string) {
  return `${base}/${encodeURIComponent(datasetId)}?workspaceId=${encodeURIComponent(workspaceId)}`;
}

type WorkbenchProps = {
  workspaceId?: string;
  initialDatasetId?: string;
  capabilities?: readonly string[];
};

export function DatasetWorkbench(props: WorkbenchProps) {
  return (
    <DatasetWorkspace
      key={JSON.stringify([props.workspaceId, props.initialDatasetId])}
      {...props}
    />
  );
}

function DatasetWorkspace({
  workspaceId,
  initialDatasetId,
  capabilities = [],
}: WorkbenchProps) {
  const canWrite = capabilities.includes("evaluations:write");
  const canApprove = capabilities.includes("evaluations:approve");
  const canReadSource = capabilities.includes("documents:read");
  const viewRequest = useRef(0);
  const uploadKeys = useRef(
    new Map<File, { datasetId: string; key: string }>(),
  );
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState<
    (Dataset & { sources: Source[] }) | null
  >(null);
  const [selected, setSelected] = useState<Source | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [page, setPage] = useState<Page | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingCaseId, setEditingCaseId] = useState<string | null>(null);
  const [caseQuestion, setCaseQuestion] = useState("");
  const [caseExpected, setCaseExpected] = useState<"ANSWER" | "REFUSAL">(
    "ANSWER",
  );
  const [caseReference, setCaseReference] = useState("");
  const [caseFacts, setCaseFacts] = useState("");
  const [caseLanguage, setCaseLanguage] = useState("en");
  const [caseCategory, setCaseCategory] = useState("single-hop");
  const [caseQuote, setCaseQuote] = useState("");
  const [casePage, setCasePage] = useState(1);
  const [caseSourceId, setCaseSourceId] = useState("");
  const [noAnswerNote, setNoAnswerNote] = useState("");
  const [reviewNote, setReviewNote] = useState("");

  const loadCatalog = useCallback(async () => {
    if (!workspaceId) return;
    const request = ++viewRequest.current;
    setError(null);
    try {
      const response = await fetch(
        `${base}?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          cache: "no-store",
        },
      );
      if (!response.ok) throw new Error("Datasets are unavailable.");
      const body: { items: Dataset[] } = await response.json();
      if (request === viewRequest.current) setDatasets(body.items);
    } catch {
      if (request === viewRequest.current)
        setError("Datasets are unavailable.");
    }
  }, [workspaceId]);

  const loadDataset = useCallback(
    async (datasetId: string) => {
      if (!workspaceId) return;
      const request = ++viewRequest.current;
      setError(null);
      try {
        const response = await fetch(detailPath(datasetId, workspaceId), {
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Dataset is unavailable.");
        const body: Dataset & { sources: Source[] } = await response.json();
        if (request !== viewRequest.current) return;
        setDataset(body);
        setSelected(null);
        setPage(null);
        setEditingCaseId(null);
        setCaseSourceId("");
        setReviewNote("");
      } catch {
        if (request === viewRequest.current)
          setError("Dataset is unavailable.");
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    const load = async () => {
      try {
        if (initialDatasetId) await loadDataset(initialDatasetId);
        else await loadCatalog();
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : "Dataset is unavailable.",
        );
      }
    };
    void load();
  }, [initialDatasetId, loadCatalog, loadDataset]);

  async function review(source: Source, physicalPage = 1) {
    const request = ++viewRequest.current;
    setSelected(source);
    setPageNumber(physicalPage);
    setPage(null);
    setError(null);
    if (!workspaceId || !dataset || source.status !== "READY") return;
    if (!Number.isSafeInteger(physicalPage) || physicalPage < 1) {
      setError("Physical page must be a positive whole number.");
      return;
    }
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(dataset.id)}/sources/${encodeURIComponent(source.id)}/pages/${physicalPage}?workspaceId=${encodeURIComponent(workspaceId)}`,
        { cache: "no-store" },
      );
      if (!response.ok) throw new Error("Extracted page is unavailable.");
      const loaded: Page = await response.json();
      if (request !== viewRequest.current) return;
      if (
        loaded.source_id !== source.id ||
        loaded.document_version_id !== source.document_version_id ||
        loaded.snapshot_id !== source.snapshot_id ||
        loaded.physical_page !== physicalPage
      ) {
        throw new Error("Source identity changed. Reload this dataset.");
      }
      setPage(loaded);
    } catch (cause) {
      if (request !== viewRequest.current) return;
      setError(
        cause instanceof Error
          ? cause.message
          : "Extracted page is unavailable.",
      );
    }
  }

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ name: name.trim() }),
        },
      );
      if (!response.ok) throw new Error("Unable to create dataset.");
      const created: Dataset = await response.json();
      setName("");
      await loadDataset(created.id);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to create dataset.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId || !dataset) return;
    const input = event.currentTarget.elements.namedItem(
      "files",
    ) as HTMLInputElement;
    if (!input.files?.length) return;
    setBusy(true);
    setError(null);
    try {
      for (const file of Array.from(input.files)) {
        const body = new FormData();
        body.append("file", file);
        let identity = uploadKeys.current.get(file);
        if (!identity || identity.datasetId !== dataset.id) {
          identity = { datasetId: dataset.id, key: crypto.randomUUID() };
          uploadKeys.current.set(file, identity);
        }
        const response = await fetch(
          `${base}/${encodeURIComponent(dataset.id)}/sources?workspaceId=${encodeURIComponent(workspaceId)}`,
          {
            method: "POST",
            headers: { "Idempotency-Key": identity.key },
            body,
          },
        );
        if (!response.ok) throw new Error(`Unable to upload ${file.name}.`);
      }
      input.value = "";
      uploadKeys.current.clear();
      await loadDataset(dataset.id);
    } catch (cause) {
      await loadDataset(dataset.id);
      setError(
        cause instanceof Error ? cause.message : "Unable to upload PDF.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function retry(source: Source) {
    if (!workspaceId || !dataset) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(dataset.id)}/sources/${encodeURIComponent(source.id)}/retry?workspaceId=${encodeURIComponent(workspaceId)}`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("Unable to retry extraction.");
      await loadDataset(dataset.id);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to retry extraction.",
      );
    } finally {
      setBusy(false);
    }
  }

  function resetCaseForm() {
    setEditingCaseId(null);
    setCaseQuestion("");
    setCaseExpected("ANSWER");
    setCaseReference("");
    setCaseFacts("");
    setCaseLanguage("en");
    setCaseCategory("single-hop");
    setCaseQuote("");
    setCasePage(1);
    setCaseSourceId("");
    setNoAnswerNote("");
  }

  function editCase(caseItem: CaseRecord) {
    const anchor = caseItem.evidence_groups[0]?.alternatives[0];
    setEditingCaseId(caseItem.case_id);
    setCaseQuestion(caseItem.question);
    setCaseExpected(caseItem.expected);
    setCaseReference(caseItem.reference_answer ?? "");
    setCaseFacts(caseItem.required_facts.join("\n"));
    setCaseLanguage(caseItem.language);
    setCaseCategory(caseItem.category);
    setCaseQuote(anchor?.quote ?? "");
    setCasePage(anchor?.physical_page ?? 1);
    setCaseSourceId(
      dataset?.sources.find(
        (source) =>
          source.document_version_id ===
          (anchor?.document_version_id ??
            caseItem.no_answer_scope?.checked_document_version_ids[0]),
      )?.id ?? "",
    );
    setNoAnswerNote(caseItem.no_answer_scope?.verification_note ?? "");
  }

  async function saveCase(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId || !dataset || !caseQuestion.trim()) return;
    const source = caseSourceId
      ? dataset.sources.find((item) => item.id === caseSourceId)
      : dataset.sources[0];
    if (!source) {
      setError("Select an original PDF source before saving a case.");
      return;
    }
    const caseId = editingCaseId ?? crypto.randomUUID();
    const answer = caseExpected === "ANSWER";
    const body: CaseRecord = {
      case_id: caseId,
      question: caseQuestion.trim(),
      expected: caseExpected,
      reference_answer: answer ? caseReference.trim() : null,
      required_facts: answer
        ? caseFacts
            .split("\n")
            .map((fact) => fact.trim())
            .filter(Boolean)
        : [],
      language: caseLanguage.trim(),
      category: caseCategory.trim(),
      evidence_groups: answer
        ? [
            {
              alternatives: [
                {
                  document_version_id: source.document_version_id,
                  physical_page: casePage,
                  quote: caseQuote.trim(),
                  extraction_snapshot_id: null,
                  extraction_sha256: null,
                  start_offset: null,
                  end_offset: null,
                },
              ],
            },
          ]
        : [],
      context_dependencies: [],
      no_answer_scope: answer
        ? null
        : {
            checked_document_version_ids: [source.document_version_id],
            verification_note: noAnswerNote.trim(),
          },
    };
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(dataset.id)}/cases/${encodeURIComponent(caseId)}?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "PUT",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            case: body,
            expected_revision: dataset.revision ?? 0,
          }),
        },
      );
      if (!response.ok) throw new Error("Unable to save case.");
      await loadDataset(dataset.id);
      resetCaseForm();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save case.");
    } finally {
      setBusy(false);
    }
  }

  async function reviewCase(caseId: string, decision: "ACCEPTED" | "REJECTED") {
    if (!workspaceId || !dataset || !reviewNote.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(dataset.id)}/cases/${encodeURIComponent(caseId)}/review?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            decision,
            note: reviewNote.trim(),
            expected_revision: dataset.revision ?? 0,
          }),
        },
      );
      if (!response.ok) throw new Error("Unable to update case review.");
      await loadDataset(dataset.id);
      setReviewNote("");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to update case review.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function freeze() {
    if (!workspaceId || !dataset) return;
    setBusy(true);
    setError(null);
    try {
      const preview = await fetch(
        `${base}/${encodeURIComponent(dataset.id)}/gold-preview?workspaceId=${encodeURIComponent(workspaceId)}`,
        { cache: "no-store" },
      );
      if (!preview.ok)
        throw new Error(
          "Review every case before freezing. Accepted cases must form a complete dataset.",
        );
      const { digest } = (await preview.json()) as { digest: string };
      const response = await fetch(
        `${base}/${encodeURIComponent(dataset.id)}/freeze?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            expected_revision: dataset.revision ?? 0,
            gold_digest: digest,
          }),
        },
      );
      if (!response.ok) throw new Error("Gold dataset is not ready to freeze.");
      await loadDataset(dataset.id);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Gold dataset is not ready to freeze.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function reopen() {
    if (!workspaceId || !dataset) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${base}/${encodeURIComponent(dataset.id)}/revisions?workspaceId=${encodeURIComponent(workspaceId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ expected_revision: dataset.revision ?? 0 }),
        },
      );
      if (!response.ok)
        throw new Error("Unable to open a new dataset revision.");
      await loadDataset(dataset.id);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to open a new dataset revision.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!workspaceId)
    return <p role="status">Select a workspace to review datasets.</p>;

  return (
    <section className="mt-6 space-y-6" aria-label="Dataset builder">
      {error && <p role="alert">{error}</p>}
      {!dataset ? (
        <>
          {canWrite && (
            <form onSubmit={create} className="flex flex-wrap items-end gap-3">
              <label className="grid gap-1">
                Dataset name
                <input
                  className="rounded border border-border bg-surface px-3 py-2"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={200}
                  required
                />
              </label>
              <button
                className="rounded bg-action px-4 py-2 text-white"
                disabled={busy}
              >
                Create dataset
              </button>
            </form>
          )}
          <h2 className="text-xl font-semibold">Datasets</h2>
          <ul className="space-y-2">
            {datasets.map((item) => (
              <li key={item.id}>
                {item.format === "pdf-gold-v1" || !item.format ? (
                  <button
                    className="text-action-text underline"
                    onClick={() => void loadDataset(item.id)}
                  >
                    {item.name}
                  </button>
                ) : (
                  <span>
                    {item.name} ({item.format})
                  </span>
                )}
                <span className="ml-2 text-text-muted">{item.status}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <button
            className="text-action-text underline"
            onClick={() => {
              setDataset(null);
              void loadCatalog();
            }}
          >
            All datasets
          </button>
          <h2 className="text-xl font-semibold">{dataset.name}</h2>
          <p className="text-text-muted">
            Draft PDF sources for manual review. Extracted text is not gold
            evidence until a reviewer selects it.
          </p>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span>Revision {dataset.revision ?? 0}</span>
            <span>Status: {dataset.status}</span>
            <span>
              Gold approval does not approve runtime binding or live calls.
            </span>
            {dataset.status === "FROZEN"
              ? canWrite && (
                  <button
                    className="text-action-text underline"
                    disabled={busy}
                    onClick={() => void reopen()}
                  >
                    Open new revision
                  </button>
                )
              : canApprove && (
                  <button
                    className="rounded bg-action px-3 py-1 text-white"
                    disabled={busy || !dataset.cases?.length}
                    onClick={() => void freeze()}
                  >
                    Freeze accepted cases
                  </button>
                )}
            {dataset.reference && (
              <span className="break-all text-text-muted">
                Gold v{String(dataset.reference.version)} ·{" "}
                {String(dataset.reference.digest)}
              </span>
            )}
            {dataset.reference && (
              <a
                className="text-action-text underline"
                href={`${base}/${encodeURIComponent(dataset.id)}/gold?workspaceId=${encodeURIComponent(workspaceId)}&version=${String(dataset.reference.version)}`}
                target="_blank"
                rel="noreferrer"
              >
                View frozen gold and approval
              </a>
            )}
          </div>
          {canWrite &&
            capabilities.includes("documents:write") &&
            dataset.status !== "FROZEN" && (
              <form
                onSubmit={upload}
                className="flex flex-wrap items-end gap-3"
              >
                <label className="grid gap-1">
                  PDF files
                  <input
                    type="file"
                    name="files"
                    accept="application/pdf,.pdf"
                    multiple
                    required
                    onChange={() => uploadKeys.current.clear()}
                  />
                </label>
                <button
                  className="rounded bg-action px-4 py-2 text-white"
                  disabled={busy}
                >
                  Upload PDFs
                </button>
              </form>
            )}
          <ul className="space-y-2">
            {dataset.sources.map((source) => (
              <li key={source.id} className="flex flex-wrap items-center gap-3">
                <button
                  className="text-action-text underline"
                  onClick={() => void review(source)}
                >
                  {source.filename}
                </button>
                <span>{source.status}</span>
                {source.failure_code && <span>{source.failure_code}</span>}
                {source.status !== "READY" &&
                  canWrite &&
                  capabilities.includes("documents:write") &&
                  dataset.status !== "FROZEN" && (
                    <button
                      className="text-action-text underline"
                      disabled={busy}
                      onClick={() => void retry(source)}
                    >
                      Retry preparation
                    </button>
                  )}
              </li>
            ))}
          </ul>
          {dataset.proposal_batches !== undefined && (
            <RagasProposals
              workspaceId={workspaceId}
              datasetId={dataset.id}
              revision={dataset.revision ?? 0}
              status={dataset.status}
              sources={dataset.sources}
              canWrite={canWrite}
              onChanged={() => loadDataset(dataset.id)}
            />
          )}
          {canWrite && dataset.status !== "FROZEN" && (
            <section
              aria-label="Case editor"
              className="space-y-3 border border-border p-4"
            >
              <h3 className="text-lg font-semibold">
                {editingCaseId ? "Edit case" : "Add case"}
              </h3>
              <form onSubmit={saveCase} className="grid gap-3 md:grid-cols-2">
                <label className="grid gap-1">
                  Source PDF
                  <select
                    className="rounded border border-border px-3 py-2"
                    value={caseSourceId || dataset.sources[0]?.id || ""}
                    onChange={(event) => setCaseSourceId(event.target.value)}
                    required
                  >
                    {!dataset.sources.length && (
                      <option value="">Upload a PDF first</option>
                    )}
                    {dataset.sources.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.filename} · {source.document_version_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="grid gap-1 md:col-span-2">
                  Question
                  <textarea
                    className="rounded border border-border px-3 py-2"
                    value={caseQuestion}
                    onChange={(event) => setCaseQuestion(event.target.value)}
                    required
                  />
                </label>
                <label className="grid gap-1">
                  Expected behavior
                  <select
                    className="rounded border border-border px-3 py-2"
                    value={caseExpected}
                    onChange={(event) =>
                      setCaseExpected(
                        event.target.value as "ANSWER" | "REFUSAL",
                      )
                    }
                  >
                    <option value="ANSWER">ANSWER</option>
                    <option value="REFUSAL">REFUSAL</option>
                  </select>
                </label>
                <label className="grid gap-1">
                  Language
                  <input
                    className="rounded border border-border px-3 py-2"
                    value={caseLanguage}
                    onChange={(event) => setCaseLanguage(event.target.value)}
                    required
                  />
                </label>
                <label className="grid gap-1">
                  Category
                  <input
                    className="rounded border border-border px-3 py-2"
                    value={caseCategory}
                    onChange={(event) => setCaseCategory(event.target.value)}
                    required
                  />
                </label>
                {caseExpected === "ANSWER" && (
                  <>
                    <label className="grid gap-1">
                      Reference answer
                      <textarea
                        className="rounded border border-border px-3 py-2"
                        value={caseReference}
                        onChange={(event) =>
                          setCaseReference(event.target.value)
                        }
                        required
                      />
                    </label>
                    <label className="grid gap-1">
                      Required facts (one per line)
                      <textarea
                        className="rounded border border-border px-3 py-2"
                        value={caseFacts}
                        onChange={(event) => setCaseFacts(event.target.value)}
                        required
                      />
                    </label>
                    <label className="grid gap-1">
                      Evidence quote
                      <textarea
                        className="rounded border border-border px-3 py-2"
                        value={caseQuote}
                        onChange={(event) => setCaseQuote(event.target.value)}
                        required
                      />
                    </label>
                    <label className="grid gap-1">
                      Evidence page
                      <input
                        className="rounded border border-border px-3 py-2"
                        type="number"
                        min={1}
                        value={casePage}
                        onChange={(event) =>
                          setCasePage(Number(event.target.value))
                        }
                        required
                      />
                    </label>
                  </>
                )}
                {caseExpected === "REFUSAL" && (
                  <label className="grid gap-1 md:col-span-2">
                    No-answer verification note
                    <textarea
                      aria-label="No-answer verification note"
                      className="rounded border border-border px-3 py-2"
                      value={noAnswerNote}
                      onChange={(event) => setNoAnswerNote(event.target.value)}
                      required
                    />
                    <span className="text-sm text-text-muted">
                      Verify the original selected PDF. This scope records only
                      that Document Version.
                    </span>
                  </label>
                )}
                <div className="flex items-center gap-3 md:col-span-2">
                  <button
                    className="rounded bg-action px-4 py-2 text-white"
                    disabled={busy}
                  >
                    {editingCaseId ? "Save case" : "Add case"}
                  </button>
                  {editingCaseId && (
                    <button
                      type="button"
                      className="text-action-text underline"
                      onClick={resetCaseForm}
                    >
                      Cancel edit
                    </button>
                  )}
                </div>
              </form>
            </section>
          )}
          {!!dataset.cases?.length && (
            <section aria-label="Case review" className="space-y-2">
              <h3 className="text-lg font-semibold">Cases</h3>
              <p className="text-sm text-text-muted">
                The basic editor supports one original-PDF anchor or one
                no-answer scope. Advanced evidence groups, extraction anchors
                and follow-up cases remain view/review only.
              </p>
              {canApprove && canReadSource && dataset.status !== "FROZEN" && (
                <label className="grid gap-1">
                  Review note
                  <textarea
                    aria-label="Review note"
                    className="rounded border border-border px-3 py-2"
                    value={reviewNote}
                    onChange={(event) => setReviewNote(event.target.value)}
                    maxLength={2000}
                  />
                  <span className="text-sm text-text-muted">
                    Record what you verified against the original PDF before
                    accepting or rejecting a case.
                  </span>
                </label>
              )}
              <ul className="space-y-2">
                {dataset.cases.map((caseItem) => {
                  const caseReview = dataset.reviews?.find(
                    (item) => item.case_id === caseItem.case_id,
                  );
                  return (
                    <li
                      key={caseItem.case_id}
                      className="border border-border p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <strong>{caseItem.question}</strong>
                        <span>{caseItem.expected}</span>
                        <span className="text-text-muted">
                          {caseReview?.decision ?? "UNREVIEWED"}
                        </span>
                      </div>
                      {caseReview?.note && (
                        <p className="break-all text-sm text-text-muted">
                          {caseReview.note} · {caseReview.owner_issuer} /{" "}
                          {caseReview.owner_subject} · {caseReview.reviewed_at}
                        </p>
                      )}
                      {caseItem.reference_answer && (
                        <p className="mt-2 whitespace-pre-wrap">
                          Reference: {caseItem.reference_answer}
                        </p>
                      )}
                      {!!caseItem.required_facts.length && (
                        <p>
                          Required facts: {caseItem.required_facts.join("; ")}
                        </p>
                      )}
                      {caseItem.evidence_groups.map((group, index) => (
                        <div key={index} className="mt-2">
                          <p>
                            Evidence group {index + 1} (required; alternatives
                            below)
                          </p>
                          {group.alternatives.map((anchor, alternative) => (
                            <div key={alternative}>
                              <blockquote className="whitespace-pre-wrap border-l-2 border-border pl-3">
                                {anchor.quote}
                              </blockquote>
                              <button
                                className="text-action-text underline"
                                disabled={!canReadSource}
                                onClick={() => {
                                  const source = dataset.sources.find(
                                    (item) =>
                                      item.document_version_id ===
                                      anchor.document_version_id,
                                  );
                                  if (source)
                                    void review(source, anchor.physical_page);
                                }}
                              >
                                {anchor.document_version_id} · page{" "}
                                {anchor.physical_page}
                              </button>
                              {anchor.extraction_snapshot_id && (
                                <p className="break-all text-sm">
                                  Extraction snapshot:{" "}
                                  {anchor.extraction_snapshot_id}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      ))}
                      {caseItem.no_answer_scope && (
                        <p className="mt-2">
                          No-answer scope:{" "}
                          {caseItem.no_answer_scope.checked_document_version_ids.join(
                            ", ",
                          )}{" "}
                          · {caseItem.no_answer_scope.verification_note}
                        </p>
                      )}
                      {!!caseItem.context_dependencies.length && (
                        <p>
                          Context cases:{" "}
                          {caseItem.context_dependencies.join(", ")}
                        </p>
                      )}
                      {dataset.status !== "FROZEN" && (
                        <div className="mt-2 flex flex-wrap gap-3">
                          {canWrite && (
                            <button
                              className="text-action-text underline"
                              disabled={
                                busy ||
                                caseItem.context_dependencies.length > 0 ||
                                caseItem.evidence_groups.length > 1 ||
                                caseItem.evidence_groups.some(
                                  (group) =>
                                    group.alternatives.length > 1 ||
                                    group.alternatives.some(
                                      (anchor) =>
                                        anchor.extraction_snapshot_id !== null,
                                    ),
                                ) ||
                                (caseItem.no_answer_scope
                                  ?.checked_document_version_ids.length ?? 0) >
                                  1
                              }
                              onClick={() => editCase(caseItem)}
                            >
                              Edit
                            </button>
                          )}
                          {canApprove && canReadSource && (
                            <>
                              <button
                                className="text-action-text underline"
                                disabled={busy || !reviewNote.trim()}
                                onClick={() =>
                                  void reviewCase(caseItem.case_id, "ACCEPTED")
                                }
                              >
                                Accept
                              </button>
                              <button
                                className="text-action-text underline"
                                disabled={busy || !reviewNote.trim()}
                                onClick={() =>
                                  void reviewCase(caseItem.case_id, "REJECTED")
                                }
                              >
                                Reject
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
          {selected && canReadSource && (
            <section aria-label="Source review" className="space-y-3">
              <h3 className="text-lg font-semibold">{selected.filename}</h3>
              <dl className="text-sm">
                <dt>Document Version</dt>
                <dd className="break-all">{selected.document_version_id}</dd>
                <dt>Raw SHA-256</dt>
                <dd className="break-all">{selected.raw_sha256}</dd>
                <dt>Extraction snapshot</dt>
                <dd>{selected.snapshot_id ?? "Unavailable"}</dd>
              </dl>
              {selected.failure_code && (
                <p role="status">{selected.failure_code}</p>
              )}
              <div className="grid gap-4 lg:grid-cols-2">
                <iframe
                  title="Original PDF"
                  className="h-[650px] w-full border border-border"
                  src={`${base}/${encodeURIComponent(dataset.id)}/sources/${encodeURIComponent(selected.id)}/original?workspaceId=${encodeURIComponent(workspaceId)}#page=${pageNumber}`}
                />
                <div className="min-w-0 border border-border p-4">
                  <label className="flex items-center gap-2">
                    Physical page
                    <input
                      className="w-20 rounded border border-border px-2 py-1"
                      type="number"
                      min={1}
                      value={pageNumber}
                      onChange={(event) => {
                        ++viewRequest.current;
                        setPage(null);
                        setPageNumber(Number(event.target.value));
                      }}
                    />
                  </label>
                  <button
                    className="mt-2 text-action-text underline"
                    onClick={() => void review(selected, pageNumber)}
                  >
                    Show extracted page
                  </button>
                  {page ? (
                    <>
                      <p className="mt-3 text-sm text-text-muted">
                        Snapshot {page.snapshot_id} · extraction{" "}
                        {page.extraction_sha256} · page checksum{" "}
                        {page.content_checksum}
                      </p>
                      <pre className="mt-3 whitespace-pre-wrap break-words font-sans text-sm">
                        {page.text}
                      </pre>
                    </>
                  ) : (
                    <p className="mt-3 text-text-muted">
                      Extracted page unavailable.
                    </p>
                  )}
                </div>
              </div>
            </section>
          )}
        </>
      )}
    </section>
  );
}
