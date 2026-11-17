import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentList } from "@/components/documents/DocumentList";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

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
});

describe("Documents Optimistic Upload", () => {
  it("immediately renders optimistic document row on upload click before POST resolves", async () => {
    let resolvePost: (value: Response) => void;
    const postPromise = new Promise<Response>((resolve) => {
      resolvePost = resolve;
    });

    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, options?: RequestInit) => {
        if (options?.method === "POST" && url.includes("/documents")) {
          return postPromise;
        }
        if (url.includes("/ingestion-jobs/")) {
          return Promise.resolve(jsonResponse({ status: "queued" }));
        }
        return Promise.resolve(jsonResponse({ documents: [] }));
      });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentList workspaceId="ws-1" capabilities={["documents:write"]} />,
    );
    await screen.findByText("No documents yet.");

    // Open upload dialog and select file
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    fireEvent.change(screen.getByLabelText("Document file"), {
      target: {
        files: [
          new File(["sample content"], "report-2026.pdf", {
            type: "application/pdf",
          }),
        ],
      },
    });

    // Click submit in modal
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Upload document",
      }),
    );

    // Optimistic row should immediately show in the document list
    expect(
      (await screen.findAllByText("report-2026.pdf")).length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText(/Uploading|Processing|Queued/i).length,
    ).toBeGreaterThan(0);

    // Resolve POST response
    await act(async () => {
      resolvePost!(
        jsonResponse(
          {
            document_id: "doc-new-123",
            document_version_id: "version-1",
            ingestion_job_id: "job-new-123",
            status: "queued",
            submission_outcome: "created",
          },
          202,
        ),
      );
    });

    // Document should now be confirmed in the list with document_id and queued status
    await waitFor(() => {
      expect(screen.getByText("report-2026.pdf")).toBeInTheDocument();
      expect(screen.getByText("Queued")).toBeInTheDocument();
    });
  });

  it("adds the new document directly from POST response into state without waiting for list reload", async () => {
    let resolveSecondGet: (res: Response) => void;
    const secondGetPromise = new Promise<Response>((resolve) => {
      resolveSecondGet = resolve;
    });

    let getCount = 0;
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, init?: RequestInit) => {
        if (init?.method === "POST" && url.includes("/documents")) {
          return Promise.resolve(
            jsonResponse(
              {
                document_id: "doc-manual-999",
                document_version_id: "version-1",
                ingestion_job_id: "job-999",
                status: "queued",
                submission_outcome: "created",
              },
              202,
            ),
          );
        }
        if (url.includes("/ingestion-jobs/")) {
          return Promise.resolve(jsonResponse({ status: "queued" }));
        }
        getCount++;
        if (getCount === 1) {
          return Promise.resolve(jsonResponse({ documents: [] }));
        }
        return secondGetPromise;
      });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentList workspaceId="ws-1" capabilities={["documents:write"]} />,
    );
    await screen.findByText("No documents yet.");

    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    fireEvent.change(screen.getByLabelText("Document file"), {
      target: {
        files: [new File(["sample"], "spec.pdf", { type: "application/pdf" })],
      },
    });

    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Upload document",
      }),
    );

    // Verify document row is ALREADY present and confirmed directly from POST response!
    await waitFor(() => {
      expect(screen.getByText("spec.pdf")).toBeInTheDocument();
      expect(screen.getByText("Queued")).toBeInTheDocument();
    });

    resolveSecondGet!(jsonResponse({ documents: [] }));
  });

  it("clears file picker input value when upload dialog is cancelled", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ documents: [] }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DocumentList workspaceId="ws-1" capabilities={["documents:write"]} />,
    );
    await screen.findByText("No documents yet.");

    // Open upload dialog and select file
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    const input = screen.getByLabelText("Document file") as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [
          new File(["sample"], "policy.pdf", { type: "application/pdf" }),
        ],
      },
    });

    expect(screen.getByText("policy.pdf")).toBeInTheDocument();

    // Click Cancel
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Cancel",
      }),
    );

    // Verify input value is cleared
    expect(input.value).toBe("");
  });
});
