"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

type Dataset = {
  id: string;
  workspace_id: string;
  name: string;
  status: string;
  format?: string;
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
};

export function DatasetWorkbench(props: WorkbenchProps) {
  return (
    <DatasetWorkspace
      key={JSON.stringify([props.workspaceId, props.initialDatasetId])}
      {...props}
    />
  );
}

function DatasetWorkspace({ workspaceId, initialDatasetId }: WorkbenchProps) {
  const viewRequest = useRef(0);
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
        const response = await fetch(
          `${base}/${encodeURIComponent(dataset.id)}/sources?workspaceId=${encodeURIComponent(workspaceId)}`,
          {
            method: "POST",
            headers: { "Idempotency-Key": crypto.randomUUID() },
            body,
          },
        );
        if (!response.ok) throw new Error(`Unable to upload ${file.name}.`);
      }
      input.value = "";
      await loadDataset(dataset.id);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to upload PDF.",
      );
      await loadDataset(dataset.id).catch(() => undefined);
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

  if (!workspaceId)
    return <p role="status">Select a workspace to review datasets.</p>;

  return (
    <section className="mt-6 space-y-6" aria-label="Dataset builder">
      {error && <p role="alert">{error}</p>}
      {!dataset ? (
        <>
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
          <form onSubmit={upload} className="flex flex-wrap items-end gap-3">
            <label className="grid gap-1">
              PDF files
              <input
                type="file"
                name="files"
                accept="application/pdf,.pdf"
                multiple
                required
              />
            </label>
            <button
              className="rounded bg-action px-4 py-2 text-white"
              disabled={busy}
            >
              Upload PDFs
            </button>
          </form>
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
                {source.status !== "READY" && (
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
          {selected && (
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
                      onChange={(event) =>
                        setPageNumber(Number(event.target.value))
                      }
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
