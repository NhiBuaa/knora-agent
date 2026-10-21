import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentList } from "@/components/documents/DocumentList";
import { DocumentDetail } from "@/components/documents/DocumentDetail";
import { documentStatus } from "@/lib/documents/presentation";
import type { DocumentResponse } from "@/generated/knora-openapi";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const document: DocumentResponse = {
  document_id: "doc",
  workspace_id: "workspace",
  source_key: "refund",
  source_name: "refund.pdf",
  archived: false,
  revision: 1,
  current_document_version_id: "version",
  served_document_version_id: null,
  serving_state: "unavailable",
  answer_availability: "unavailable",
  ingestion_job_id: "extraction",
  ingestion_status: "succeeded",
  indexing_job_id: "index",
  indexing_status: "processing",
  lexical_readiness: "not_indexed",
  embedding_readiness: "not_indexed",
  reprocess_supported: true,
  derivation_kind: "pdf_extraction",
  desired_lexical_generation_id: "desired-B",
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("lexical document lifecycle", () => {
  it.each([
    ["processing", "not_indexed", "Indexing…"],
    ["failed", "not_indexed", "Indexing failed"],
    ["succeeded", "ready", "Ready"],
    ["succeeded", "reindex_required", "Needs re-index"],
  ] as const)(
    "renders %s/%s without fabricated embedding readiness",
    (indexing_status, lexical_readiness, label) => {
      expect(
        documentStatus({ ...document, indexing_status, lexical_readiness })
          .label,
      ).toBe(label);
    },
  );

  it.each(["list", "detail"] as const)(
    "%s keeps polling after extraction succeeds",
    async (surface) => {
      const fetcher = vi.fn(async (url: string) =>
        json(
          url.includes("/ingestion-jobs/")
            ? {
                ingestion_job_id: "extraction",
                status: "succeeded",
                indexing_job_id: "index",
                indexing_status: "processing",
                lexical_readiness: "not_indexed",
                poll_after_seconds: 1,
                current_document_version_id: "version",
                serving_state: "unavailable",
                served_document_version_id: null,
              }
            : surface === "list"
              ? { documents: [document] }
              : document,
        ),
      );
      vi.stubGlobal("fetch", fetcher);
      if (surface === "list")
        render(
          <DocumentList
            workspaceId="workspace"
            capabilities={["documents:write"]}
          />,
        );
      else
        render(
          <DocumentDetail
            workspaceId="workspace"
            documentId="doc"
            capabilities={["documents:write"]}
          />,
        );
      expect((await screen.findAllByText("Indexing…")).length).toBeGreaterThan(
        0,
      );
      await waitFor(
        () =>
          expect(
            fetcher.mock.calls.filter(([url]) =>
              url.includes("/ingestion-jobs/extraction"),
            ).length,
          ).toBeGreaterThanOrEqual(2),
        { timeout: 2500 },
      );
      if (surface === "detail")
        expect(
          screen.getByRole("button", { name: /Reprocess/ }),
        ).toBeDisabled();
    },
  );

  it("list retries a failed lexical index using current desired profile", async () => {
    const failed = {
      ...document,
      indexing_status: "failed" as const,
      lexical_readiness: "reindex_required" as const,
    };
    const fetcher = vi.fn(async (url: string, init?: RequestInit) =>
      json(
        init?.method === "POST"
          ? {
              ingestion_job_id: "retry-extraction",
              status: "failed",
            }
          : url.includes("/ingestion-jobs/")
            ? { status: "failed" }
            : { documents: [failed] },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    vi.stubGlobal("crypto", { randomUUID: () => "retry-key" });
    render(
      <DocumentList
        workspaceId="workspace"
        capabilities={["documents:write"]}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: /Try again refund.pdf/ }),
    );
    await waitFor(() =>
      expect(
        fetcher.mock.calls.find(([, init]) => init?.method === "POST")?.[1]
          ?.body,
      ).toBe(JSON.stringify({ config_mode: "current" })),
    );
  });

  it.each(["list", "detail"] as const)(
    "%s retries failed extraction with its exact profile until a desired generation exists",
    async (surface) => {
      const failed = {
        ...document,
        ingestion_status: "failed",
        indexing_job_id: null,
        indexing_status: null,
        desired_lexical_generation_id: null,
      };
      const fetcher = vi.fn(async (url: string, init?: RequestInit) =>
        json(
          init?.method === "POST"
            ? {
                ingestion_job_id: "retry-extraction",
                status: "failed",
              }
            : url.includes("/ingestion-jobs/")
              ? {
                  ingestion_job_id: "extraction",
                  status: "failed",
                  derivation_kind: "pdf_extraction",
                  desired_lexical_generation_id: null,
                  current_document_version_id: "version",
                  serving_state: "unavailable",
                  served_document_version_id: null,
                }
              : surface === "list"
                ? { documents: [failed] }
                : failed,
        ),
      );
      vi.stubGlobal("fetch", fetcher);
      vi.stubGlobal("crypto", { randomUUID: () => "retry-key" });
      if (surface === "list")
        render(
          <DocumentList
            workspaceId="workspace"
            capabilities={["documents:write"]}
          />,
        );
      else
        render(
          <DocumentDetail
            workspaceId="workspace"
            documentId="doc"
            capabilities={["documents:write"]}
          />,
        );
      fireEvent.click(
        await screen.findByRole("button", {
          name: surface === "list" ? /Try again refund.pdf/ : /Reprocess/,
        }),
      );
      await waitFor(() =>
        expect(
          fetcher.mock.calls.find(([, init]) => init?.method === "POST")?.[1]
            ?.body,
        ).toBe(
          JSON.stringify({
            config_mode: "same_as_job",
            config_source_job_id: "extraction",
          }),
        ),
      );
    },
  );

  it("list uses desired B even when a newer extraction failed without a child", async () => {
    const failed = {
      ...document,
      ingestion_status: "failed",
      indexing_job_id: null,
      indexing_status: null,
    };
    const fetcher = vi.fn(async (_url: string, init?: RequestInit) =>
      json(
        init?.method === "POST"
          ? {
              ingestion_job_id: "retry-extraction",
              status: "failed",
            }
          : { documents: [failed] },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    vi.stubGlobal("crypto", { randomUUID: () => "retry-key" });
    render(
      <DocumentList
        workspaceId="workspace"
        capabilities={["documents:write"]}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: /Try again refund.pdf/ }),
    );
    await waitFor(() =>
      expect(
        fetcher.mock.calls.find(([, init]) => init?.method === "POST")?.[1]
          ?.body,
      ).toBe(JSON.stringify({ config_mode: "current" })),
    );
  });
});
