import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { DocumentList } from "@/components/documents/DocumentList";
import { DocumentDetail } from "@/components/documents/DocumentDetail";

const document = {
  document_id: "doc-1",
  workspace_id: "ws-1",
  source_key: "guide",
  source_name: "guide.pdf",
  archived: false,
  revision: 7,
  current_document_version_id: "version-1",
  serving_state: "current" as const,
  ingestion_job_id: null,
  ingestion_status: null,
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "stable-request-id") });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("document management", () => {
  it("resumes status polling for a job already processing after page load", async () => {
    const outdated = {
      ...document,
      ingestion_job_id: "existing-job",
      ingestion_status: "processing",
      embedding_readiness: "reindex_required",
      reprocess_supported: true,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [outdated] }))
      .mockResolvedValueOnce(
        jsonResponse({ ingestion_job_id: "existing-job", status: "succeeded" }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          documents: [
            {
              ...outdated,
              ingestion_status: "succeeded",
              embedding_readiness: "ready",
            },
          ],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentList workspaceId="ws-1" capabilities={["documents:write"]} />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/v1/workspaces/ws-1/ingestion-jobs/existing-job",
    );
    expect(screen.getByText(/Embedding ready/)).toBeInTheDocument();
  });

  it("shows backend re-index readiness and reuses the key after an ambiguous failure", async () => {
    const outdated = {
      ...document,
      embedding_readiness: "reindex_required" as const,
      reprocess_supported: true,
      active_embedding_configuration_id: "old-profile",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [outdated] }))
      .mockResolvedValueOnce(
        jsonResponse({ error: { code: "PROVIDER_REQUEST_FAILED" } }, 503),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            ingestion_job_id: "reindex-job",
            document_version_id: "version-1",
            outcome: "idempotency_replay",
            status: "queued",
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({ ingestion_job_id: "reindex-job", status: "succeeded" }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          documents: [{ ...outdated, embedding_readiness: "ready" }],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentList workspaceId="ws-1" capabilities={["documents:write"]} />,
    );
    await screen.findByText(/Re-index required/);
    fireEvent.click(screen.getByRole("button", { name: "Re-index guide.pdf" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Re-index guide.pdf" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    const submits = fetchMock.mock.calls.filter(
      (call) => call[1]?.method === "POST",
    );
    expect(submits).toHaveLength(2);
    expect(submits[0][1].body).toBe(
      JSON.stringify({ config_mode: "deployed" }),
    );
    expect(new Headers(submits[0][1].headers).get("Idempotency-Key")).toBe(
      "stable-request-id",
    );
    expect(new Headers(submits[1][1].headers).get("Idempotency-Key")).toBe(
      "stable-request-id",
    );
    expect(screen.getByText(/Embedding ready/)).toBeInTheDocument();
  });

  it.each([
    {
      label: "no write capability",
      capabilities: [],
      archived: false,
      supported: true,
      pending: false,
      workspaceArchived: false,
    },
    {
      label: "archived Workspace",
      capabilities: ["documents:write"],
      archived: false,
      supported: true,
      pending: false,
      workspaceArchived: true,
    },
    {
      label: "archived Document",
      capabilities: ["documents:write"],
      archived: true,
      supported: true,
      pending: false,
      workspaceArchived: false,
    },
    {
      label: "unsupported source",
      capabilities: ["documents:write"],
      archived: false,
      supported: false,
      pending: false,
      workspaceArchived: false,
    },
    {
      label: "queued re-index",
      capabilities: ["documents:write"],
      archived: false,
      supported: true,
      pending: true,
      workspaceArchived: false,
    },
  ])(
    "hides re-index action for $label",
    async ({
      capabilities,
      archived,
      supported,
      pending,
      workspaceArchived,
    }) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          jsonResponse({
            documents: [
              {
                ...document,
                archived,
                ingestion_status: pending ? "queued" : null,
                embedding_readiness: "reindex_required",
                reprocess_supported: supported,
              },
            ],
          }),
        ),
      );
      render(
        <DocumentList
          workspaceId="ws-1"
          capabilities={capabilities}
          workspaceArchived={workspaceArchived}
        />,
      );
      if (archived)
        fireEvent.click(await screen.findByLabelText("Show archived"));
      await screen.findByText(/Re-index required/);
      expect(
        screen.queryByRole("button", { name: "Re-index guide.pdf" }),
      ).not.toBeInTheDocument();
    },
  );

  it("sends the loaded revision and reloads after an archive conflict", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [document] }))
      .mockResolvedValueOnce(jsonResponse({ detail: "revision conflict" }, 409))
      .mockResolvedValueOnce(jsonResponse({ documents: [document] }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentList workspaceId="ws-1" capabilities={["documents:write"]} />,
    );
    await screen.findByText("guide.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(
      new Headers(fetchMock.mock.calls[1][1].headers).get("If-Match"),
    ).toBe("7");
    expect(screen.getByRole("alert")).toHaveTextContent("changed");
  });

  it("hides document write controls when documents:write is absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ documents: [document] })),
    );
    render(<DocumentList workspaceId="ws-1" capabilities={[]} />);
    await screen.findByText("guide.pdf");
    expect(screen.queryByLabelText("Document file")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Upload document" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Archive" }),
    ).not.toBeInTheDocument();
  });

  it("uploads a file through the BFF and renders the backend submission state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [] }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            document_id: "doc-2",
            document_version_id: "version-2",
            ingestion_job_id: "job-2",
            status: "queued",
            submission_outcome: "created",
          },
          202,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ documents: [] }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentList workspaceId="ws-1" capabilities={["documents:write"]} />,
    );
    await screen.findByText("No documents yet.");
    fireEvent.change(screen.getByLabelText("Document file"), {
      target: {
        files: [new File(["%PDF"], "manual.pdf", { type: "application/pdf" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/v1/workspaces/ws-1/documents",
    );
    expect(fetchMock.mock.calls[1][1].body).toBeInstanceOf(FormData);
    expect(
      new Headers(fetchMock.mock.calls[1][1].headers).get("Idempotency-Key"),
    ).toBe("stable-request-id");
    expect(fetchMock.mock.calls[1][1].headers).not.toHaveProperty(
      "content-type",
      "application/json",
    );
    expect(await screen.findByRole("status")).toHaveTextContent("queued");
  });

  it("gates deletion on documents:delete and keeps one idempotency key for a retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(document))
      .mockResolvedValueOnce(jsonResponse(document))
      .mockResolvedValueOnce(jsonResponse({ detail: "temporary" }, 503))
      .mockResolvedValueOnce(
        jsonResponse(
          { request_id: "req-1", document_id: "doc-1", state: "requested" },
          202,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const view = render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={[]}
      />,
    );
    await screen.findByText("guide.pdf");
    expect(
      screen.queryByRole("button", { name: "Request deletion" }),
    ).not.toBeInTheDocument();

    view.rerender(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={["documents:delete"]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Request deletion" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Request deletion" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const firstHeaders = fetchMock.mock.calls[1][1].headers as Headers;
    const secondHeaders = fetchMock.mock.calls[2][1].headers as Headers;
    expect(firstHeaders.get("Idempotency-Key")).toBe("stable-request-id");
    expect(secondHeaders.get("Idempotency-Key")).toBe("stable-request-id");
  });

  it("reprocesses the current version and polls until the backend reports success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ ...document, ingestion_job_id: "job-1" }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            ingestion_job_id: "job-3",
            document_version_id: "version-3",
            outcome: "created",
            status: "queued",
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ingestion_job_id: "job-3",
          status: "processing",
          poll_after_seconds: 0.01,
          attempt_count: 1,
          max_attempts: 3,
          created_at: "now",
          updated_at: "now",
          target_document_version_id: "version-3",
          current_document_version_id: null,
          served_document_version_id: "version-1",
          serving_state: "previous",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ingestion_job_id: "job-3",
          status: "succeeded",
          poll_after_seconds: 0,
          attempt_count: 1,
          max_attempts: 3,
          created_at: "now",
          updated_at: "now",
          target_document_version_id: "version-3",
          current_document_version_id: "version-3",
          served_document_version_id: "version-3",
          serving_state: "current",
          result: { document_version_id: "version-3" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={["documents:write"]}
      />,
    );
    await screen.findByText("guide.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Reprocess document" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
    const reprocessCall = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST" && call[0].includes("reprocess"),
    );
    expect(reprocessCall?.[1]).toEqual(
      expect.objectContaining({
        body: JSON.stringify({ config_mode: "current" }),
      }),
    );
    await new Promise((resolve) => setTimeout(resolve, 30));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(screen.getByText("succeeded")).toBeInTheDocument();
  });

  it("reuses one idempotency key when reprocess is retried after a lost response", async () => {
    vi.stubGlobal("crypto", {
      randomUUID: vi
        .fn()
        .mockReturnValueOnce("reprocess-key-one")
        .mockReturnValueOnce("reprocess-key-two"),
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(document))
      .mockResolvedValueOnce(jsonResponse({ detail: "timeout" }, 503))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            ingestion_job_id: "job-4",
            document_version_id: "version-4",
            outcome: "idempotency_replay",
            status: "processing",
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ingestion_job_id: "job-4",
          status: "succeeded",
          poll_after_seconds: 0,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={["documents:write"]}
      />,
    );
    await screen.findByText("guide.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Reprocess document" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Reprocess document" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const keys = fetchMock.mock.calls
      .filter((call) => call[1]?.method === "POST")
      .map((call) => new Headers(call[1].headers).get("Idempotency-Key"));
    expect(keys[0]).toBe("reprocess-key-one");
    expect(keys[1]).toBe("reprocess-key-one");
  });
});
