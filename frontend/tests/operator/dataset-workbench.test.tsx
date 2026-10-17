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
import { DatasetWorkbench as Workbench } from "@/components/operator/datasets/DatasetWorkbench";

function DatasetWorkbench(props: React.ComponentProps<typeof Workbench>) {
  return (
    <Workbench
      capabilities={[
        "operator:read",
        "evaluations:write",
        "evaluations:approve",
        "documents:read",
        "documents:write",
      ]}
      {...props}
    />
  );
}

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

const dataset = {
  id: "d1",
  workspace_id: "w1",
  name: "Review",
  status: "DRAFT",
  sources: [source],
};

const extractedPage = {
  source_id: "s1",
  document_version_id: "ver1",
  snapshot_id: "snap1",
  extraction_sha256: "b".repeat(64),
  configuration_sha256: "c".repeat(64),
  physical_page: 1,
  text: "Page one evidence",
  content_checksum: "d".repeat(64),
};

it("downloads the selected original PDF in the current Workspace", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) =>
      Response.json(
        input.includes("/pages/")
          ? { ...extractedPage, source_id: "s2" }
          : {
              ...dataset,
              sources: [source, { ...source, id: "s2", filename: "notes.pdf" }],
            },
      ),
    ),
  );
  render(
    <DatasetWorkbench
      workspaceId="w1"
      initialDatasetId="d1"
      capabilities={["operator:read", "documents:read", "evaluations:approve"]}
    />,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "notes.pdf" }),
  );

  const download = screen.getByRole("link", { name: "Download original PDF" });
  expect(download).toHaveAttribute(
    "href",
    "/api/operator/evaluation/datasets/d1/sources/s2/original?workspaceId=w1#page=1",
  );
  expect(download).toHaveAttribute("download", "notes.pdf");
});

it("clears loaded extraction when the physical page changes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) =>
      Response.json(input.includes("/pages/") ? extractedPage : dataset),
    ),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await userEvent.click(
    await screen.findByRole("button", { name: "guide.pdf" }),
  );
  expect(await screen.findByText("Page one evidence")).toBeInTheDocument();

  fireEvent.change(screen.getByRole("spinbutton", { name: "Physical page" }), {
    target: { value: "2" },
  });

  expect(screen.getByTitle("Original PDF")).toHaveAttribute(
    "src",
    "/api/operator/evaluation/datasets/d1/sources/s1/original?workspaceId=w1#page=2",
  );
  expect(screen.queryByText("Page one evidence")).not.toBeInTheDocument();
  expect(screen.getByText("Extracted page unavailable.")).toBeInTheDocument();
});

it("ignores a pending extraction after editing the physical page", async () => {
  let finishPage!: (response: Response) => void;
  const pendingPage = new Promise<Response>((resolve) => {
    finishPage = resolve;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      if (input.includes("/pages/1?")) return pendingPage;
      if (input.includes("/pages/2?"))
        return Response.json({
          ...extractedPage,
          physical_page: 2,
          text: "Page two evidence",
        });
      return Response.json(dataset);
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await userEvent.click(
    await screen.findByRole("button", { name: "guide.pdf" }),
  );
  fireEvent.change(screen.getByRole("spinbutton", { name: "Physical page" }), {
    target: { value: "2" },
  });
  await act(async () => {
    finishPage(Response.json(extractedPage));
  });

  expect(screen.queryByText("Page one evidence")).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Show extracted page" }),
  );
  expect(await screen.findByText("Page two evidence")).toBeInTheDocument();
});

it.each(["", "0", "-1", "1.5", "9007199254740992"])(
  "does not request an invalid physical page %j",
  async (value) => {
    const requestedPages: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        if (input.includes("/pages/")) {
          requestedPages.push(input);
          return Response.json(extractedPage);
        }
        return Response.json(dataset);
      }),
    );
    render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
    await userEvent.click(
      await screen.findByRole("button", { name: "guide.pdf" }),
    );
    await screen.findByText("Page one evidence");
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Physical page" }),
      {
        target: { value },
      },
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Show extracted page" }),
    );

    expect(requestedPages).toHaveLength(1);
    expect(screen.queryByText("Page one evidence")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "positive whole number",
    );
  },
);

it("replays a partial upload batch without duplicating its committed sources", async () => {
  const requests: { filename: string; key: string | null }[] = [];
  const committed = new Map<string, string>();
  let loseResponse = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      if (init?.method === "POST" && input.includes("/sources?")) {
        const file = (init.body as FormData).get("file") as File;
        const key = new Headers(init.headers).get("Idempotency-Key");
        requests.push({ filename: file.name, key });
        if (!key) return new Response(null, { status: 400 });
        committed.set(key, file.name);
        if (file.name === "second.pdf" && loseResponse) {
          loseResponse = false;
          throw new Error("Upload response lost.");
        }
        return Response.json(source, { status: 201 });
      }
      return Response.json(dataset);
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await screen.findByRole("heading", { name: "Review" });
  await userEvent.upload(screen.getByLabelText("PDF files"), [
    new File(["%PDF-first"], "guide.pdf", { type: "application/pdf" }),
    new File(["%PDF-second"], "second.pdf", { type: "application/pdf" }),
  ]);
  const submit = screen.getByRole("button", { name: "Upload PDFs" });
  fireEvent.submit(submit.closest("form")!);
  await waitFor(() => expect(submit).toBeEnabled());
  fireEvent.submit(submit.closest("form")!);
  await waitFor(() => expect(submit).toBeEnabled());

  expect(requests).toHaveLength(4);
  expect(requests[0].key).toBeTruthy();
  expect(requests[1].key).not.toBe(requests[0].key);
  expect(requests.slice(2)).toEqual(requests.slice(0, 2));
  expect([...committed.values()]).toEqual(["guide.pdf", "second.pdf"]);
  expect(
    (screen.getByLabelText("PDF files") as HTMLInputElement).files,
  ).toHaveLength(0);
});

it("keeps an upload error visible after refreshing dataset details", async () => {
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: string, init?: RequestInit) => {
      if (init?.method === "POST") return new Response(null, { status: 413 });
      reads++;
      return Response.json(dataset);
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await screen.findByRole("heading", { name: "Review" });
  await userEvent.upload(
    screen.getByLabelText("PDF files"),
    new File(["%PDF-too-big"], "large.pdf", { type: "application/pdf" }),
  );
  const submit = screen.getByRole("button", { name: "Upload PDFs" });
  fireEvent.submit(submit.closest("form")!);
  await waitFor(() => expect(submit).toBeEnabled());

  expect(reads).toBe(2);
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Unable to upload large.pdf.",
  );
});

it("uses a new upload identity when the selected file changes", async () => {
  const keys: (string | null)[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        keys.push(new Headers(init.headers).get("Idempotency-Key"));
        return new Response(null, { status: 413 });
      }
      return Response.json(dataset);
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await screen.findByRole("heading", { name: "Review" });
  const input = screen.getByLabelText("PDF files");
  const submit = screen.getByRole("button", { name: "Upload PDFs" });
  for (const content of ["%PDF-first", "%PDF-changed"]) {
    await userEvent.upload(
      input,
      new File([content], "guide.pdf", { type: "application/pdf" }),
    );
    fireEvent.submit(submit.closest("form")!);
    await waitFor(() => expect(submit).toBeEnabled());
  }
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).not.toBe(keys[0]);
});

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

it("creates, reviews, and freezes a canonical answer case", async () => {
  let current: typeof dataset & {
    revision: number;
    cases: { case_id: string }[];
    reviews: { case_id: string; decision: string }[];
    reference?: { version: number; digest: string };
  } = { ...dataset, revision: 0, cases: [], reviews: [] };
  const requests: { method: string; url: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      if (init?.method && init.method !== "GET") {
        const body = init.body ? JSON.parse(init.body as string) : undefined;
        requests.push({ method: init.method, url: input, body });
        if (input.includes("/cases/") && init.method === "PUT") {
          current = {
            ...current,
            revision: 1,
            cases: [body.case],
            reviews: [],
          };
          return Response.json(current);
        }
        if (input.includes("/review")) {
          current = {
            ...current,
            revision: 2,
            reviews: [
              {
                case_id: body.case_id ?? current.cases[0].case_id,
                decision: "ACCEPTED",
              },
            ],
          };
          return Response.json(current);
        }
        if (input.includes("/freeze")) {
          current = {
            ...current,
            revision: 3,
            status: "FROZEN",
            reference: { version: 1, digest: "e".repeat(64) },
          };
          return Response.json(current);
        }
      }
      if (input.includes("/gold-preview"))
        return Response.json({
          digest: "e".repeat(64),
          gold: { cases: current.cases },
        });
      return Response.json(current);
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await screen.findByRole("heading", { name: "Review" });
  await userEvent.type(
    screen.getByRole("textbox", { name: "Question" }),
    "What is here?",
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: "Reference answer" }),
    "A garden.",
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: /Required facts/i }),
    "garden",
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: "Evidence quote" }),
    "community garden",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add case" }));
  await screen.findByText("UNREVIEWED");
  await userEvent.type(
    screen.getByRole("textbox", { name: "Review note" }),
    "Checked against original PDF",
  );
  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  await screen.findByText("ACCEPTED");
  await userEvent.click(
    screen.getByRole("button", { name: "Freeze accepted cases" }),
  );
  await screen.findByText(/Gold v1/);
  expect(requests.map((request) => request.method)).toEqual([
    "PUT",
    "POST",
    "POST",
  ]);
});

it("does not offer writes or approval to a read-only operator", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(dataset)),
  );
  render(
    <DatasetWorkbench
      workspaceId="w1"
      initialDatasetId="d1"
      capabilities={["operator:read"]}
    />,
  );
  await screen.findByRole("heading", { name: "Review" });
  expect(
    screen.queryByRole("button", { name: "Add case" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Freeze accepted cases" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Upload PDFs" }),
  ).not.toBeInTheDocument();
});

it("allows original-PDF no-answer review after extraction failure with an explicit scope note", async () => {
  let saved: any;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        saved = JSON.parse(init.body as string).case;
        return Response.json({ ...dataset, cases: [saved], revision: 1 });
      }
      return Response.json({
        ...dataset,
        revision: 0,
        sources: [{ ...source, status: "FAILED", snapshot_id: null }],
      });
    }),
  );
  render(<DatasetWorkbench workspaceId="w1" initialDatasetId="d1" />);
  await screen.findByRole("heading", { name: "Review" });
  await userEvent.type(
    screen.getByRole("textbox", { name: "Question" }),
    "Is an unknown fact stated?",
  );
  await userEvent.selectOptions(
    screen.getByLabelText("Expected behavior"),
    "REFUSAL",
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: "No-answer verification note" }),
    "I checked all pages of this PDF for that fact.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add case" }));
  await waitFor(() =>
    expect(saved?.no_answer_scope).toEqual({
      checked_document_version_ids: ["ver1"],
      verification_note: "I checked all pages of this PDF for that fact.",
    }),
  );
});
