import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DocumentResponse } from "@/generated/knora-openapi";
import { DocumentList } from "@/components/documents/DocumentList";
import { DocumentDetail } from "@/components/documents/DocumentDetail";

const navigation = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
  usePathname: () => "/workspaces/ws-1/documents/doc-1",
}));

const ready: DocumentResponse = {
  document_id: "doc-1",
  workspace_id: "ws-1",
  source_key: "manual",
  source_name: "manual.pdf",
  archived: false,
  revision: 7,
  current_document_version_id: "version-new",
  served_document_version_id: "version-new",
  serving_state: "current",
  ingestion_job_id: null,
  ingestion_status: "succeeded",
  embedding_readiness: "ready",
  reprocess_supported: true,
  answer_availability: "available",
  last_processed_at: null,
  deletion_request: null,
};
const capabilities = ["documents:write", "documents:delete"];
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
function detail(document: DocumentResponse = ready) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(document)));
  return render(
    <DocumentDetail
      workspaceId="ws-1"
      documentId="doc-1"
      capabilities={capabilities}
    />,
  );
}
async function openUpload() {
  await userEvent.click(
    screen.getByRole("button", { name: "Upload document" }),
  );
  return screen.getByRole("dialog", { name: "Upload document" });
}
beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "intent-key") });
  navigation.push.mockClear();
  navigation.refresh.mockClear();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("Documents Figma lifecycle", () => {
  it.each(["list", "detail"])(
    "uses the reloaded Document projection after a terminal %s job",
    async (surface) => {
      let reads = 0;
      const initial = {
        ...ready,
        ingestion_job_id: "terminal-job",
        ingestion_status: "processing" as const,
        serving_state: "previous" as const,
        served_document_version_id: "old-served",
      };
      const latest = {
        ...ready,
        current_document_version_id: "newest-version",
        served_document_version_id: "newest-version",
        last_processed_at: "2026-09-26T07:32:00Z",
      };
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string) => {
          if (url.includes("ingestion-jobs"))
            return json({
              ingestion_job_id: "terminal-job",
              status: "succeeded",
              poll_after_seconds: 0,
              current_document_version_id: "version-new",
              served_document_version_id: "old-served",
              serving_state: "previous",
            });
          reads++;
          const document = reads === 1 ? initial : latest;
          return json(
            surface === "list" ? { documents: [document] } : document,
          );
        }),
      );
      render(
        surface === "list" ? (
          <DocumentList workspaceId="ws-1" capabilities={capabilities} />
        ) : (
          <DocumentDetail
            workspaceId="ws-1"
            documentId="doc-1"
            capabilities={capabilities}
          />
        ),
      );
      await waitFor(() => expect(reads).toBe(2));
      await waitFor(() =>
        expect(
          screen.queryByText(/previous version still served/i),
        ).not.toBeInTheDocument(),
      );
      if (surface === "detail")
        expect(screen.getByText("Served: newest-version")).toBeVisible();
    },
  );

  it("polls an accepted upload even when it has not appeared in the list yet", async () => {
    let finishJob: ((value: Response) => void) | undefined;
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST")
        return json(
          {
            document_id: "doc-1",
            document_version_id: "version-new",
            ingestion_job_id: "upload-job",
            status: "queued",
            submission_outcome: "created",
          },
          202,
        );
      if (url.endsWith("/upload-job"))
        return new Promise<Response>((resolve) => {
          finishJob = resolve;
        });
      return json({ documents: finishJob ? [ready] : [] });
    });
    vi.stubGlobal("fetch", fetcher);
    render(<DocumentList workspaceId="ws-1" capabilities={capabilities} />);
    await screen.findByText("No documents yet.");
    const dialog = await openUpload();
    await userEvent.upload(
      within(dialog).getByLabelText("Document file"),
      new File(["pdf"], "upload.pdf", { type: "application/pdf" }),
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Upload document" }),
    );
    await waitFor(() => expect(finishJob).toBeTypeOf("function"));
    finishJob!(
      json({
        ingestion_job_id: "upload-job",
        status: "succeeded",
        poll_after_seconds: 0,
      }),
    );
    expect(
      await screen.findByRole("link", { name: "manual.pdf" }),
    ).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("succeeded");
  });

  it("uses the latest job serving snapshot while processing independently of its original document snapshot", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("ingestion-jobs")
          ? json({
              ingestion_job_id: "job-1",
              status: "failed",
              serving_state: "previous",
              served_document_version_id: "older-served",
              current_document_version_id: "version-new",
              poll_after_seconds: 0,
              failure_reason: "retry_exhausted",
            })
          : json({
              ...ready,
              ingestion_job_id: "job-1",
              ingestion_status: "processing",
            }),
      ),
    );
    render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={capabilities}
      />,
    );
    expect(
      await screen.findByText(/Previous version still served: older-served/),
    ).toBeVisible();
    expect(screen.getByRole("region", { name: "Overview" })).toHaveTextContent(
      "Processing failed",
    );
    expect(
      screen.getByText(/Ingestion failure: retry_exhausted/),
    ).toBeVisible();
  });

  it("discards an old detail response after a document route change", async () => {
    let resolveOld!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveOld = resolve;
            }),
        )
        .mockResolvedValueOnce(
          json({
            ...ready,
            document_id: "doc-2",
            source_name: "replacement.pdf",
          }),
        ),
    );
    const view = render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={capabilities}
      />,
    );
    view.rerender(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-2"
        capabilities={capabilities}
      />,
    );
    await screen.findByRole("heading", { name: "replacement.pdf" });
    resolveOld(json(ready));
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "manual.pdf" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("renders a session recovery link instead of an empty list for HTTP 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "expired" }, 401)),
    );
    render(<DocumentList workspaceId="ws-1" capabilities={capabilities} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "session expired",
    );
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/api/auth/login",
    );
    expect(screen.queryByText("No documents yet.")).not.toBeInTheDocument();
  });
  it("keeps a selected upload on session expiry and offers native sign-in recovery", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json({ documents: [] }))
        .mockResolvedValueOnce(json({ detail: "expired" }, 401)),
    );
    render(<DocumentList workspaceId="ws-1" capabilities={capabilities} />);
    await screen.findByText("No documents yet.");
    const dialog = await openUpload();
    await userEvent.upload(
      within(dialog).getByLabelText("Document file"),
      new File(["pdf"], "resume.pdf", { type: "application/pdf" }),
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Upload document" }),
    );
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "session expired",
    );
    expect(within(dialog).getByText("resume.pdf")).toBeVisible();
    expect(
      within(dialog).getByRole("link", { name: "Sign in" }),
    ).toHaveAttribute("target", "_blank");
  });
  it("selects and removes a file in a modal, and Cancel submits nothing", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ documents: [] }));
    vi.stubGlobal("fetch", fetcher);
    render(<DocumentList workspaceId="ws-1" capabilities={capabilities} />);
    await screen.findByText("No documents yet.");
    let dialog = await openUpload();
    expect(
      within(dialog).getByRole("button", { name: "Upload document" }),
    ).toBeDisabled();
    const file = new File(["pdf"], "selected.pdf", { type: "application/pdf" });
    await userEvent.upload(
      within(dialog).getByLabelText("Document file"),
      file,
    );
    expect(within(dialog).getByText("selected.pdf")).toBeVisible();
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Remove file" }),
    );
    expect(within(dialog).queryByText("selected.pdf")).not.toBeInTheDocument();
    await userEvent.upload(
      within(dialog).getByLabelText("Document file"),
      file,
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Cancel" }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    dialog = await openUpload();
    expect(within(dialog).queryByText("selected.pdf")).not.toBeInTheDocument();
    expect(
      fetcher.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(0);
  });

  it("guards duplicate upload clicks and retries an uncertain submission with the same file/key", async () => {
    let rejectUpload!: (reason: Error) => void;
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ documents: [] }))
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            rejectUpload = reject;
          }),
      )
      .mockResolvedValueOnce(
        json({
          document_id: "doc-1",
          document_version_id: "version-new",
          outcome: "created",
        }),
      )
      .mockResolvedValueOnce(json({ documents: [ready] }));
    vi.stubGlobal("fetch", fetcher);
    render(<DocumentList workspaceId="ws-1" capabilities={capabilities} />);
    await screen.findByText("No documents yet.");
    const dialog = await openUpload();
    await userEvent.upload(
      within(dialog).getByLabelText("Document file"),
      new File(["pdf"], "selected.pdf", { type: "application/pdf" }),
    );
    const submit = within(dialog).getByRole("button", {
      name: "Upload document",
    });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(
      fetcher.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    rejectUpload(new Error("lost response"));
    await screen.findByRole("alert");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Upload document" }),
    );
    await screen.findByRole("link", { name: "manual.pdf" });
    const uploads = fetcher.mock.calls.filter(
      ([, init]) => init?.method === "POST",
    );
    expect(uploads).toHaveLength(2);
    expect(
      uploads.map(([, init]) =>
        new Headers(init.headers).get("Idempotency-Key"),
      ),
    ).toEqual(["intent-key", "intent-key"]);
    expect(uploads[1][1].body.get("source_key")).toBe("selected.pdf");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("searches the complete list and distinguishes archived visibility from no matches", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json({
          documents: [
            ready,
            {
              ...ready,
              document_id: "old",
              source_name: "Old handbook.md",
              archived: true,
            },
          ],
        }),
      ),
    );
    render(<DocumentList workspaceId="ws-1" capabilities={[]} />);
    await screen.findByRole("link", { name: "manual.pdf" });
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search documents" }),
      "HANDBOOK",
    );
    expect(screen.getByText("No documents found.")).toBeVisible();
    await userEvent.click(screen.getByLabelText("Show archived"));
    expect(screen.getByRole("link", { name: "Old handbook.md" })).toBeVisible();
    expect(screen.getByText("1 document")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "manual.pdf" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["queued", "Queued"],
    ["processing", "Processing…"],
    ["retry_scheduled", "Retry scheduled"],
    ["failed", "Processing failed"],
  ])(
    "shows %s separately from previous serving",
    async (ingestion_status, label) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          json({
            documents: [
              {
                ...ready,
                ingestion_status,
                serving_state: "previous",
                served_document_version_id: "version-old",
              },
            ],
          }),
        ),
      );
      render(<DocumentList workspaceId="ws-1" capabilities={[]} />);
      expect(await screen.findByText(label)).toBeVisible();
      expect(screen.getByText(/Previous version still served/)).toBeVisible();
    },
  );

  it("renders the canonical source route and unknown last processing without manufacturing answer readiness", async () => {
    detail({
      ...ready,
      answer_availability: "unknown",
      serving_state: "previous",
      served_document_version_id: "version-old",
      ingestion_status: "failed",
    });
    await screen.findByRole("heading", { name: "manual.pdf" });
    const overview = screen.getByRole("region", { name: "Overview" });
    expect(
      within(overview).getByText("Last processed").nextElementSibling,
    ).toHaveTextContent("Unavailable");
    expect(
      within(overview).getByText("Available for new answers")
        .nextElementSibling,
    ).toHaveTextContent("Unavailable");
    expect(
      within(overview).getByText("Source version").nextElementSibling,
    ).toHaveTextContent("Current: version-new");
    expect(
      within(overview).getByText("Source version").nextElementSibling,
    ).toHaveTextContent("Previous served: version-old");
    expect(screen.getByRole("link", { name: "manual.pdf" })).toHaveAttribute(
      "href",
      "/workspaces/ws-1/documents/doc-1",
    );
    expect(screen.getByText(/Previous version still served/)).toBeVisible();
  });

  it("restores an archived detail with its revision and renders the server result", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        json({ ...ready, archived: true, answer_availability: "unavailable" }),
      )
      .mockResolvedValueOnce(json({ ...ready, revision: 8 }));
    vi.stubGlobal("fetch", fetcher);
    render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={capabilities}
      />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Restore document" }),
    );
    expect(
      await screen.findByRole("button", { name: "Archive document" }),
    ).toBeVisible();
    expect(fetcher.mock.calls[1][0]).toBe(
      "/api/v1/workspaces/ws-1/documents/doc-1/unarchive",
    );
    expect(new Headers(fetcher.mock.calls[1][1].headers).get("If-Match")).toBe(
      "7",
    );
  });

  it("opens the row menu with keyboard and archives using the loaded revision", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ documents: [ready] }))
      .mockResolvedValueOnce(json({ ...ready, archived: true }))
      .mockResolvedValueOnce(
        json({ documents: [{ ...ready, archived: true }] }),
      );
    vi.stubGlobal("fetch", fetcher);
    render(<DocumentList workspaceId="ws-1" capabilities={capabilities} />);
    const trigger = await screen.findByRole("button", {
      name: "Actions for manual.pdf",
    });
    trigger.focus();
    await userEvent.keyboard("{ArrowDown}");
    expect(
      screen.getByRole("menuitem", { name: "View details" }),
    ).toHaveFocus();
    await userEvent.click(
      screen.getByRole("menuitem", { name: "Archive document" }),
    );
    await screen.findByText("No documents yet.");
    expect(new Headers(fetcher.mock.calls[1][1].headers).get("If-Match")).toBe(
      "7",
    );
  });

  it("confirms deletion and preserves real blocked/policy unavailable after reload", async () => {
    const blocked = {
      request_id: "delete-1",
      document_id: "doc-1",
      state: "blocked",
      failure_reason: "DOCUMENT_DELETION_POLICY_UNAVAILABLE",
    };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json(ready))
      .mockResolvedValueOnce(json(blocked, 202))
      .mockResolvedValueOnce(json({ ...ready, deletion_request: blocked }));
    vi.stubGlobal("fetch", fetcher);
    const view = render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={capabilities}
      />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Request deletion" }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Request document deletion",
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Cancel" }),
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    await userEvent.click(
      screen.getByRole("button", { name: "Request deletion" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Request deletion",
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("region", { name: "Deletion request" }),
      ).toHaveTextContent("Deletion blocked"),
    );
    expect(screen.getByText(/policy.*unavailable/i)).toBeVisible();
    expect(
      screen.queryByText("Deletion requested — not used for grounded answers"),
    ).not.toBeInTheDocument();
    view.unmount();
    render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={capabilities}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("region", { name: "Deletion request" }),
      ).toHaveTextContent("Deletion blocked"),
    );
    expect(screen.getByText(/policy.*unavailable/i)).toBeVisible();
  });

  it.each(["requested", "processing", "succeeded", "failed"] as const)(
    "renders the persisted explicit %s deletion fixture",
    async (state) => {
      detail({
        ...ready,
        deletion_request: {
          request_id: "fixture-request",
          document_id: "doc-1",
          state,
          failure_reason: state === "failed" ? "FIXTURE_FAILURE" : null,
        },
        answer_availability: state === "failed" ? "available" : "unavailable",
      });
      expect(
        await screen.findByRole("region", { name: "Deletion request" }),
      ).toHaveTextContent(
        state === "requested" ? "Deletion requested" : `Deletion ${state}`,
      );
      if (state === "failed")
        expect(screen.getByText("FIXTURE_FAILURE")).toBeVisible();
    },
  );

  it("refreshes a changed source after reprocess conflict before retrying", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json(ready))
      .mockResolvedValueOnce(json({ detail: "conflict" }, 409))
      .mockResolvedValueOnce(
        json({
          ...ready,
          current_document_version_id: "version-latest",
          revision: 8,
        }),
      )
      .mockResolvedValueOnce(
        json({ ingestion_job_id: "job-2", status: "succeeded" }),
      )
      .mockResolvedValueOnce(
        json({
          ...ready,
          current_document_version_id: "version-latest",
          revision: 8,
        }),
      );
    vi.stubGlobal("fetch", fetcher);
    render(
      <DocumentDetail
        workspaceId="ws-1"
        documentId="doc-1"
        capabilities={capabilities}
      />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Reprocess document" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("changed");
    await userEvent.click(
      screen.getByRole("button", { name: "Reprocess document" }),
    );
    await waitFor(() =>
      expect(
        fetcher.mock.calls.filter(([, init]) => init?.method === "POST"),
      ).toHaveLength(2),
    );
    expect(fetcher.mock.calls[3][0]).toContain("/version-latest/reprocess");
  });

  it("discards stale list responses and upload intent when the Workspace changes", async () => {
    let resolveOld!: (value: Response) => void;
    const fetcher = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve;
          }),
      )
      .mockResolvedValueOnce(
        json({
          documents: [
            {
              ...ready,
              workspace_id: "ws-2",
              source_name: "new-workspace.pdf",
            },
          ],
        }),
      );
    vi.stubGlobal("fetch", fetcher);
    const view = render(
      <DocumentList workspaceId="ws-1" capabilities={capabilities} />,
    );
    await openUpload();
    view.rerender(
      <DocumentList workspaceId="ws-2" capabilities={capabilities} />,
    );
    await screen.findByRole("link", { name: "new-workspace.pdf" });
    resolveOld(json({ documents: [ready] }));
    await waitFor(() =>
      expect(
        screen.queryByRole("link", { name: "manual.pdf" }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("composes the authenticated selector and switches to the new Documents list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/documents")) return json({ documents: [ready] });
        if (url.includes("?archived"))
          return json({
            items: [
              {
                id: "ws-2",
                name: "Other workspace",
                archived: false,
                revision: 1,
              },
            ],
            next_cursor: null,
          });
        if (url === "/api/workspace-selection")
          return json({ workspaceId: "ws-2" });
        return json({
          id: "ws-1",
          name: "Authenticated workspace",
          archived: false,
          revision: 1,
        });
      }),
    );
    render(
      <DocumentList
        workspaceId="ws-1"
        workspaceName="Untrusted label"
        capabilities={capabilities}
      />,
    );
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Switch workspace: Authenticated workspace",
      }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Other workspace" }),
    );
    expect(navigation.push).toHaveBeenCalledWith("/workspaces/ws-2/documents");
    expect(screen.queryByText("Untrusted label")).not.toBeInTheDocument();
  });
});
