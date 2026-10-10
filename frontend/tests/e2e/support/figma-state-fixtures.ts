import type { Page } from "@playwright/test";
import type {
  ConversationResponse,
  DocumentResponse,
  OperatorEvaluationResponse,
  OperatorOperationsResponse,
  OperatorTraceResponse,
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
/** Operator prototypes are focused fixtures, outside the original 51-state capture loop. */
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
  {
    id: "216:345",
    name: "Prototype · Operator · 01 Operations",
    group: "operator",
  },
  {
    id: "216:573",
    name: "Prototype · Operator · 03 Trace detail",
    group: "operator",
  },
  {
    id: "216:755",
    name: "Prototype · Operator · 05 Evaluation unavailable",
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
/** Synthetic presentation projections, never observations of existing backend resources. */
export const prototypeOperations: OperatorOperationsResponse = {
  configuration_version: "runtime-config-v12",
  workspace_id: workspace.id,
  metrics: {
    queue_depth: 0,
    retry_rate: 0.024,
    cleanup_failure_total: 0,
    // Deliberately absent observation exercises unavailable, independently of valid zeros.
    orphan_discovery_total: null,
    oldest_job_age: 18,
    claim_latency_count: 124,
    claim_latency_sum: 18.4,
    lease_expiry_recovery_total: 1,
    cleanup_attempt_total: 32,
    orphan_reconciliation_total: 0,
  },
  histograms: {
    claim_latency_seconds: {
      count: 124,
      sum: 18.4,
      buckets: [
        [0.1, 38],
        [0.25, 91],
        [0.5, 118],
        [1, 124],
      ],
    },
  },
};
export const prototypeTrace: OperatorTraceResponse = {
  trace_id: "fixture-trace",
  workspace_id: workspace.id,
  trace_schema_version: 2,
  branch_observation_schema_version: 1,
  branch_observations: [],
  retrieval_configuration_id: "retrieval-m1-v1",
  embedding_configuration_id: "embedding-local-m1-v2",
  chunk_set_ids: ["fixture-chunk-set-12", "fixture-chunk-set-4"],
  embedding_set_ids: ["fixture-embedding-set-12", "fixture-embedding-set-4"],
  retrieval_latency_ms: 184,
  decision: "ANSWER",
  validation_outcome: "valid",
  refusal_reason: null,
  answer:
    "The report is organized into 7 chapters. The retrieved passages explicitly list the chapter structure and ordering.",
  parsed_markers: ["E1", "E2"],
  alias_mapping: { E1: "fixture-chunk-12", E2: "fixture-chunk-4" },
  candidate_decisions: [],
  candidates: [
    {
      workspace_id: workspace.id,
      chunk_id: "fixture-chunk-12",
      chunk_ordinal: 12,
      chunk_set_id: "fixture-chunk-set-12",
      document_version_id: "fixture-version-12",
      source_key: "Teacher Manh – Guidelines 2024.pdf",
      start_line: 84,
      end_line: 102,
      final_rank: 1,
      fusion_score: 0.86,
      final_decision: "SELECTED",
      decision_reason: null,
      vector_contribution: { status: "ELIGIBLE", rank: 1, score: 0.86 },
      fts_contribution: null,
      content: "“Seven chapters, presented in this order …”",
    },
    {
      workspace_id: workspace.id,
      chunk_id: "fixture-chunk-4",
      chunk_ordinal: 4,
      chunk_set_id: "fixture-chunk-set-4",
      document_version_id: "fixture-version-4",
      source_key: "Reporting policy.pdf",
      start_line: 31,
      end_line: 47,
      final_rank: 2,
      fusion_score: 0.72,
      final_decision: "SELECTED",
      decision_reason: null,
      vector_contribution: null,
      fts_contribution: { status: "ELIGIBLE", rank: 2, score: 0.72 },
      content:
        "“The required chapter structure follows the seven-part guideline …”",
    },
  ],
  provider_metadata: {
    timing: {
      clock_resolution_ms: 0.001,
      phases: {
        retrieval: { duration_ms: 184 },
        generation: { duration_ms: 612 },
        validation: { duration_ms: 24 },
      },
    },
    // Neither costs nor usage are supplied; the production view must retain unavailable.
  },
};
export const prototypeEvaluation: OperatorEvaluationResponse = {
  report_id: "fixture-report",
  workspace_id: workspace.id,
  availability: "unavailable",
  observation_failure: "EVALUATION_REPORT_UNAVAILABLE",
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
    return {
      ...answered,
      status: "interrupted",
      stage: "failure",
      error_code: "EXECUTION_OUTCOME_UNKNOWN",
      result: null,
    };
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
  if (state === "183:490") return `/workspaces/${workspace.id}`;
  if (["154:431", "166:211", "166:290"].includes(state))
    return "/workspaces/archived";
  if (["194:194", "216:345"].includes(state)) return "/operator/operations";
  if (state === "216:448") return "/operator/traces";
  if (state === "216:698") return "/operator/evaluations";
  if (["198:200", "216:573"].includes(state))
    return "/operator/traces/fixture-trace";
  if (["206:206", "216:755"].includes(state))
    return "/operator/evaluations/fixture-report";
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
  if (["216:345", "216:573", "216:755"].includes(state)) {
    // The three comparison compositions only hydrate the existing Workspace selector.
    if (method === "GET" && url.pathname === base && !url.search)
      return workspace;
    throw new Error("Unrecognized prototype comparison request");
  }
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
  if (["128:107", "128:115", "4:35", "4:67", "4:99"].includes(state))
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
