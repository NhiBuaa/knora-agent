import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { DatasetWorkbench } from "@/components/operator/datasets/DatasetWorkbench";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const source = {
  id: "s1",
  dataset_id: "d1",
  document_id: "doc1",
  document_version_id: "ver1",
  filename: "guide.pdf",
  raw_sha256: "a".repeat(64),
  byte_size: 100,
  status: "READY",
  failure_code: null,
  snapshot_id: "snap1",
};

it("does not show a late extraction response beside another original PDF", async () => {
  let finishFirst!: (response: Response) => void;
  const firstPage = new Promise<Response>((resolve) => {
    finishFirst = resolve;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      if (input.includes("/sources/s1/pages/")) return firstPage;
      if (input.includes("/sources/s2/pages/"))
        return Response.json({
          source_id: "s2",
          document_version_id: "ver2",
          snapshot_id: "snap2",
          extraction_sha256: "b".repeat(64),
          configuration_sha256: "c".repeat(64),
          physical_page: 1,
          text: "Second document evidence",
          content_checksum: "d".repeat(64),
        });
      return Response.json({
        id: "d1",
        workspace_id: "w1",
        name: "Review",
        status: "DRAFT",
        sources: [
          source,
          {
            ...source,
            id: "s2",
            document_version_id: "ver2",
            filename: "second.pdf",
            snapshot_id: "snap2",
          },
        ],
      });
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await userEvent.click(
    await screen.findByRole("button", { name: "guide.pdf" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "second.pdf" }));
  expect(
    await screen.findByText("Second document evidence"),
  ).toBeInTheDocument();
  await act(async () => {
    finishFirst(
      Response.json({
        source_id: "s1",
        document_version_id: "ver1",
        snapshot_id: "snap1",
        extraction_sha256: "b".repeat(64),
        configuration_sha256: "c".repeat(64),
        physical_page: 1,
        text: "Stale first document evidence",
        content_checksum: "d".repeat(64),
      }),
    );
  });
  expect(
    screen.queryByText("Stale first document evidence"),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Second document evidence")).toBeInTheDocument();
  expect(screen.getByTitle("Original PDF")).toHaveAttribute(
    "src",
    "/api/operator/evaluation/datasets/d1/sources/s2/original?workspaceId=w1#page=1",
  );
});

it("clears the previous workspace dataset while the next workspace loads", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      if (input.includes("workspaceId=w2"))
        return new Promise<Response>(() => {});
      return Response.json({
        id: "d1",
        workspace_id: "w1",
        name: "Workspace one dataset",
        status: "DRAFT",
        sources: [source],
      });
    }),
  );
  const { rerender } = render(
    <DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />,
  );
  expect(
    await screen.findByRole("heading", { name: "Workspace one dataset" }),
  ).toBeInTheDocument();
  rerender(<DatasetWorkbench workspaceId="w2" initialDatasetId="d2" />);
  expect(
    screen.queryByRole("heading", { name: "Workspace one dataset" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "guide.pdf" }),
  ).not.toBeInTheDocument();
});

it("creates a dataset and exposes the uploaded PDF for review", async () => {
  let uploaded = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      if (init?.method === "POST" && input.includes("/sources?")) {
        const file = (init.body as FormData).get("file") as File;
        if (file.name !== "guide.pdf" || !init.headers)
          return new Response(null, { status: 400 });
        uploaded = true;
        return Response.json(source, { status: 201 });
      }
      if (init?.method === "POST") {
        if (JSON.parse(init.body as string).name !== "Manual gold")
          return new Response(null, { status: 400 });
        return Response.json(
          {
            id: "d1",
            workspace_id: "w1",
            name: "Manual gold",
            status: "DRAFT",
          },
          { status: 201 },
        );
      }
      if (input.includes("/d1?"))
        return Response.json({
          id: "d1",
          workspace_id: "w1",
          name: "Manual gold",
          status: "DRAFT",
          sources: uploaded ? [source] : [],
        });
      return Response.json({ items: [] });
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" />);
  await userEvent.type(
    screen.getByRole("textbox", { name: "Dataset name" }),
    "Manual gold",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create dataset" }));
  expect(
    await screen.findByRole("heading", { name: "Manual gold" }),
  ).toBeInTheDocument();
  await userEvent.upload(
    screen.getByLabelText("PDF files"),
    new File(["%PDF-test"], "guide.pdf", { type: "application/pdf" }),
  );
  expect(
    (screen.getByLabelText("PDF files") as HTMLInputElement).files,
  ).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Upload PDFs" })).toBeEnabled();
  // JSDOM reports valueMissing for user-event's populated FileList.
  fireEvent.submit(
    screen.getByRole("button", { name: "Upload PDFs" }).closest("form")!,
  );
  expect(
    await screen.findByRole("button", { name: "guide.pdf" }),
  ).toBeInTheDocument();
  expect(screen.getByText("READY")).toBeInTheDocument();
});

it("reports a failed dataset lookup without leaving an unhandled request", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) =>
      input.includes("/d1?")
        ? new Response(null, { status: 404 })
        : Response.json({
            items: [
              {
                id: "d1",
                workspace_id: "w1",
                name: "Unavailable draft",
                status: "DRAFT",
                format: "pdf-gold-v1",
              },
            ],
          }),
    ),
  );
  render(<DatasetWorkbench workspaceId="w1" />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Unavailable draft" }),
  );
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Dataset is unavailable",
    ),
  );
});

it("reviews a physical page beside the retained original PDF", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      if (input.includes("/pages/1"))
        return Response.json({
          source_id: "s1",
          document_version_id: "ver1",
          snapshot_id: "snap1",
          extraction_sha256: "b".repeat(64),
          configuration_sha256: "c".repeat(64),
          physical_page: 1,
          text: "Garden evidence on page one",
          content_checksum: "d".repeat(64),
        });
      return Response.json({
        id: "d1",
        workspace_id: "w1",
        name: "Review",
        status: "DRAFT",
        sources: [source],
      });
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await userEvent.click(
    await screen.findByRole("button", { name: /guide.pdf/i }),
  );
  expect(
    await screen.findByText("Garden evidence on page one"),
  ).toBeInTheDocument();
  expect(screen.getByTitle("Original PDF")).toHaveAttribute(
    "src",
    "/api/operator/evaluation/datasets/d1/sources/s1/original?workspaceId=w1#page=1",
  );
  expect(screen.getByText("ver1")).toBeInTheDocument();
});

it("keeps failed extraction visible and the original reviewable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        id: "d1",
        workspace_id: "w1",
        name: "Review",
        status: "DRAFT",
        sources: [
          {
            ...source,
            status: "FAILED",
            failure_code: "PDF_TEXT_INSUFFICIENT",
            snapshot_id: null,
          },
        ],
      }),
    ),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await userEvent.click(
    await screen.findByRole("button", { name: /guide.pdf/i }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "PDF_TEXT_INSUFFICIENT",
  );
  expect(screen.getByTitle("Original PDF")).toBeInTheDocument();
  expect(
    screen.queryByText("Garden evidence on page one"),
  ).not.toBeInTheDocument();
});
