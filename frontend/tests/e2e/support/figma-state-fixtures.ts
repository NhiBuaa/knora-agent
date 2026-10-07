import type { Page } from "@playwright/test";
import type {
  ConversationResponse,
  DocumentResponse,
  TurnResponse,
  WorkspaceResponse,
} from "@/generated/knora-openapi";
import inventory from "../../../../docs/design/figma-ui-inventory-2026-10-05.json";

export const visualStates = [
  ...inventory.screens,
  ...inventory.panelStates.map((state) => ({ ...state, group: "panels" })),
  ...inventory.responseStates.map((state) => ({
    ...state,
    group: "responses",
  })),
];
/** Lookup prototypes are focused fixtures, outside the original 51-state capture loop. */
export const fixtureStates = [
  ...visualStates,
  {
    id: "216:448",
    name: "Prototype · Operator · 02 Traces lookup",
    group: "operator",
  },
  {
    id: "216:698",
    name: "Prototype · Operator · 04 Evaluations lookup",
    group: "operator",
  },
];
export const nativeStates = new Set([
  "228:212",
  "228:251",
  "237:251",
  "237:313",
  "242:272",
  "242:333",
  "242:389",
  "246:311",
  "246:404",
]);
export const workspace: WorkspaceResponse = {
  id: "fixture-workspace",
  name: "Research workspace",
  archived: false,
  revision: 4,
  created_at: "2026-10-05T00:00:00Z",
};
export const workspaces: WorkspaceResponse[] = [
  workspace,
  ...["Policy workspace", "Reporting workspace"].map((name, index) => ({
    ...workspace,
    id: `fixture-workspace-${index}`,
    name,
  })),
];
export const conversation: ConversationResponse = {
  id: "fixture-conversation",
  workspace_id: workspace.id,
  title: "Annual reporting structure",
  title_source: "manual",
  archived: false,
  revision: 3,
  updated_at: "2026-10-05T00:00:00Z",
};
export const conversations: ConversationResponse[] = [
  conversation,
  ...["Policy exceptions", "Submission checklist", "Archive requirements"].map(
    (title, index) => ({
      ...conversation,
      id: `fixture-conversation-${index}`,
      title,
    }),
  ),
];
export const document: DocumentResponse = {
  document_id: "fixture-document",
  workspace_id: workspace.id,
  source_key: "guidelines-2024",
  source_name: "Teacher Manh – Guidelines 2024.pdf",
  archived: false,
  revision: 7,
  current_document_version_id: "fixture-version",
  served_document_version_id: "fixture-version",
  serving_state: "current",
  ingestion_job_id: null,
  ingestion_status: "succeeded",
  embedding_readiness: "ready",
  reprocess_supported: true,
  answer_availability: "available",
  last_processed_at: "2026-10-05T00:00:00Z",
  deletion_request: null,
};
export const documents: DocumentResponse[] = [
  document,
  {
    ...document,
    document_id: "fixture-processing",
    source_name: "Reporting policy.pdf",
    ingestion_status: "processing",
    serving_state: "unavailable",
    answer_availability: "unavailable",
    embedding_readiness: "not_indexed",
  },
  {
    ...document,
    document_id: "fixture-embedding",
    source_name: "Archive requirements.md",
    embedding_readiness: "not_indexed",
    answer_availability: "unavailable",
  },
  {
    ...document,
    document_id: "fixture-failed",
    source_name: "Submission checklist.txt",
    ingestion_status: "failed",
    serving_state: "unavailable",
    answer_availability: "unavailable",
    embedding_readiness: "not_indexed",
  },
  {
    ...document,
    document_id: "fixture-archived",
    source_name: "Legacy handbook.pdf",
    archived: true,
    answer_availability: "unavailable",
  },
];
export const answered: TurnResponse = {
  id: "fixture-turn",
  conversation_id: conversation.id,
  sequence: 1,
  question: "How many chapters are in the report?",
  status: "answered",
  stage: null,
  error_code: null,
  result: {
    decision: "ANSWER",
    answer:
      "The reporting guideline explicitly defines a seven-chapter structure. The chapter list and ordering are specified in the report-structure section of the indexed document.",
    refusal_reason: null,
    trace_id: "fixture-trace",
    workspace_id: workspace.id,
    citations: [
      {
        evidence_id: "E1",
        document_id: document.document_id,
        document_version_id: "fixture-version",
        source_key: document.source_key,
        source_name: document.source_name,
        heading_path: ["Report structure"],
        start_line: 12,
        end_line: 18,
        excerpt:
          "The report consists of 7 chapters. Chapter 1 introduces the topic, followed by the remaining chapters in the prescribed order.",
        content_checksum: "fixture-checksum",
        page_start: 12,
        page_end: 12,
        start_offset: 0,
        end_offset: 149,
      },
      {
        evidence_id: "E2",
        document_id: document.document_id,
        document_version_id: "fixture-version",
        source_key: document.source_key,
        source_name: document.source_name,
        heading_path: ["Report structure"],
        start_line: 19,
        end_line: 24,
        excerpt:
          "Follow the full chapter order described in the report structure.",
        content_checksum: "fixture-checksum",
        page_start: 12,
        page_end: 13,
        start_offset: 149,
        end_offset: 210,
      },
    ],
  },
};

export function turnForState(state: string): TurnResponse {
  if (["128:111", "4:190"].includes(state))
    return {
      ...answered,
      question: "What is the late-submission policy?",
      status: "refused",
      result: {
        ...answered.result!,
        decision: "REFUSAL",
        answer: null,
        citations: [],
        refusal_reason: "INSUFFICIENT_EVIDENCE",
      },
    };
  if (["128:108", "128:112", "4:179"].includes(state))
    return {
      ...answered,
      status: "processing",
      stage: state === "128:108" ? null : "retrieving",
      result: null,
    };
  if (["128:118", "4:201"].includes(state))
    return { ...answered, status: "interrupted", result: null };
  if (state === "4:212")
    return {
      ...answered,
      status: "failed",
      result: null,
      error_code: "SYSTEM_FAILURE",
    };
  return answered;
}
export function documentForState(state: string): DocumentResponse {
  if (state === "128:125")
    return { ...document, archived: true, answer_availability: "unavailable" };
  if (state === "128:131")
    return {
      ...document,
      answer_availability: "unavailable",
      deletion_request: {
        document_id: document.document_id,
        request_id: "fixture-request",
        state: "requested",
      },
    };
  return document;
}
export function statePath(state: string): string {
  if (nativeStates.has(state)) return `/native/${state.replace(":", "-")}.html`;
  if (state === "228:293") return "/auth/unavailable";
  if (state === "228:326") return "/auth/failed";
  if (["152:128"].includes(state)) return "/workspaces";
  if (["154:431", "166:211", "166:290"].includes(state))
    return "/workspaces/archived";
  if (state === "194:194") return "/operator/operations";
  if (state === "216:448") return "/operator/traces";
  if (state === "216:698") return "/operator/evaluations";
  if (state === "198:200") return "/operator/traces/fixture-trace";
  if (state === "206:206") return "/operator/evaluations/fixture-report";
  if (["128:122", "128:125", "128:128", "128:131"].includes(state))
    return `/workspaces/${workspace.id}/documents/${document.document_id}`;
  if (["128:120", "128:121", "183:334"].includes(state))
    return `/workspaces/${workspace.id}/documents`;
  return `/workspaces/${workspace.id}/conversations/${conversation.id}`;
}

/** Deliberately narrow API double: no credentials, authority, network fallback or arbitrary scope. */
export function fixtureResponse(
  state: string,
  path: string,
  method: string,
): unknown {
  if (!fixtureStates.some((item) => item.id === state))
    throw new Error("Unrecognized fixture request");
  const url = new URL(path, "http://fixture.invalid");
  const base = `/api/v1/workspaces/${workspace.id}`;
  if (
    state === "183:176" &&
    method === "POST" &&
    url.pathname === `${base}/restore`
  )
    return { ...workspace, archived: false, revision: workspace.revision + 1 };
  if (
    state === "183:176" &&
    method === "POST" &&
    url.pathname === "/api/v1/workspaces/resolve"
  )
    return {
      state: "ACTIVE",
      workspace: {
        ...workspace,
        archived: false,
        revision: workspace.revision + 1,
      },
    };
  if (
    state === "183:176" &&
    method === "POST" &&
    url.pathname === "/api/workspace-selection"
  )
    return { workspaceId: workspace.id };
  if (method === "GET" && url.pathname === "/api/v1/workspaces")
    return {
      items:
        url.searchParams.get("archived") === "true"
          ? state === "166:290" || url.searchParams.get("q")
            ? []
            : workspaces.map((item) => ({ ...item, archived: true }))
          : workspaces,
      next_cursor: null,
    };
  if (method === "GET" && url.pathname === base)
    return { ...workspace, archived: state === "183:176" };
  if (method === "GET" && url.pathname === `${base}/documents`)
    return { documents: state === "183:334" ? [document] : documents };
  if (
    method === "GET" &&
    url.pathname === `${base}/documents/${document.document_id}`
  )
    return documentForState(state);
  if (method === "GET" && url.pathname === `${base}/conversations`)
    return { items: conversations, next_cursor: null };
  if (
    method === "GET" &&
    url.pathname === `${base}/conversations/${conversation.id}/turns`
  )
    return {
      items: [
        "128:109",
        "140:104",
        "148:116",
        "154:134",
        "154:290",
        "228:424",
      ].includes(state)
        ? []
        : [turnForState(state)],
      next_cursor: null,
    };
  if (
    method === "GET" &&
    url.pathname ===
      `${base}/conversations/${conversation.id}/turns/${answered.id}`
  )
    return turnForState(state);
  throw new Error("Unrecognized fixture request");
}

export async function prepareFixture(page: Page, state: string) {
  const unexpected: string[] = [];
  await page.clock.setFixedTime(new Date("2026-10-05T12:00:00Z"));
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    try {
      const body = fixtureResponse(state, request.url(), request.method());
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    } catch {
      unexpected.push(`${request.method()} ${new URL(request.url()).pathname}`);
      await route.fulfill({
        status: 501,
        contentType: "application/json",
        body: '{"code":"FIXTURE_UNEXPECTED_REQUEST"}',
      });
    }
  });
  const narrowCreation =
    state === "148:116" && (page.viewportSize()?.width ?? 1440) < 960;
  await page.goto(
    `${narrowCreation ? "/workspaces" : statePath(state)}?state=${encodeURIComponent(state)}`,
  );
  await page.evaluate(() => window.document.fonts.ready);
  if (nativeStates.has(state)) {
    const failedStyles = await page.evaluate(async () => {
      const links = Array.from(
        window.document.querySelectorAll<HTMLLinkElement>(
          'link[rel="stylesheet"]',
        ),
      );
      const responses = await Promise.all(
        links.map(
          async (link) =>
            [new URL(link.href).pathname, (await fetch(link.href)).ok] as const,
        ),
      );
      return responses.filter(([, ok]) => !ok).map(([pathname]) => pathname);
    });
    if (failedStyles.length)
      throw new Error(
        `Native source fixture styles missing: ${failedStyles.join(", ")}`,
      );
    await page.evaluate(() => {
      window.document.addEventListener(
        "submit",
        (event) => event.preventDefault(),
        true,
      );
    });
    return unexpected;
  }
  if (["228:293", "228:326"].includes(state)) return unexpected;
  if (["128:107", "128:115"].includes(state))
    await page.getByRole("button", { name: /citation 1/i }).click();
  if (["128:108", "4:67", "4:126"].includes(state))
    await page.getByRole("button", { name: "Collapse rail" }).click();
  if (["4:10", "4:126"].includes(state))
    await page.getByRole("button", { name: "Close evidence" }).click();
  if (state === "4:99")
    await page.getByRole("button", { name: "Hide rail" }).click();
  if (state === "140:104")
    await page.getByRole("button", { name: /Switch workspace:/ }).click();
  if (state === "148:116") {
    if (!narrowCreation)
      await page.getByRole("button", { name: /Switch workspace:/ }).click();
    await page
      .getByRole("button", {
        name: narrowCreation ? "Create workspace" : "+ Create workspace",
        exact: true,
      })
      .click();
    await page
      .getByLabel("Workspace name", { exact: true })
      .fill("Research workspace");
  }
  if (["154:134", "154:290"].includes(state)) {
    await page.getByRole("button", { name: "Workspace actions" }).click();
    if (state === "154:290")
      await page.getByRole("menuitem", { name: "Archive workspace" }).click();
  }
  if (state === "166:211") {
    await page
      .getByRole("searchbox", { name: /search archived/i })
      .fill("No matching workspace");
    await page
      .getByRole("heading", { name: "No archived workspaces found" })
      .waitFor();
  }
  if (state === "228:424")
    await page.getByRole("button", { name: /Account:/ }).click();
  if (state === "128:121") {
    await page
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    await page.getByLabel(/file/i).setInputFiles({
      name: "Reporting policy.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\nfixture source only"),
    });
  }
  if (state === "128:120") {
    await page.getByRole("checkbox", { name: "Show archived" }).check();
    await page
      .getByRole("button", {
        name: `Actions for ${document.source_name}`,
        exact: true,
      })
      .click();
  }
  if (state === "128:128")
    await page
      .getByRole("button", { name: "Request deletion", exact: true })
      .click();
  await page.locator("[data-fixture-state]").waitFor();
  await page
    .getByText("Loading history…", { exact: true })
    .waitFor({ state: "hidden" });
  await page
    .getByText("Loading documents…", { exact: true })
    .waitFor({ state: "hidden" });
  return unexpected;
}
