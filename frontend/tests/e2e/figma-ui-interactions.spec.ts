import { expect, test, type Page } from "@playwright/test";
import {
  prepareFixture,
  prototypeTrace,
  visualStates,
  fixtureStates,
  fixtureResponse,
  statePath,
} from "./support/figma-state-fixtures";
import { createHash, randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import { captureIdentity, openFigmaLogin } from "./support/figma-auth";
import type {
  IngestionJobStatusResponse,
  WorkspaceResponse,
  ConversationResponse,
  TurnResponse,
} from "../../generated/knora-openapi";

function writeLookupGeometry(evidence: string, geometry: unknown) {
  fs.mkdirSync(path.dirname(evidence), { recursive: true });
  fs.writeFileSync(
    `${evidence}-geometry.json`,
    JSON.stringify(geometry, null, 2),
  );
}

type SourceMeasurement = {
  name: string;
  node: string;
  selector: string;
  expected: Record<string, number | string>;
};
const prototypeEvidence =
  "../.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07";
const sha256 = (filename: string) =>
  createHash("sha256").update(fs.readFileSync(filename)).digest("hex");

async function operatorSourceGeometry(
  page: Page,
  state: string,
  width: number,
) {
  const operations = state === "216:345";
  const asset = operations ? "a4e11" : "bab86";
  // Only root metadata is inspected; source SVG drawing bytes are never adapted.
  const svgRoot = fs
    .readFileSync(`public/icons/figma/${asset}.svg`, "utf8")
    .match(/<svg\b[^>]*>/)![0];
  const root = {
    width: Number(svgRoot.match(/\bwidth="([^"]+)"/)![1]),
    height: Number(svgRoot.match(/\bheight="([^"]+)"/)![1]),
  };
  expect(root).toEqual(
    operations ? { width: 10, height: 6 } : { width: 11.4, height: 6.4 },
  );
  if (!operations)
    expect(sha256("public/icons/figma/bab86.svg").toUpperCase()).toBe(
      "864C1D2BB9B35ED4DD76DEE4346A2BF2BAE674A2B8E74EFBE6138A1651949911",
    );
  const geometry = await page.locator("main").evaluate((main) => {
    const box = (element: Element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        radius: style.borderRadius,
        fits: element.scrollWidth <= element.clientWidth,
        overflowY: style.overflowY,
      };
    };
    const word = (element: Element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      const ink = range.getBoundingClientRect();
      const parent = element.parentElement!.getBoundingClientRect();
      return {
        text: element.textContent,
        lines: range.getClientRects().length,
        ink: { x: ink.x, y: ink.y, width: ink.width, height: ink.height },
        textFitsParent:
          ink.left >= parent.left &&
          ink.right <= parent.right &&
          ink.top >= parent.top &&
          ink.bottom <= parent.bottom,
        ...box(element),
      };
    };
    const caret = main.querySelector<HTMLImageElement>(
      ".workspace-selector-trigger img",
    )!;
    const input = main.querySelector("form > div > input");
    const button = main.querySelector("form > div > button");
    const band = main.querySelector('dl[aria-label="Runtime signals"]');
    const columns = main.querySelector("article > div");
    const answer = main.querySelector(
      'section[aria-labelledby="observed-result-heading"] > p:last-of-type',
    );
    const badge = main.querySelector(
      'section[aria-labelledby="evaluation-heading"] > div > div > span',
    );
    return {
      selector: box(main.querySelector(".workspace-selector-heading")!),
      actions: box(main.querySelector(".kn-menu__trigger")!),
      caret: {
        src: caret.getAttribute("src"),
        loaded: caret.complete && caret.naturalWidth > 0,
        widthAttribute: caret.getAttribute("width"),
        heightAttribute: caret.getAttribute("height"),
        ...box(caret),
        slot: box(caret.parentElement!),
        insetX:
          caret.getBoundingClientRect().x -
          caret.parentElement!.getBoundingClientRect().x,
        insetY:
          caret.getBoundingClientRect().y -
          caret.parentElement!.getBoundingClientRect().y,
      },
      input: input && box(input),
      button: button && box(button),
      band: band && {
        ...box(band),
        cells: Array.from(band.children).map(box),
        missing: Array.from(
          band.querySelectorAll('dd[data-state="unavailable"]'),
        ).map(word),
      },
      columns: columns && {
        gap: getComputedStyle(columns).columnGap,
        children: Array.from(columns.children).map(box),
      },
      answer: answer && box(answer),
      badge: badge && box(badge),
      selected: Array.from(
        main.querySelectorAll(
          'section[aria-labelledby="candidate-heading"] .kn-status-badge > span:last-child',
        ),
      ).map(word),
    };
  });
  expect.soft(geometry.selector.height, "Operator selector height").toBe(26);
  expect
    .soft(geometry.actions.height, "retained Workspace actions height")
    .toBe(26);
  expect
    .soft(geometry.caret.src)
    .toBe(`/icons/figma/${operations ? "a4e11" : "bab86"}.svg`);
  expect.soft(geometry.caret.loaded).toBe(true);
  expect.soft(geometry.caret.widthAttribute).toBeNull();
  expect.soft(geometry.caret.heightAttribute).toBeNull();
  expect.soft(geometry.caret.slot.width).toBe(10);
  expect.soft(geometry.caret.slot.height).toBe(operations ? 6 : 5);
  // Chromium quantizes the 6.4px root height to 6.390625px, then resolves
  // its intrinsic aspect ratio to a quantized 11.375px width. No SVG size override.
  expect.soft(geometry.caret.width).toBe(operations ? 10 : 11.375);
  expect.soft(geometry.caret.height).toBe(operations ? 6 : 6.390625);
  expect.soft(geometry.caret.insetX).toBe(operations ? 0 : -0.6875);
  expect.soft(geometry.caret.insetY).toBe(operations ? 0 : -0.6875);
  if (geometry.input && geometry.button) {
    const trace = state === "216:448" || state === "216:573";
    expect.soft(geometry.input.height).toBe(trace ? 34 : 36);
    expect.soft(geometry.button.height).toBe(36);
    expect.soft(geometry.button.width).toBe(trace ? 104 : 124);
  }
  if (geometry.band) {
    if (width === 1440) expect.soft(geometry.band.height).toBe(108);
    for (const missing of geometry.band.missing) {
      expect.soft(missing.text).toBe("Unavailable");
      expect
        .soft(missing.lines, "Unavailable must remain a whole word")
        .toBe(1);
      expect.soft(missing.fits).toBe(true);
      expect.soft(missing.textFitsParent).toBe(true);
    }
  }
  if (geometry.columns && width === 1440) {
    expect.soft(geometry.columns.gap).toBe("40px");
    expect
      .soft(geometry.columns.children.map((column) => column.width))
      .toEqual([780, 380]);
    expect.soft(geometry.answer?.width).toBe(630);
  }
  if (geometry.badge) {
    expect
      .soft(geometry.badge)
      .toMatchObject({ width: 92, height: 28, radius: "8px", fits: true });
  }
  for (const selected of geometry.selected) {
    expect.soft(selected.text).toBe("SELECTED");
    expect.soft(selected.lines, "SELECTED must remain a whole word").toBe(1);
    expect.soft(selected.fits).toBe(true);
    expect.soft(selected.textFitsParent).toBe(true);
  }
  return { ...geometry, assetRoot: root };
}

// Full MCP structure coordinates, including the root 1px border and 64px navigation.
// Keep declared local coordinates as well: the generated normal line heights do not give
// exact text ink bounds. Comparing CSS boxes is descriptive evidence, never a parity gate.
function sourceMeasurements(state: string): SourceMeasurement[] {
  const x = state === "216:345" ? 121 : 120;
  const y = 109;
  const rows: SourceMeasurement[] = [
    {
      name: "top navigation",
      node:
        state === "216:345"
          ? "216:346"
          : state === "216:573"
            ? "216:574"
            : "216:756",
      selector: "header",
      expected: { x: 1, y: 1, width: 1440, height: 64 },
    },
    {
      name: "workspace selector",
      node:
        state === "216:345"
          ? "216:366"
          : state === "216:573"
            ? "216:594"
            : "216:776",
      selector: "main > div:first-child > div > div",
      expected: { x, y: y + 18, width: 220, height: 26 },
    },
    {
      name: "page title",
      node:
        state === "216:345"
          ? "216:371"
          : state === "216:573"
            ? "216:597"
            : "216:779",
      selector: "main > h1",
      expected: {
        x,
        y: y + 58,
        fontSize: "32px",
        fontWeight: "600",
        fontFamily: "Roboto Slab",
      },
    },
    {
      name: "page description",
      node:
        state === "216:345"
          ? "216:372"
          : state === "216:573"
            ? "216:598"
            : "216:780",
      selector: "main > p",
      expected: {
        x,
        y: y + 105,
        fontSize: "16px",
        fontFamily: "Inter",
        color: "rgb(101, 122, 116)",
      },
    },
    {
      name: "operator navigation",
      node:
        state === "216:345"
          ? "216:373"
          : state === "216:573"
            ? "216:599"
            : "216:781",
      selector: 'nav[aria-label="Operator navigation"]',
      expected: { x, y: y + 151, width: 1200, height: 42, gap: "28px" },
    },
  ];
  const add = (
    name: string,
    node: string,
    selector: string,
    expected: SourceMeasurement["expected"],
  ) => rows.push({ name, node, selector, expected });
  add(
    "workspace label",
    state === "216:345"
      ? "216:365"
      : state === "216:573"
        ? "216:593"
        : "216:775",
    ".workspace-selector-label",
    { x, y, fontSize: "11px", fontWeight: "600", fontFamily: "Inter" },
  );
  if (state === "216:345") {
    add(
      "configuration context",
      "216:382",
      'section[aria-labelledby="operations-heading"] > p:first-child',
      { x, y: y + 213, height: 34, fontSize: "13px", gap: "8px" },
    );
    add("observations heading", "216:385", "#operations-heading", {
      x,
      y: y + 269,
      fontSize: "20px",
      fontFamily: "Roboto Slab",
      fontWeight: "600",
    });
    add("observations description", "216:386", "#operations-heading + p", {
      x,
      y: y + 299,
      fontSize: "14px",
      color: "rgb(101, 122, 116)",
    });
    add("runtime signals", "216:387", 'dl[aria-label="Runtime signals"]', {
      x,
      y: y + 338,
      width: 1200,
      height: 108,
    });
    add("signal label", "216:389", 'dl[aria-label="Runtime signals"] dt', {
      x: x + 20,
      y: y + 360,
      fontSize: "13px",
      fontWeight: "500",
    });
    add("signal value", "216:390", 'dl[aria-label="Runtime signals"] dd', {
      x: x + 20,
      y: y + 391,
      fontSize: "26px",
      fontWeight: "600",
      fontFamily: "Roboto Slab",
    });
    add(
      "accounting heading",
      "216:400",
      'section[aria-labelledby="operations-heading"] > h3',
      { x, y: y + 476, fontSize: "18px", fontFamily: "Roboto Slab" },
    );
    add(
      "accounting list",
      "216:401",
      'section[aria-labelledby="operations-heading"] > h3 + dl',
      { x, y: y + 510, width: 1200, height: 148, columnGap: "20px" },
    );
    add(
      "accounting row",
      "216:402",
      'section[aria-labelledby="operations-heading"] > h3 + dl > div',
      { x, y: y + 510, width: 580, height: 49 },
    );
    add(
      "latency heading",
      "216:426",
      'section[aria-labelledby="operations-heading"] > h3:last-of-type',
      { x, y: y + 690, fontSize: "18px", fontFamily: "Roboto Slab" },
    );
    add(
      "histogram summary",
      "216:427",
      'section[aria-labelledby="operations-heading"] > div > div:first-child p',
      { x, y: y + 720, fontSize: "13px" },
    );
    add(
      "latency buckets",
      "216:428",
      'dl[aria-label="Cumulative latency buckets"]',
      {
        x,
        y: y + 748,
        width: 760,
        height: 92,
        columnGap: "20px",
        rowGap: "6px",
      },
    );
    add(
      "alerts notice",
      "216:445",
      'section[aria-labelledby="operations-heading"] [role="status"]',
      {
        x: x + 820,
        y: y + 748,
        width: 380,
        height: 70,
        borderRadius: "8px",
        backgroundColor: "rgb(244, 234, 230)",
      },
    );
  } else {
    const trace = state === "216:573";
    add(
      "lookup field",
      trace ? "216:610" : "216:791",
      trace ? "#operator-trace-id" : "#operator-report-id",
      {
        x,
        y: y + 229,
        width: 360,
        height: trace ? 34 : 36,
        fontSize: trace ? "13px" : "14px",
        borderRadius: "8px",
      },
    );
    add("lookup button", trace ? "216:612" : "216:793", "main form button", {
      x: x + 372,
      y: y + 229,
      width: trace ? 104 : 124,
      height: 36,
      fontSize: "14px",
      fontWeight: "600",
    });
    if (trace) {
      add("summary heading", "216:614", "#trace-summary-heading", {
        x,
        y: y + 282,
        height: 24,
        fontSize: "20px",
        fontFamily: "Roboto Slab",
      });
      add(
        "summary signals",
        "216:615",
        'dl[aria-label="Trace summary signals"]',
        { x, y: y + 316, width: 1200, height: 84 },
      );
      add(
        "summary label",
        "216:617",
        'dl[aria-label="Trace summary signals"] dt',
        { x: x + 18, y: y + 331, fontSize: "13px" },
      );
      add(
        "summary value",
        "216:618",
        'dl[aria-label="Trace summary signals"] dd',
        { x: x + 18, y: y + 355, fontSize: "22px", fontWeight: "600" },
      );
      add("detail columns", "216:634", "article > div", {
        x,
        y: y + 424,
        width: 1200,
        height: 420,
        gap: "40px",
      });
      add("result and candidates column", "216:635", "article > div > div", {
        x,
        y: y + 424,
        width: 780,
        height: 420,
      });
      add("observed result heading", "216:636", "#observed-result-heading", {
        x,
        y: y + 424,
        fontSize: "20px",
        fontFamily: "Roboto Slab",
      });
      add(
        "observed answer",
        "216:639",
        'section[aria-labelledby="observed-result-heading"] > p',
        {
          x,
          y: y + 458,
          width: 630,
          height: 40,
          fontSize: "14px",
          lineHeight: "20px",
        },
      );
      add("candidate heading", "216:640", "#candidate-heading", {
        x,
        y: y + 550,
        height: 24,
        fontSize: "20px",
        fontFamily: "Roboto Slab",
      });
      add("candidate description", "216:641", "#candidate-heading + p", {
        x,
        y: y + 580,
        width: 730,
        height: 18,
        fontSize: "13px",
        lineHeight: "18px",
      });
      add(
        "first candidate",
        "216:642",
        'section[aria-labelledby="candidate-heading"] li:first-child',
        { x, y: y + 614, width: 760, height: 102 },
      );
      add(
        "second candidate",
        "216:649",
        'section[aria-labelledby="candidate-heading"] li:nth-child(2)',
        { x, y: y + 724, width: 760, height: 102 },
      );
      add("technical context column", "216:662", "article aside", {
        x: x + 820,
        y: y + 424,
        width: 380,
        height: 420,
      });
      add("trace context heading", "216:663", "#trace-context-heading", {
        x: x + 820,
        y: y + 424,
        fontSize: "20px",
        fontFamily: "Roboto Slab",
      });
      add("context row", "216:664", "#trace-context-heading + dl > div", {
        x: x + 820,
        y: y + 458,
        width: 380,
        height: 38,
      });
      add("citation heading", "216:680", "#citation-mapping-heading", {
        x: x + 820,
        y: y + 629,
        height: 22,
        fontSize: "18px",
        fontFamily: "Roboto Slab",
      });
      add("phase heading", "216:685", "#phase-timing-heading", {
        x: x + 820,
        y: y + 742,
        height: 22,
        fontSize: "18px",
        fontFamily: "Roboto Slab",
      });
      add("phase row", "216:686", "#phase-timing-heading + dl > div", {
        x: x + 820,
        y: y + 766,
        width: 380,
        height: 26,
      });
      add(
        "validation timing row",
        "216:694",
        "#phase-timing-heading + dl > div:nth-child(3)",
        { x: x + 820, y: y + 818, width: 380, height: 26 },
      );
      add(
        "answer badge",
        "216:637",
        'section[aria-labelledby="observed-result-heading"] [data-kind]',
        { x: x + 650, y: y + 424, width: 110, height: 28, borderRadius: "7px" },
      );
      add(
        "selected candidate badge",
        "216:644",
        'section[aria-labelledby="candidate-heading"] li:first-child [data-kind]',
        { x: x + 610, y: y + 618, width: 150, height: 28, borderRadius: "7px" },
      );
    } else {
      add(
        "evaluation columns",
        "216:774/795/797",
        'section[aria-labelledby="evaluation-heading"]',
        { x, y: y + 300, width: 1200, columnGap: "60px" },
      );
      add("unavailable heading", "216:795", "#evaluation-heading", {
        x,
        y: y + 300,
        fontSize: "26px",
        fontFamily: "Inter",
        fontWeight: "600",
      });
      add(
        "unavailable explanation",
        "216:796",
        'section[aria-labelledby="evaluation-heading"] > div > p',
        {
          x,
          y: y + 344,
          width: 680,
          height: 70,
          fontSize: "16px",
          lineHeight: "20px",
          color: "rgb(94, 115, 107)",
        },
      );
      add("report context heading", "216:797", "#report-context-heading", {
        x: x + 820,
        y: y + 300,
        height: 24,
        fontSize: "22px",
        fontFamily: "Inter",
      });
      add(
        "report context row",
        "216:798/800",
        "#report-context-heading + dl > div",
        {
          x: x + 820,
          y: y + 344,
          width: 380,
          height: 40,
          fontSize: "14px",
          columnGap: "10px",
        },
      );
      add(
        "unavailable badge",
        "216:810",
        'section[aria-labelledby="evaluation-heading"] > div > div > span',
        {
          x: x + 383,
          y: y + 303,
          width: 92,
          height: 28,
          borderRadius: "8px",
          fontSize: "12px",
        },
      );
      add(
        "observation code value",
        "216:808",
        "#report-context-heading + dl > div:last-child dd",
        {
          x: x + 1000,
          y: y + 464,
          width: 300,
          height: 24,
          fontSize: "12px",
          fontFamily: "Inter",
        },
      );
    }
  }
  return rows;
}

function classifyPDFObservation(observation: IngestionJobStatusResponse) {
  const statuses: readonly IngestionJobStatusResponse["status"][] = [
    "queued",
    "processing",
    "retry_scheduled",
    "succeeded",
    "superseded",
    "failed",
  ];
  expect(statuses).toContain(observation.status);
  return ["queued", "processing", "retry_scheduled"].includes(
    observation.status,
  )
    ? "pending"
    : "terminal";
}

test("PDF observation classifies retry and superseded using the public projection", () => {
  const projection: IngestionJobStatusResponse = {
    ingestion_job_id: "fixture-job",
    target_document_version_id: "fixture-version",
    current_document_version_id: null,
    served_document_version_id: null,
    serving_state: "unavailable",
    status: "retry_scheduled",
    attempt_count: 1,
    max_attempts: 3,
    poll_after_seconds: 2,
    created_at: "2026-10-05T12:00:00Z",
    updated_at: "2026-10-05T12:00:00Z",
  };
  for (const status of ["queued", "processing", "retry_scheduled"] as const)
    expect(classifyPDFObservation({ ...projection, status })).toBe("pending");
  for (const status of ["succeeded", "superseded", "failed"] as const)
    expect(classifyPDFObservation({ ...projection, status })).toBe("terminal");
  expect(() =>
    classifyPDFObservation({
      ...projection,
      status: "retry_wait" as IngestionJobStatusResponse["status"],
    }),
  ).toThrow();
});

test.describe("source fixtures", () => {
  test.skip(
    process.env.FIGMA_TEST_MODE !== "fixture",
    "Dedicated fixture project required.",
  );

  for (const prototype of [
    { state: "216:345", name: "Operations", route: "/operator/operations" },
    {
      state: "216:573",
      name: "Trace detail",
      route: "/operator/traces/fixture-trace",
    },
    {
      state: "216:755",
      name: "Evaluation unavailable",
      route: "/operator/evaluations/fixture-report",
    },
  ] as const) {
    test(`Operator prototype comparison ${prototype.state} ${prototype.name} records desktop deviations and mobile fit`, async ({
      page,
    }, testInfo) => {
      expect(visualStates).toHaveLength(51);
      expect(fixtureStates).toHaveLength(56);
      expect(statePath(prototype.state)).toBe(prototype.route);
      // These views receive presentation props. No backend endpoint is opened by the fixture.
      expect(() =>
        fixtureResponse(prototype.state, "/api/v1/unexpected", "GET"),
      ).toThrow();
      expect(() =>
        fixtureResponse(prototype.state, "/api/v1/workspaces", "POST"),
      ).toThrow();
      expect(() =>
        fixtureResponse(prototype.state, "/api/v1/workspaces", "GET"),
      ).toThrow();
      const writes: string[] = [];
      const apiRequests: string[] = [];
      page.on("request", (request) => {
        if (new URL(request.url()).pathname.startsWith("/api/"))
          apiRequests.push(
            `${request.method()} ${new URL(request.url()).pathname}`,
          );
        if (
          new URL(request.url()).pathname.startsWith("/api/") &&
          request.method() !== "GET"
        )
          writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
      });
      const id = prototype.state.replace(":", "-");
      fs.mkdirSync(prototypeEvidence, { recursive: true });
      const sourceIndex = JSON.parse(
        fs.readFileSync(`${prototypeEvidence}/source-index.json`, "utf8"),
      ) as Array<{
        nodeId: string;
        structureSHA256: string;
        screenshotSHA256: string;
      }>;
      const source = sourceIndex.find(
        (entry) => entry.nodeId === prototype.state,
      )!;
      expect(sha256(`${prototypeEvidence}/${id}.md`).toUpperCase()).toBe(
        source.structureSHA256,
      );
      expect(sha256(`${prototypeEvidence}/${id}.png`).toUpperCase()).toBe(
        source.screenshotSHA256,
      );
      for (const width of [1440, 390]) {
        await page.setViewportSize({
          width,
          height: width === 1440 ? 960 : 844,
        });
        const unexpected = await prepareFixture(page, prototype.state);
        await expect(page.locator("[data-fixture-state]")).toHaveAttribute(
          "data-fixture-state",
          prototype.state,
        );
        const sourceGeometry = await operatorSourceGeometry(
          page,
          prototype.state,
          width,
        );
        writeLookupGeometry(
          testInfo.outputPath(`operator-source-${width}`),
          sourceGeometry,
        );
        if (prototype.state === "216:345") {
          await expect(
            page.getByRole("heading", { name: "Operational observations" }),
          ).toBeVisible();
          await expect(
            page.getByRole("heading", { name: "Execution accounting" }),
          ).toBeVisible();
          await expect(
            page.getByRole("heading", { name: "Latency observations" }),
          ).toBeVisible();
          await expect(
            page.getByText("runtime-config-v12", { exact: true }),
          ).toBeVisible();
          const signals = page.getByRole("group", { name: "Runtime signals" });
          await expect(signals.locator("dt")).toHaveText([
            "Queue depth",
            "Retry rate",
            "Cleanup failures",
            "Orphan discoveries",
          ]);
          await expect(signals.locator("dd")).toHaveText([
            "0",
            "2.4%",
            "0",
            "Unavailable",
          ]);
          await expect(
            signals.locator('dd[data-state="available"]'),
          ).toHaveCount(3);
          await expect(
            signals.locator('dd[data-state="unavailable"]'),
          ).toHaveCount(1);
          const accounting = page.locator(
            'section[aria-labelledby="operations-heading"] > h3 + dl',
          );
          await expect(accounting.locator("dt")).toHaveText([
            "Oldest job age",
            "Claim latency samples",
            "Claim latency sum",
            "Lease expiry recoveries",
            "Cleanup attempts",
            "Orphan reconciliations",
          ]);
          await expect(accounting.locator("dd")).toHaveText([
            "18 s",
            "124",
            "18.4 s",
            "1",
            "32",
            "0",
          ]);
          await expect(
            page.getByText(
              "claim_latency_seconds · 124 samples · 18.4 s total",
              { exact: true },
            ),
          ).toBeVisible();
          const histogram = page.locator(
            'dl[aria-label="Cumulative latency buckets"]',
          );
          await expect(histogram.locator("dt")).toHaveText([
            "≤ 0.1 s",
            "≤ 0.25 s",
            "≤ 0.5 s",
            "≤ 1 s",
          ]);
          await expect(histogram.locator("dd")).toHaveText([
            "38",
            "91",
            "118",
            "124",
          ]);
          await expect(page.getByRole("status")).toHaveText(
            "ALERTSUnavailable in the current Operator contract.",
          );
        } else if (prototype.state === "216:573") {
          for (const heading of [
            "Trace summary",
            "Observed result",
            "Candidate provenance",
            "Trace context",
            "Citation mapping",
            "Phase timing",
          ])
            await expect(
              page.getByRole("heading", { name: heading, exact: true }),
            ).toBeVisible();
          await expect(
            page.getByRole("textbox", { name: "Trace ID", exact: true }),
          ).toHaveValue("fixture-trace");
          const summary = page.getByRole("group", {
            name: "Trace summary signals",
          });
          await expect(summary.locator("dt")).toHaveText([
            "Decision",
            "Validation outcome",
            "Retrieval latency",
            "Candidates",
          ]);
          await expect(summary.locator("dd")).toHaveText([
            "ANSWER",
            "VALID",
            "184 ms",
            "2",
          ]);
          await expect(
            page.getByText(prototypeTrace.answer!, { exact: true }),
          ).toBeVisible();
          const candidates = page.locator(
            'section[aria-labelledby="candidate-heading"] li',
          );
          await expect(candidates).toHaveCount(2);
          for (const [
            index,
            candidate,
          ] of prototypeTrace.candidates.entries()) {
            await expect(candidates.nth(index).locator("strong")).toHaveText(
              candidate.source_key,
            );
            await expect(candidates.nth(index)).toContainText("SELECTED");
            await expect(candidates.nth(index)).toContainText(
              `Chunk ${candidate.chunk_ordinal} · Lines ${candidate.start_line}-${candidate.end_line} · Rank ${candidate.final_rank} · Fusion ${candidate.fusion_score}`,
            );
            await expect(
              page.getByText(candidate.content, { exact: true }),
            ).toBeVisible();
          }
          const context = page.getByRole("region", {
            name: "Trace context",
            exact: true,
          });
          await expect(context.locator("dd")).toHaveText([
            "fixture-trace",
            "retrieval-m1-v1",
            "embedding-local-m1-v2",
            "v2",
          ]);
          const mapping = page.getByRole("region", {
            name: "Citation mapping",
            exact: true,
          });
          await expect(mapping.locator("dt")).toHaveText(["E1", "E2"]);
          await expect(mapping.locator("dd")).toHaveText([
            "fixture-chunk-12Teacher Manh – Guidelines 2024.pdf",
            "fixture-chunk-4Reporting policy.pdf",
          ]);
          const timing = page.getByRole("region", {
            name: "Phase timing",
            exact: true,
          });
          await expect(timing.locator("dt")).toHaveText([
            "retrieval",
            "generation",
            "validation",
          ]);
          await expect(timing.locator("dd")).toHaveText([
            "184 ms",
            "612 ms",
            "24 ms",
          ]);
        } else {
          await expect(
            page.getByRole("textbox", { name: "Report ID", exact: true }),
          ).toHaveValue("fixture-report");
          await expect(
            page.getByRole("heading", {
              name: "Evaluation report unavailable",
              exact: true,
            }),
          ).toBeVisible();
          await expect(
            page.getByText(
              "Persisted evaluation reports are not available in the current Operator contract. Knora does not invent quality scores, pass/fail results, or other evaluation metrics when the backend has no report to expose.",
              { exact: true },
            ),
          ).toBeVisible();
          const context = page.getByRole("region", {
            name: "Report context",
            exact: true,
          });
          await expect(context.locator("dt")).toHaveText([
            "Report ID",
            "Observed Workspace",
            "Availability",
            "Observation code",
          ]);
          await expect(context.locator("dd")).toHaveText([
            "fixture-report",
            "fixture-workspace",
            "Unavailable",
            "EVALUATION_REPORT_UNAVAILABLE",
          ]);
          await expect(
            page.locator("[data-state], table, output, meter, progress"),
          ).toHaveCount(0);
        }
        const measurements = [];
        for (const measurement of sourceMeasurements(prototype.state)) {
          const actual = await page
            .locator(measurement.selector)
            .first()
            .evaluate((element) => {
              const box = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {
                x: box.x,
                y: box.y,
                width: box.width,
                height: box.height,
                fontFamily: style.fontFamily,
                fontSize: style.fontSize,
                fontWeight: style.fontWeight,
                lineHeight: style.lineHeight,
                gap: style.gap,
                columnGap: style.columnGap,
                rowGap: style.rowGap,
                color: style.color,
                backgroundColor: style.backgroundColor,
                borderRadius: style.borderRadius,
              };
            });
          const differences = Object.entries(measurement.expected).map(
            ([property, expected]) => {
              const value = actual[property as keyof typeof actual];
              const exact =
                property === "fontFamily"
                  ? String(value).includes(String(expected))
                  : value === expected;
              return {
                property,
                source: expected,
                current: value,
                delta:
                  typeof expected === "number" && typeof value === "number"
                    ? value - expected
                    : null,
                classification:
                  width !== 1440
                    ? "responsive adaptation; no mobile source"
                    : exact
                      ? "exact measured match"
                      : [
                            "x",
                            "y",
                            "width",
                            "height",
                            "gap",
                            "columnGap",
                            "rowGap",
                          ].includes(property)
                        ? "geometry deviation; parity unresolved"
                        : "typography/color/shape deviation; parity unresolved",
              };
            },
          );
          measurements.push({ ...measurement, actual, differences });
        }
        const assets = await page
          .locator("main img, header img")
          .evaluateAll((elements) =>
            elements.map((element) => {
              const image = element as HTMLImageElement;
              const box = image.getBoundingClientRect();
              return {
                src: image.getAttribute("src")!,
                loaded: image.complete && image.naturalWidth > 0,
                x: box.x,
                y: box.y,
                width: box.width,
                height: box.height,
              };
            }),
          );
        expect(assets).toHaveLength(2);
        expect(assets.every((asset) => asset.loaded)).toBe(true);
        expect(assets[0]).toMatchObject({
          src: "/brand/knora-leaf.svg",
          width: 18,
          height: 18,
        });
        const assetEvidence = assets.map((asset) => ({
          ...asset,
          sha256: sha256(`public${asset.src}`),
          sourceAsset:
            asset.src === "/brand/knora-leaf.svg"
              ? "ad252.svg; Brand/Knora Mark 20:2/20:3; 18x18"
              : prototype.state === "216:345"
                ? "a4e11.svg; 216:368/369; 10x6"
                : prototype.state === "216:573"
                  ? "bab86.svg; 216:596; 10x5 slot, 11.4x6.4 ink wrapper"
                  : "bab86.svg; 216:778; 10x5 slot, 11.4x6.4 ink wrapper",
          classification:
            asset.src === "/brand/knora-leaf.svg"
              ? "original local brand asset; exact dimensions"
              : "exact local source caret and slot; SVG intrinsic dimensions retained",
        }));
        const fit = await page.locator("main").evaluate((main) => {
          const box = main.getBoundingClientRect();
          const overflowing = Array.from(
            main.querySelectorAll(
              "p, h1, h2, h3, dt, dd, summary, input, button",
            ),
          )
            .filter((element) => {
              const rect = element.getBoundingClientRect();
              return (
                rect.width > 0 &&
                rect.height > 0 &&
                (rect.left < box.left ||
                  rect.right > box.right ||
                  element.scrollWidth > element.clientWidth)
              );
            })
            .map((element) => element.textContent || element.tagName);
          return {
            pageWidth: document.documentElement.scrollWidth,
            viewportWidth: innerWidth,
            overflowing,
          };
        });
        expect(fit.pageWidth).toBeLessThanOrEqual(width);
        expect(fit.overflowing).toEqual([]);
        const extraControls = await page
          .locator("main summary, main .kn-menu__trigger")
          .evaluateAll((elements) =>
            elements.map((element) => ({
              text: element.textContent,
              label: element.getAttribute("aria-label"),
              box: {
                x: element.getBoundingClientRect().x,
                y: element.getBoundingClientRect().y,
                width: element.getBoundingClientRect().width,
                height: element.getBoundingClientRect().height,
              },
            })),
          );
        const evidence = `${prototypeEvidence}/implemented-${id}-${width}`;
        writeLookupGeometry(evidence, {
          state: prototype.state,
          viewport: page.viewportSize(),
          authority:
            "Synthetic typed fixture presentation only; no backend existence/authorization/runtime claim",
          source: {
            ...source,
            frame: [1440, 960],
            pngPixels: [1024, 683],
            annotationCrop: 0,
            coordinates:
              "Full MCP CSS boxes reconstructed with 1px root border; declared content x=120 (Operations) or119, y=44 within 896px body after64px nav. Normal text ink bounds are not specified.",
          },
          measurements,
          assets: assetEvidence,
          correctedGeometry: sourceGeometry,
          extraControls,
          apiRequests,
          fit,
          parityAccepted: false,
        });
        await page.screenshot({
          path: `${evidence}.png`,
          fullPage: width !== 1440,
          animations: "disabled",
        });
        if (prototype.state === "216:573") {
          // Expanded detail checks follow the source-comparison capture so extra disclosure
          // content does not masquerade as the prototype's closed composition.
          for (const [
            index,
            candidate,
          ] of prototypeTrace.candidates.entries()) {
            const details = page
              .locator('section[aria-labelledby="candidate-heading"] li')
              .nth(index)
              .locator("details");
            await details.locator("summary").click();
            await expect(details.locator("dd")).toHaveText([
              candidate.chunk_id,
              candidate.document_version_id,
              candidate.chunk_set_id,
              String(candidate.fusion_score),
              "Unavailable",
              candidate.vector_contribution
                ? JSON.stringify(candidate.vector_contribution)
                : "Unavailable",
              candidate.fts_contribution
                ? JSON.stringify(candidate.fts_contribution)
                : "Unavailable",
            ]);
          }
          for (const heading of [
            "Additional provenance",
            "Provider accounting",
            "M4 lifecycle evidence",
          ])
            await page.getByText(heading, { exact: true }).click();
          const additional = page.locator("details").filter({
            has: page
              .locator("summary")
              .filter({ hasText: /^Additional provenance$/ }),
          });
          await expect(additional.locator("dd")).toHaveText([
            "fixture-workspace",
            "fixture-chunk-set-12, fixture-chunk-set-4",
            "fixture-embedding-set-12, fixture-embedding-set-4",
            "0.001 ms",
          ]);
          const accounting = page.locator("details").filter({
            has: page
              .locator("summary")
              .filter({ hasText: /^Provider accounting$/ }),
          });
          await expect(accounting.locator("dd")).toHaveText(
            Array(6).fill("Unavailable"),
          );
          await expect(
            page.getByText("Branch observation schema: 1", { exact: true }),
          ).toBeVisible();
          await expect(
            page.getByText("M4 observation unavailable", { exact: true }),
          ).toBeVisible();
        }
        expect(unexpected).toEqual([]);
        expect(writes).toEqual([]);
      }
      fs.writeFileSync(
        `${prototypeEvidence}/remaining-operator-comparisons.html`,
        `<!doctype html><html lang="en"><meta charset="utf-8"><title>Remaining Operator whole-frame comparisons</title><style>body{font:14px system-ui;margin:24px;background:#eee}section{margin:32px 0}.pair{display:flex;gap:20px;align-items:flex-start}.pair img{width:720px;height:auto;border:1px solid #bbb}figure{margin:0}figcaption{margin:8px 0}a{color:#175b3a}</style><h1>Whole-frame comparisons; parity unresolved</h1><p>Figma1440×960 frame returned as1024×683 PNG; common display width720px. No annotation strip, no crop. Synthetic projections prove presentation only. Desktop CSS box measurements and every measured deviation are in linked JSON. Mobile has no supplied source geometry.</p>${["216-345", "216-573", "216-755"].map((node) => `<section><h2>${node}</h2><div class="pair"><figure><figcaption>Full MCP source</figcaption><img src="${node}.png" alt="Figma source ${node}"></figure><figure><figcaption>Actual production composition, synthetic fixture</figcaption><img src="implemented-${node}-1440.png" alt="Current desktop ${node}"></figure></div><p><a href="implemented-${node}-1440-geometry.json">Desktop geometry and deviations</a> · <a href="implemented-${node}-390.png">390px readable fit capture</a> · <a href="implemented-${node}-390-geometry.json">Mobile measurements</a></p></section>`).join("")}</html>`,
      );
    });
  }

  for (const lookup of [
    {
      state: "216:448",
      kind: "trace",
      heading: "What this trace shows",
      target: "traces",
      observationState: "198:200",
      observationPath: "/operator/traces/fixture-trace",
      observation: "Trace context",
      observationIdentity: "fixture-trace",
    },
    {
      state: "216:698",
      kind: "report",
      heading: "What this report provides",
      target: "evaluations",
      observationState: "206:206",
      observationPath: "/operator/evaluations/fixture-report",
      observation: "Report context",
      observationIdentity: "fixture-report",
    },
  ] as const) {
    test(`Operator ${lookup.kind} lookup guidance fits desktop and mobile and preserves scoped navigation`, async ({
      page,
    }, testInfo) => {
      const freshEvidence = testInfo.outputPath(
        "fresh-nested-evidence",
        "operator-prototypes-2026-10-07",
        "lookup",
      );
      expect(fs.existsSync(path.dirname(freshEvidence))).toBe(false);
      writeLookupGeometry(freshEvidence, { width: 1200 });
      expect(
        JSON.parse(fs.readFileSync(`${freshEvidence}-geometry.json`, "utf8")),
      ).toEqual({ width: 1200 });
      const writes: string[] = [];
      page.on("request", (request) => {
        if (
          new URL(request.url()).pathname.startsWith("/api/") &&
          request.method() !== "GET"
        )
          writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
      });
      for (const width of [1440, 390]) {
        await page.setViewportSize({
          width,
          height: width === 1440 ? 960 : 844,
        });
        const unexpected = await prepareFixture(page, lookup.state);
        const sourceGeometry = await operatorSourceGeometry(
          page,
          lookup.state,
          width,
        );
        writeLookupGeometry(
          testInfo.outputPath(`operator-source-${width}`),
          sourceGeometry,
        );
        const guidance = page.getByRole("region", { name: lookup.heading });
        await expect(guidance).toBeVisible();
        const submit = page.getByRole("button", {
          name: `Open ${lookup.kind}`,
        });
        await expect(submit).toBeDisabled();
        const assets = await page
          .locator(
            'img[src="/brand/knora-leaf.svg"], .workspace-selector-trigger img',
          )
          .evaluateAll((images) =>
            images.map((element) => {
              const image = element as HTMLImageElement;
              const box = image.getBoundingClientRect();
              return {
                src: image.getAttribute("src"),
                loaded: image.complete && image.naturalWidth > 0,
                width: box.width,
                height: box.height,
              };
            }),
          );
        expect(assets).toHaveLength(2);
        expect(assets.every((asset) => asset.loaded)).toBe(true);
        expect(assets[0]).toMatchObject({
          src: "/brand/knora-leaf.svg",
          width: 18,
          height: 18,
        });
        expect(assets[1]).toMatchObject({
          src: "/icons/figma/bab86.svg",
          width: 11.375,
          height: 6.390625,
        });
        const geometry = await guidance.evaluate((element) => {
          const box = element.getBoundingClientRect();
          const heading = element.querySelector("h2")!;
          const columns = Array.from(element.querySelectorAll("li"));
          return {
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            headingFont: getComputedStyle(heading).fontFamily,
            headingSize: getComputedStyle(heading).fontSize,
            headingWeight: getComputedStyle(heading).fontWeight,
            columns: columns.map((column) => {
              const card = column.getBoundingClientRect();
              const label = column.querySelector("h3")!;
              const body = column.querySelector("p")!;
              const copy = body.getBoundingClientRect();
              const style = getComputedStyle(body);
              return {
                x: card.x,
                y: card.y,
                width: card.width,
                height: card.height,
                labelSize: getComputedStyle(label).fontSize,
                labelFont: getComputedStyle(label).fontFamily,
                bodyFont: style.fontFamily,
                bodySize: style.fontSize,
                bodyLineHeight: style.lineHeight,
                copyFits:
                  copy.right <= card.right &&
                  copy.bottom <= card.bottom &&
                  body.scrollWidth <= body.clientWidth,
              };
            }),
          };
        });
        expect(geometry.headingFont).toContain("Roboto Slab");
        expect(geometry.headingSize).toBe("18px");
        expect(geometry.headingWeight).toBe("600");
        expect(geometry.columns).toHaveLength(3);
        for (const column of geometry.columns) {
          expect(column.labelSize).toBe("12px");
          expect(column.labelFont).toContain("Inter");
          expect(column.bodyFont).toContain("Inter");
          expect(column.bodySize).toBe("14px");
          expect(column.bodyLineHeight).toBe("20px");
          expect(column.copyFits).toBe(true);
        }
        if (width === 1440) {
          expect(geometry.x).toBe(120);
          expect(geometry.width).toBe(1200);
          expect(geometry.columns.map((column) => column.x)).toEqual([
            120, 540, 960,
          ]);
          expect(geometry.columns.map((column) => column.width)).toEqual([
            360, 360, 360,
          ]);
          expect(geometry.columns[0].y - geometry.y).toBe(92);
        } else {
          expect(geometry.columns.map((column) => column.x)).toEqual([
            16, 16, 16,
          ]);
          expect(geometry.columns[1].y).toBeGreaterThanOrEqual(
            geometry.columns[0].y + geometry.columns[0].height,
          );
          expect(geometry.columns[2].y).toBeGreaterThanOrEqual(
            geometry.columns[1].y + geometry.columns[1].height,
          );
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth,
            ),
          ).toBe(true);
        }
        const evidence = `../.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/implemented-${lookup.state.replace(":", "-")}-${width}`;
        writeLookupGeometry(evidence, {
          ...geometry,
          assets,
          correctedGeometry: sourceGeometry,
        });
        await page.screenshot({
          path: `${evidence}.png`,
          fullPage: width !== 1440,
          animations: "disabled",
        });

        await page
          .getByText("Exact Workspace ID (optional)", { exact: true })
          .click();
        await page
          .getByRole("textbox", { name: "Workspace ID", exact: true })
          .fill("fixture-workspace");
        const identifier = `fixture-${lookup.kind} /?&`;
        await page
          .getByRole("textbox", {
            name: lookup.kind === "trace" ? "Trace ID" : "Report ID",
          })
          .fill(identifier);
        const targetPath = `/operator/${lookup.target}/fixture-${lookup.kind}%20%2F%3F%26`;
        const requested = page.waitForRequest(
          (request) => new URL(request.url()).pathname === targetPath,
        );
        await submit.click();
        const request = await requested;
        expect(request.method()).toBe("GET");
        expect(new URL(request.url()).searchParams.get("workspaceId")).toBe(
          "fixture-workspace",
        );
        await expect(page).toHaveURL(
          `http://127.0.0.1:3300${targetPath}?workspaceId=fixture-workspace`,
        );
        // Observe the existing guarded detail fixture independently of the synthetic lookup ID.
        await page.goto(
          `${lookup.observationPath}?state=${encodeURIComponent(lookup.observationState)}&workspaceId=fixture-workspace`,
        );
        await expect(
          page.getByRole("region", { name: lookup.observation }),
        ).toContainText(lookup.observationIdentity);
        expect(unexpected).toEqual([]);
        expect(writes).toEqual([]);
      }
    });
  }

  for (const width of [1440, 390]) {
    test(`W5A unselected retained answer context and notice fit at ${width}`, async ({
      page,
    }) => {
      const writes: string[] = [];
      page.on("request", (request) => {
        if (
          new URL(request.url()).pathname.startsWith("/api/") &&
          request.method() !== "GET"
        )
          writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
      });
      await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
      const unexpected = await prepareFixture(page, "183:176");
      if (width === 390)
        await page.getByRole("button", { name: "Open evidence" }).click();
      const inspector = page.getByRole("complementary", {
        name: "Evidence Inspector",
      });
      const context = inspector.locator("blockquote");
      const notice = inspector.locator(
        '[aria-label="Read-only Workspace notice"]',
      );
      await expect(
        inspector.getByRole("heading", { name: "Select a citation" }),
      ).toBeVisible();
      await expect(context).toHaveText(
        "VERIFY THE ANSWERChoose a citation in the answer to inspect the exact supporting passage and its source context.",
      );
      await expect(notice).toHaveText(
        "READ-ONLY WORKSPACEWorkspace archived. Restore it to ask new questions or make changes.",
      );
      const geometry = await context.evaluate((element) => {
        const notice = element.nextElementSibling!;
        const measure = (card: Element) => {
          const box = card.getBoundingClientRect();
          const style = getComputedStyle(card);
          return {
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            minHeight: style.minHeight,
            maxHeight: style.maxHeight,
            overflowY: style.overflowY,
            paddingX: style.paddingLeft,
            paddingY: style.paddingTop,
            radius: style.borderRadius,
            gap: style.gap,
            copyFits: Array.from(card.children).every((child) => {
              const copy = child.getBoundingClientRect();
              return (
                copy.left >= box.left &&
                copy.right <= box.right &&
                copy.top >= box.top &&
                copy.bottom <= box.bottom &&
                child.scrollWidth <= child.clientWidth &&
                child.scrollHeight <= child.clientHeight
              );
            }),
          };
        };
        const card = measure(element);
        const following = measure(notice);
        return {
          context: card,
          notice: following,
          noticeGap: following.y - (card.y + card.height),
          viewportFits: document.documentElement.scrollWidth <= innerWidth,
        };
      });
      expect(geometry.context.minHeight).toBe("96px");
      expect(geometry.context.height).toBeGreaterThanOrEqual(96);
      expect(geometry.context.maxHeight).toBe("none");
      expect(geometry.context.overflowY).toBe("visible");
      for (const card of [geometry.context, geometry.notice]) {
        expect(card.paddingX).toBe("14px");
        expect(card.paddingY).toBe("13px");
        expect(card.radius).toBe("8px");
        expect(card.gap).toBe("8px");
        expect(card.copyFits).toBe(true);
        expect(card.x).toBeGreaterThanOrEqual(0);
        expect(card.x + card.width).toBeLessThanOrEqual(width);
      }
      expect(geometry.noticeGap).toBe(14);
      expect(geometry.viewportFits).toBe(true);
      if (width === 1440) {
        expect(geometry.context.width).toBe(340);
        expect(geometry.context.height).toBe(96);
        expect(geometry.notice.width).toBe(340);
        expect(geometry.notice.height).toBe(82);
      }
      const evidence = `../.superpowers/figma/q1/evidence/archived-inspector-context-${width}`;
      writeLookupGeometry(evidence, geometry);
      await page.screenshot({
        path: `${evidence}.png`,
        animations: "disabled",
      });
      if (width === 390) await page.keyboard.press("Escape");
      const citation = page.getByRole("button", { name: /citation 1/i });
      await citation.focus();
      await citation.press("Enter");
      await expect(context).toContainText("The report consists of 7 chapters.");
      expect(
        await context.evaluate(
          (element) => getComputedStyle(element).minHeight,
        ),
      ).toBe("146px");
      await expect(inspector).toContainText("fixture-version");
      await inspector.getByText("Provenance", { exact: true }).click();
      for (const value of ["E1", "guidelines-2024", "fixture-checksum"])
        await expect(inspector.getByText(value, { exact: true })).toBeVisible();
      const documentLink = inspector.getByRole("link", {
        name: /open document/i,
      });
      await expect(documentLink).toHaveAttribute(
        "href",
        "/workspaces/fixture-workspace/documents/fixture-document",
      );
      const navigation = page.waitForRequest(
        (request) =>
          new URL(request.url()).pathname ===
          "/workspaces/fixture-workspace/documents/fixture-document",
      );
      await documentLink.click();
      expect((await navigation).method()).toBe("GET");
      await expect(page).toHaveURL(
        /\/workspaces\/fixture-workspace\/documents\/fixture-document/,
      );
      // The standalone host chooses composition by explicit state, not pathname.
      // Check the existing document detail fixture independently after real link navigation.
      await page.goto(
        "/workspaces/fixture-workspace/documents/fixture-document?state=128%3A122",
      );
      await expect(
        page.getByRole("heading", {
          name: "Teacher Manh – Guidelines 2024.pdf",
        }),
      ).toBeVisible();
      expect(unexpected).toEqual([]);
      expect(writes).toEqual([]);
    });

    test(`archived Workspace evidence notice preserves selected source and fits at ${width}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
      const unexpected = await prepareFixture(page, "183:176");
      const citation = page.getByRole("button", { name: /citation 1/i });
      await citation.focus();
      await citation.press("Enter");
      const inspector = page.getByRole("complementary", {
        name: "Evidence Inspector",
      });
      await expect(inspector).toContainText(
        "The report consists of 7 chapters.",
      );
      await expect(
        inspector.getByRole("link", { name: /open document/i }),
      ).toHaveAttribute(
        "href",
        "/workspaces/fixture-workspace/documents/fixture-document",
      );
      const notice = inspector.locator(
        '[aria-label="Read-only Workspace notice"]',
      );
      await expect(notice).toHaveText(
        "READ-ONLY WORKSPACEWorkspace archived. Restore it to ask new questions or make changes.",
      );
      const geometry = await notice.evaluate((element) => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const body = element.lastElementChild!.getBoundingClientRect();
        return {
          width: box.width,
          height: box.height,
          paddingX: style.paddingLeft,
          paddingY: style.paddingTop,
          radius: style.borderRadius,
          gap: style.gap,
          bodyFits: body.right <= box.right && body.bottom <= box.bottom,
          background: style.backgroundColor,
        };
      });
      expect(geometry.height).toBeGreaterThanOrEqual(82);
      expect(geometry.paddingX).toBe("14px");
      expect(geometry.paddingY).toBe("13px");
      expect(geometry.radius).toBe("8px");
      expect(geometry.gap).toBe("8px");
      expect(geometry.bodyFits).toBe(true);
      expect(geometry.background).toBe("rgb(243, 248, 245)");
      if (width === 1440) {
        expect(geometry.width).toBe(340);
        expect(geometry.height).toBe(82);
      } else {
        await expect(
          page.getByRole("dialog", { name: "Evidence" }),
        ).toBeVisible();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true);
      }
      await page.screenshot({
        path: `../.superpowers/figma/q1/evidence/archived-evidence-notice-${width}.png`,
        animations: "disabled",
      });
      if (width === 1440)
        await page.getByRole("button", { name: "Close evidence" }).click();
      else {
        await notice.evaluate((element) => {
          for (const child of element.children) {
            const paragraph = child as HTMLElement;
            const style = getComputedStyle(paragraph);
            paragraph.style.fontSize = `${parseFloat(style.fontSize) * 2}px`;
            paragraph.style.lineHeight = `${parseFloat(style.lineHeight) * 2}px`;
          }
        });
        expect(
          await notice.evaluate((element) => {
            const card = element.getBoundingClientRect();
            const body = element.lastElementChild!.getBoundingClientRect();
            return (
              body.bottom <= card.bottom &&
              element.scrollWidth <= element.clientWidth
            );
          }),
        ).toBe(true);
        await page.keyboard.press("Escape");
      }
      await expect(citation).toBeFocused();
      expect(unexpected).toEqual([]);
    });
  }

  test("citation selection toggles on repeated click; inspector close returns keyboard focus", async ({
    page,
  }) => {
    const unexpected = await prepareFixture(page, "128:110");
    const citation = page.getByRole("button", { name: /citation 1/i });
    await citation.focus();
    await citation.press("Enter");
    await expect(
      page.getByRole("complementary", { name: /evidence/i }),
    ).toContainText("The report consists of 7 chapters.");
    await citation.click();
    await expect(citation).toHaveAttribute("aria-pressed", "false");
    await expect(
      page.getByRole("heading", { name: "Select a citation" }),
    ).toBeVisible();
    await page.screenshot({
      path: "../.superpowers/figma/q1/evidence/parity-citation-deselected.png",
      animations: "disabled",
    });
    await citation.focus();
    await citation.press("Space");
    await expect(citation).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("complementary", { name: /evidence/i }),
    ).toContainText("The report consists of 7 chapters.");
    await page.getByRole("button", { name: "Close evidence" }).click();
    await expect(citation).toBeFocused();
    expect(unexpected).toEqual([]);
  });

  for (const width of [1440, 390]) {
    test(`archived Workspace bottom restore fits and activates by keyboard at ${width}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
      const unexpected = await prepareFixture(page, "183:176");
      const bar = page.locator('[aria-label="Archived workspace controls"]');
      const button = page.getByRole("button", {
        name: "Restore workspace",
        exact: true,
      });
      await expect(
        page.getByText("Archived workspace · Read-only", { exact: true }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      const box = await bar.boundingBox();
      expect(box!.y + box!.height).toBeLessThanOrEqual(
        width === 1440 ? 960 : 844,
      );
      if (width === 1440) {
        expect(box!.height).toBe(72);
        expect((await button.boundingBox())!.width).toBe(184);
        expect((await button.boundingBox())!.height).toBe(40);
      }
      await page.screenshot({
        path: `../.superpowers/figma/q1/evidence/parity-workspace-${width}.png`,
        animations: "disabled",
      });
      const restore = page.waitForRequest((request) =>
        request.url().endsWith("/fixture-workspace/restore"),
      );
      await button.focus();
      await button.press("Enter");
      const request = await restore;
      expect(request.method()).toBe("POST");
      expect(request.headers()["if-match"]).toBe("4");
      await expect(page).toHaveURL(/\/workspaces\/fixture-workspace$/);
      expect(unexpected).toEqual([]);
    });
  }

  test("narrow evidence and rail each open one modal and Escape restores their triggers", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const unexpected = await prepareFixture(page, "128:110");
    const citation = page.getByRole("button", { name: /citation 1/i });
    await citation.click();
    await expect(page.getByRole("dialog", { name: "Evidence" })).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(citation).toBeFocused();
    const trigger = page.getByRole("button", { name: "Show conversations" });
    await trigger.click();
    await expect(
      page.getByRole("dialog", { name: "Conversations" }),
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    expect(unexpected).toEqual([]);
  });

  test("divider arrows resize and Enter resets the actual panel width", async ({
    page,
  }) => {
    await prepareFixture(page, "128:110");
    const rail = page.getByRole("separator", {
      name: "Resize conversation rail",
    });
    await rail.focus();
    await rail.press("ArrowRight");
    await expect(rail).toHaveAttribute("aria-valuenow", "268");
    await rail.press("Enter");
    await expect(rail).toHaveAttribute("aria-valuenow", "252");
    expect(
      (
        await page
          .getByRole("navigation", { name: "Conversations" })
          .boundingBox()
      )?.width,
    ).toBe(252);
    expect(
      (await page.locator(".conversation-inspector-column").boundingBox())
        ?.width,
    ).toBe(376);
  });

  test("workspace dialog traps Tab, closes on Escape and returns focus", async ({
    page,
  }) => {
    const unexpected = await prepareFixture(page, "152:128");
    const trigger = page.getByRole("button", {
      name: "Create workspace",
      exact: true,
    });
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Create workspace" });
    await expect(
      page.getByLabel("Workspace name", { exact: true }),
    ).toBeFocused();
    for (let index = 0; index < 6; index++) {
      await page.keyboard.press("Tab");
      expect(
        await dialog.evaluate((element) =>
          element.contains(document.activeElement),
        ),
      ).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    expect(unexpected).toEqual([]);
  });

  test("workspace menu arrows and Escape retain keyboard context", async ({
    page,
  }) => {
    await prepareFixture(page, "154:134");
    await expect(
      page.getByRole("menuitem", { name: "Archive workspace" }),
    ).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(
      page.getByRole("menuitem", { name: "Archive workspace" }),
    ).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Workspace actions" }),
    ).toBeFocused();
  });

  test("native FTL OTP input accepts leading-zero paste and enables resend after the cooldown", async ({
    page,
    context,
  }) => {
    const now = new Date("2026-10-05T12:00:00Z");
    await page.clock.install({ time: now });
    const unexpected = await prepareFixture(page, "246:311");
    await page.clock.pauseAt(now);
    const resend = page.locator("#otp-resend");
    await expect(resend).toBeDisabled();
    await expect(page.locator("#otp-retry")).toHaveText("30");
    const code = page.getByRole("textbox", { name: "Six-digit reset code" });
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.evaluate(() => navigator.clipboard.writeText("000042"));
    await code.focus();
    await code.press("Control+V");
    await expect(code).toHaveValue("000042");
    await expect(code).toHaveAttribute("aria-invalid", "true");
    expect(await code.evaluate((input) => getComputedStyle(input).height)).toBe(
      "56px",
    );
    expect(await code.evaluate((input) => getComputedStyle(input).color)).toBe(
      "rgba(0, 0, 0, 0)",
    );
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.locator(".knora-otp-cells")).toHaveText("000042");
    await page.clock.setFixedTime(new Date(now.getTime() + 29_000));
    await page.clock.runFor(250);
    await expect(resend).toBeDisabled();
    await expect(page.locator("#otp-retry")).toHaveText("1");
    await page.clock.setFixedTime(new Date(now.getTime() + 30_000));
    await page.clock.runFor(250);
    await expect(resend).toBeEnabled();
    await expect(page.locator("#otp-retry")).toHaveText("0");
    await expect(resend).toHaveAttribute("name", "intent");
    await expect(resend).toHaveAttribute("value", "resend");
    await expect(resend).toHaveAttribute("formnovalidate", "");
    expect(unexpected).toEqual([]);
  });

  test("native FTL OTP remains a visible labelled single input with enabled resend without JavaScript", async ({
    browser,
    baseURL,
  }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    try {
      const page = await context.newPage();
      // Source fixtures never submit recovery actions, including with scripts blocked.
      await page.route("**/native/blocked-action", (route) => route.abort());
      await page.goto(`${baseURL}/native/242-333.html`);
      const input = page.getByRole("textbox", { name: "Six-digit reset code" });
      await expect(input).toBeVisible();
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
      await page.evaluate(() => navigator.clipboard.writeText("000042"));
      await input.focus();
      await input.press("Control+V");
      await expect(input).toHaveValue("000042");
      expect(
        await input.evaluate((element) => getComputedStyle(element).height),
      ).toBe("56px");
      expect(
        await input.evaluate((element) => getComputedStyle(element).color),
      ).not.toBe("rgba(0, 0, 0, 0)");
      await expect(page.locator(".knora-otp-cells")).toBeHidden();
      const resend = page.locator("#otp-resend");
      await expect(resend).toBeEnabled();
      await expect(resend).toHaveAttribute("name", "intent");
      await expect(resend).toHaveAttribute("value", "resend");
      await expect(resend).toHaveAttribute("formnovalidate", "");
      await expect(page.locator("#otp-retry")).toHaveText("30");
      await expect(page.locator("form")).toHaveAttribute("method", "post");
      await expect(page.locator("form")).toHaveAttribute(
        "action",
        "/native/blocked-action",
      );
      await input.fill("");
      await page.screenshot({
        path: "../.superpowers/figma/q1/evidence/otp-resend-no-js-enabled.png",
        animations: "disabled",
      });
    } finally {
      await context.close();
    }
  });

  test("light and dark text tokens meet contrast and reduced motion removes control transitions", async ({
    page,
  }) => {
    await prepareFixture(page, "128:110");
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const theme of ["light", "dark"]) {
      await page.evaluate((value) => {
        document.documentElement.dataset.theme = value;
      }, theme);
      const ratios = await page.evaluate(() => {
        const styles = getComputedStyle(document.documentElement);
        const luminance = (token: string) => {
          const hex = styles.getPropertyValue(token).trim().replace("#", "");
          const rgb = [0, 2, 4].map(
            (index) => parseInt(hex.slice(index, index + 2), 16) / 255,
          );
          const linear = rgb.map((value) =>
            value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
          );
          return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
        };
        return [
          ["--text-primary", "--surface"],
          ["--text-muted", "--surface"],
          ["--action-text", "--page"],
          ["--action-foreground", "--action"],
        ].map(([foreground, background]) => {
          const values = [luminance(foreground), luminance(background)].sort(
            (a, b) => b - a,
          );
          return (values[0] + 0.05) / (values[1] + 0.05);
        });
      });
      for (const ratio of ratios)
        expect(ratio, `${theme} text contrast`).toBeGreaterThanOrEqual(4.5);
    }
    const citation = page.getByRole("button", { name: /citation 1/i });
    await citation.focus();
    await citation.press("Tab");
    await page.keyboard.press("Shift+Tab");
    expect(
      await citation.evaluate(
        (button) => getComputedStyle(button).outlineWidth,
      ),
    ).toBe("2px");
    await page.unrouteAll();
    await prepareFixture(page, "128:122");
    expect(
      await page
        .getByRole("button", { name: "Archive document", exact: true })
        .evaluate((button) => getComputedStyle(button).transitionDuration),
    ).toBe("0s");
  });

  test("CSS 200 percent zoom reflows critical document actions without page overflow", async ({
    page,
  }, info) => {
    await prepareFixture(page, "128:122");
    await page.evaluate(() => {
      document.documentElement.style.zoom = "2";
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const action = page.getByRole("button", {
      name: "Request deletion",
      exact: true,
    });
    await action.scrollIntoViewIfNeeded();
    await expect(action).toBeVisible();
    await page.screenshot({
      path: info.outputPath("document-css-zoom-200.png"),
      animations: "disabled",
    });
  });

  test("empty suggestions edit the draft without submission; archived history remains read only", async ({
    page,
  }) => {
    const unexpected = await prepareFixture(page, "128:109");
    await page
      .getByRole("button", { name: "Summarize this workspace" })
      .click();
    await expect(page.getByLabel("Question", { exact: true })).toHaveValue(
      "Summarize this workspace",
    );
    expect(unexpected).toEqual([]);
    await page.unrouteAll();
    await prepareFixture(page, "128:119");
    await expect(
      page.getByText("This Conversation is read-only."),
    ).toBeVisible();
    await expect(page.getByLabel("Question", { exact: true })).toHaveCount(0);
  });
});

test.describe("guarded application journeys", () => {
  test.skip(
    process.env.FIGMA_TEST_MODE !== "application",
    "Dedicated guarded application project required.",
  );
  test("owned Workspace restores from the Conversation bottom bar while an archived Conversation stays archived", async ({
    page,
  }) => {
    const identity = realm.users.find((user) => user.username === "m5-user");
    if (!identity) throw new Error("Owned synthetic identity missing.");
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    const created = await page.request.post("/api/v1/workspaces", {
      headers: { "Idempotency-Key": randomUUID() },
      data: { name: `Conversation parity ${randomUUID()}` },
    });
    expect(created.status()).toBe(201);
    const workspace = (await created.json()) as WorkspaceResponse;
    const base = `/workspaces/${workspace.id}`;
    const createConversation = async () => {
      const response = await page.request.post(`/api/v1${base}/conversations`, {
        headers: { "Idempotency-Key": randomUUID() },
      });
      expect(response.status()).toBe(201);
      return (await response.json()) as ConversationResponse;
    };
    const active = await createConversation();
    const second = await createConversation();
    const archivedResponse = await page.request.post(
      `/api/v1${base}/conversations/${second.id}/archive`,
      { headers: { "If-Match": String(second.revision) } },
    );
    expect(archivedResponse.ok()).toBe(true);
    expect((await archivedResponse.json()).archived).toBe(true);
    await page.goto(`${base}/conversations/${active.id}`);
    await expect(page.getByLabel("Question", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Workspace actions" }).click();
    await page.getByRole("menuitem", { name: "Archive workspace" }).click();
    const archive = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith(`${base}/archive`),
    );
    await page
      .getByRole("dialog", { name: "Archive workspace" })
      .getByRole("button", { name: "Archive workspace", exact: true })
      .click();
    const archivedWorkspace = (await (
      await archive
    ).json()) as WorkspaceResponse;
    expect(archivedWorkspace.archived).toBe(true);
    await expect(
      page.getByRole("dialog", { name: "Archive workspace" }),
    ).toBeHidden();
    await page.goto(`${base}/conversations/${active.id}`);
    await expect(
      page.getByText("Archived workspace · Read-only", { exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("Question", { exact: true })).toHaveCount(0);
    await captureIdentity(
      page,
      "../.superpowers/figma/q1/evidence/parity-live-workspace-archived.png",
    );
    await page.goto(`${base}/conversations/${second.id}`);
    await expect(
      page.getByRole("button", { name: "Restore workspace", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Restore conversation", exact: true }),
    ).toHaveCount(0);
    const restore = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith(`${base}/restore`),
    );
    const selection = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/workspace-selection",
    );
    const button = page.getByRole("button", {
      name: "Restore workspace",
      exact: true,
    });
    await button.focus();
    await button.press("Enter");
    const restoredResponse = await restore;
    expect(restoredResponse.request().headers()["if-match"]).toBe(
      String(archivedWorkspace.revision),
    );
    expect(restoredResponse.ok()).toBe(true);
    const restored = (await restoredResponse.json()) as WorkspaceResponse;
    expect(restored.id).toBe(workspace.id);
    expect(restored.archived).toBe(false);
    expect(restored.revision).toBeGreaterThan(archivedWorkspace.revision);
    expect((await selection).status()).toBe(200);
    await expect(page).toHaveURL(new RegExp(`${base}$`));
    await page.goto(`${base}/conversations/${second.id}`);
    await expect(
      page.getByText("This Conversation is read-only.", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Restore conversation", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("Question", { exact: true })).toHaveCount(0);
    const retained = await page.request.get(
      `/api/v1${base}/conversations/${second.id}`,
    );
    expect((await retained.json()).archived).toBe(true);
    await captureIdentity(
      page,
      "../.superpowers/figma/q1/evidence/parity-live-conversation-still-archived.png",
    );
    await page.goto(`${base}/conversations/${active.id}`);
    await expect(page.getByLabel("Question", { exact: true })).toBeVisible();
    await captureIdentity(
      page,
      "../.superpowers/figma/q1/evidence/parity-live-workspace-restored.png",
    );
    fs.writeFileSync(
      "../.superpowers/figma/q1/evidence/parity-live-restore.json",
      JSON.stringify(
        {
          workspaceId: workspace.id,
          activeConversationId: active.id,
          archivedConversationId: second.id,
          archivedRevision: archivedWorkspace.revision,
          restoredRevision: restored.revision,
          restoreStatus: restoredResponse.status(),
          secondConversationArchived: true,
          resolvedPath: base,
        },
        null,
        2,
      ),
    );
  });
  test("owned document and workspace lifecycle; authoritative Turn submission and lost-response recovery", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const identity = realm.users.find(
      (user) => user.username === "m5-delete-user",
    );
    if (!identity) throw new Error("Owned synthetic identity missing.");
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    await page.goto("/workspaces");
    const navigation: string[] = [];
    page.on("request", (request) => {
      const pathname = new URL(request.url()).pathname;
      if (pathname.startsWith("/workspaces"))
        navigation.push(`request ${pathname}`);
    });
    page.on("requestfailed", (request) => {
      const pathname = new URL(request.url()).pathname;
      if (pathname.startsWith("/workspaces"))
        navigation.push(`failed ${pathname}`);
    });
    const name = `Q1 verification ${randomUUID()}`;
    await page
      .getByRole("button", { name: "Create workspace", exact: true })
      .click();
    const creation = page.getByRole("dialog", { name: "Create workspace" });
    await creation.getByLabel("Workspace name", { exact: true }).fill(name);
    const workspaceCreation = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/v1/workspaces",
    );
    const workspaceSelection = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/workspace-selection",
    );
    await creation
      .getByRole("button", { name: "Create workspace", exact: true })
      .click();
    const createdResponse = await workspaceCreation;
    expect(
      createdResponse.status(),
      "Authoritative workspace creation status",
    ).toBe(201);
    expect(
      (await workspaceSelection).status(),
      "Authoritative selection status",
    ).toBe(200);
    try {
      await expect(page).toHaveURL(/\/workspaces\/[^/]+$/);
    } finally {
      fs.writeFileSync(
        "../.superpowers/figma/q1/evidence/live-create-navigation.json",
        JSON.stringify(
          {
            creationStatus: 201,
            selectionStatus: 200,
            navigation,
            finalPath: new URL(page.url()).pathname,
          },
          null,
          2,
        ),
      );
    }
    const workspaceId = new URL(page.url()).pathname.split("/")[2];
    const base = `/workspaces/${workspaceId}`;
    const evidence = "../.superpowers/figma/q1/evidence";
    await page.goto(`${base}/documents`);
    await page
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    const upload = page.getByRole("dialog", { name: "Upload document" });
    const sourceName = "q1-report-structure.md";
    const statement =
      "The reporting guideline defines seven chapters in the report structure.";
    await upload.getByLabel("Document file").setInputFiles({
      name: sourceName,
      mimeType: "text/markdown",
      buffer: Buffer.from(statement),
    });
    const uploaded = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname ===
          `/api/v1/workspaces/${workspaceId}/documents`,
    );
    await upload
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    expect((await uploaded).ok()).toBe(true);
    await expect(upload).toBeHidden();
    await page.getByRole("link", { name: sourceName, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: sourceName, exact: true }),
    ).toBeVisible();
    await captureIdentity(page, `${evidence}/live-document-ready.png`);
    await page
      .getByRole("button", { name: "Archive document", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Restore document", exact: true }),
    ).toBeVisible();
    await captureIdentity(page, `${evidence}/live-document-archived.png`);
    await page
      .getByRole("button", { name: "Restore document", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Archive document", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Request deletion", exact: true })
      .click();
    const deletion = page.getByRole("dialog", {
      name: "Request document deletion",
    });
    // Confirmation/cancellation only. Existing policy must not be assumed to block submission.
    await captureIdentity(page, `${evidence}/live-deletion-confirm-only.png`);
    await deletion.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.goto(base);
    await page
      .getByRole("button", { name: "New Conversation", exact: true })
      .click();
    await expect(page).toHaveURL(/\/conversations\//);
    const conversationPath = new URL(page.url()).pathname;
    await expect(
      page.getByText("Loading history…", { exact: true }),
    ).toBeHidden();
    let accepted: TurnResponse | undefined;
    await page.route("**/turns", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      expect(response.ok()).toBe(true);
      accepted = (await response.json()) as TurnResponse;
      await route.abort("failed");
    });
    await page.getByLabel("Question", { exact: true }).fill(statement);
    await expect(page.getByLabel("Question", { exact: true })).toHaveValue(
      statement,
    );
    await expect(
      page.getByRole("button", { name: "Ask", exact: true }),
    ).toBeEnabled();
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "Submission status is uncertain" }),
    ).toContainText("Submission status is uncertain");
    await captureIdentity(page, `${evidence}/live-lost-response.png`);
    await page.unrouteAll();
    await page.goto(conversationPath);
    await expect(
      page.getByText("Loading history…", { exact: true }),
    ).toBeHidden();
    const history = await page.request.get(`/api/v1${conversationPath}/turns`);
    expect(history.ok()).toBe(true);
    const turns = (await history.json()).items as TurnResponse[];
    expect(turns.filter((turn) => turn.id === accepted?.id)).toHaveLength(1);
    fs.writeFileSync(
      `${evidence}/live-turn-observation.json`,
      JSON.stringify(
        {
          workspaceId,
          conversationPath,
          acceptedStatus: accepted?.status,
          observedStatus: turns.find((turn) => turn.id === accepted?.id)
            ?.status,
          turnId: accepted?.id,
          completionGap:
            "Owned graph has no authorized conversation worker; terminal answer/refusal/interruption is not proved.",
        },
        null,
        2,
      ),
    );
    await captureIdentity(page, `${evidence}/live-history-recovered.png`);
    const actions = page.getByRole("button", { name: /^Actions for / }).first();
    await actions.click();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("menuitem", { name: "Archive", exact: true }).click();
    await expect(
      page.getByText("This Conversation is read-only.", { exact: true }),
    ).toBeVisible();
    await captureIdentity(page, `${evidence}/live-conversation-archived.png`);
    await page
      .getByRole("button", { name: "Restore conversation", exact: true })
      .click();
    await expect(page.getByLabel("Question", { exact: true })).toBeVisible();
    await captureIdentity(page, `${evidence}/live-conversation-restored.png`);
    await page.getByRole("button", { name: "Workspace actions" }).click();
    await page.getByRole("menuitem", { name: "Archive workspace" }).click();
    await page
      .getByRole("dialog", { name: "Archive workspace" })
      .getByRole("button", { name: "Archive workspace", exact: true })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Archive workspace" }),
    ).toBeHidden();
    await page.goto(base);
    await expect(
      page.getByText("Archived workspace · Read-only", { exact: true }),
    ).toBeVisible();
    await captureIdentity(page, `${evidence}/live-workspace-archived.png`);
    await page
      .getByRole("button", { name: "Restore workspace", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "New Conversation", exact: true }),
    ).toBeVisible();
    await captureIdentity(page, `${evidence}/live-workspace-restored.png`);
    await page.goto("/workspaces");
    const rename = page.getByLabel(`Rename ${name}`, { exact: true });
    for (let index = 0; index < 5 && (await rename.count()) === 0; index++) {
      const more = page.getByRole("button", {
        name: "Load more Workspaces",
        exact: true,
      });
      if (!(await more.count())) break;
      const response = page.waitForResponse(
        (item) =>
          item.request().method() === "GET" &&
          new URL(item.url()).pathname === "/api/v1/workspaces",
      );
      await more.click();
      await response;
    }
    await rename.fill(`${name} retained`);
    await page
      .getByRole("button", { name: `Save ${name} name`, exact: true })
      .click();
    await expect(
      page.getByRole("link", { name: `${name} retained`, exact: true }),
    ).toBeVisible();
    await captureIdentity(page, `${evidence}/live-workspace-renamed.png`);
    // Owned synthetic data remains retained. No cleanup/deletion authority is inferred.
  });

  test("owned PDF upload exposes an authoritative job observation without starting a worker", async ({
    page,
  }) => {
    const identity = realm.users.find((user) => user.username === "m5-user");
    if (!identity) throw new Error("Owned synthetic identity missing.");
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    const seed = await page.request.post("/api/v1/workspaces", {
      headers: { "Idempotency-Key": randomUUID() },
      data: { name: `Q1 PDF observation ${randomUUID()}` },
    });
    expect(seed.status()).toBe(201);
    const workspace = (await seed.json()) as { id: string };
    await page.goto(`/workspaces/${workspace.id}/documents`);
    await page
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Upload document" });
    const text = "BT /F1 12 Tf 40 200 Td (Q1 synthetic PDF observation.) Tj ET";
    const objects = [
      "<< /Type /Catalog /Pages 2 0 R >>",
      "<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
      "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
      `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
    ];
    let pdf = "%PDF-1.4\n";
    const offsets = [0];
    for (const [index, object] of objects.entries()) {
      offsets.push(Buffer.byteLength(pdf));
      pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
    }
    const xref = Buffer.byteLength(pdf);
    pdf += `xref\n0 6\n0000000000 65535 f \n${offsets
      .slice(1)
      .map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`)
      .join(
        "",
      )}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
    await dialog.getByLabel("Document file").setInputFiles({
      name: "q1-observation.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from(pdf),
    });
    const upload = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith("/documents"),
    );
    await dialog
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    const response = await upload;
    expect(response.status()).toBe(202);
    const submitted = (await response.json()) as {
      document_id: string;
      ingestion_job_id: string;
    };
    const job = await page.request.get(
      `/api/v1/workspaces/${workspace.id}/ingestion-jobs/${submitted.ingestion_job_id}`,
    );
    expect(job.ok()).toBe(true);
    const observation = (await job.json()) as IngestionJobStatusResponse;
    const classification = classifyPDFObservation(observation);
    fs.writeFileSync(
      "../.superpowers/figma/q1/evidence/live-pdf-observation.json",
      JSON.stringify(
        {
          workspaceId: workspace.id,
          ...submitted,
          observation,
          classification,
        },
        null,
        2,
      ),
    );
    await expect(dialog).toBeHidden();
    await page
      .getByRole("link", { name: "q1-observation.pdf", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "q1-observation.pdf", exact: true }),
    ).toBeVisible();
    await captureIdentity(
      page,
      "../.superpowers/figma/q1/evidence/live-pdf-job.png",
    );
  });

  test("existing owned queued Turn reconciles to an actual grounded answer after the controller runner", async ({
    page,
  }) => {
    test.skip(
      process.env.FIGMA_CONTROLLER_PROOF !== "1",
      "Controller-processed preserved records required; no worker is started by this suite.",
    );
    const artifact = fs.existsSync(
      "../.superpowers/figma/q1/evidence/live-turn-terminal.json",
    )
      ? "../.superpowers/figma/q1/evidence/live-turn-terminal.json"
      : "../.superpowers/figma/q1/evidence/live-turn-observation.json";
    test.skip(
      !fs.existsSync(artifact),
      "Requires the preserved owned Q1 Turn processed by the controller.",
    );
    const observation = JSON.parse(fs.readFileSync(artifact, "utf8")) as {
      workspaceId: string;
      conversationPath: string;
      turnId: string;
    };
    if (
      !/^\/workspaces\/[a-f0-9-]+\/conversations\/[a-f0-9-]+$/.test(
        observation.conversationPath,
      ) ||
      !observation.conversationPath.startsWith(
        `/workspaces/${observation.workspaceId}/`,
      )
    )
      throw new Error("Owned Turn artifact scope rejected.");
    const identity = realm.users.find(
      (user) => user.username === "m5-delete-user",
    );
    if (!identity) throw new Error("Owned synthetic identity missing.");
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    await page.goto(observation.conversationPath);
    await expect(
      page.getByText("Loading history…", { exact: true }),
    ).toBeHidden();
    const response = await page.request.get(
      `/api/v1${observation.conversationPath}/turns/${observation.turnId}`,
    );
    expect(response.ok()).toBe(true);
    const turn = (await response.json()) as TurnResponse;
    expect(turn.status).toBe("answered");
    const citation = page.getByRole("button", { name: /citation 1/i }).first();
    await citation.click();
    await expect(
      page.getByRole("complementary", { name: /evidence/i }),
    ).toContainText("q1-report-structure.md");
    await captureIdentity(
      page,
      "../.superpowers/figma/q1/evidence/live-answer-evidence.png",
    );
    fs.writeFileSync(
      "../.superpowers/figma/q1/evidence/live-turn-terminal.json",
      JSON.stringify(
        {
          ...observation,
          status: turn.status,
          decision: turn.result?.decision,
          citationCount: turn.result?.citations.length,
          completionGap: null,
        },
        null,
        2,
      ),
    );
    if (
      !fs.existsSync(
        "../.superpowers/figma/q1/evidence/live-refusal-pending.json",
      )
    ) {
      await page
        .getByLabel("Question", { exact: true })
        .fill("Describe extraterrestrial volcanic ice skates zyx987.");
      const submission = page.waitForResponse(
        (item) =>
          item.request().method() === "POST" &&
          new URL(item.url()).pathname.endsWith("/turns"),
      );
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      const submitted = await submission;
      expect(submitted.ok()).toBe(true);
      const pending = (await submitted.json()) as TurnResponse;
      fs.writeFileSync(
        "../.superpowers/figma/q1/evidence/live-refusal-pending.json",
        JSON.stringify(
          {
            workspaceId: observation.workspaceId,
            conversationPath: observation.conversationPath,
            turnId: pending.id,
            status: pending.status,
          },
          null,
          2,
        ),
      );
    }
  });

  test("existing owned PDF reconciles to Ready after the controller isolated extractor", async ({
    page,
  }) => {
    test.skip(
      process.env.FIGMA_CONTROLLER_PROOF !== "1",
      "Controller-processed preserved PDF required.",
    );
    const artifact =
      "../.superpowers/figma/q1/evidence/live-pdf-observation.json";
    test.skip(
      !fs.existsSync(artifact),
      "Preserved owned PDF observation required.",
    );
    const ids = JSON.parse(fs.readFileSync(artifact, "utf8")) as {
      workspaceId: string;
      document_id: string;
      ingestion_job_id: string;
    };
    for (const id of [ids.workspaceId, ids.document_id, ids.ingestion_job_id])
      if (!/^[a-f0-9-]+$/.test(id))
        throw new Error("Owned PDF artifact scope rejected.");
    const identity = realm.users.find((user) => user.username === "m5-user");
    if (!identity) throw new Error("Owned synthetic identity missing.");
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    const base = `/api/v1/workspaces/${ids.workspaceId}`;
    const job = await page.request.get(
      `${base}/ingestion-jobs/${ids.ingestion_job_id}`,
    );
    expect(job.ok()).toBe(true);
    const observation = (await job.json()) as {
      status: string;
      attempt_count: number;
    };
    expect(observation.status).toBe("succeeded");
    await page.goto(
      `/workspaces/${ids.workspaceId}/documents/${ids.document_id}`,
    );
    await expect(
      page.getByRole("heading", { name: "q1-observation.pdf", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("region", { name: "Overview" })).toContainText(
      "Ready",
    );
    await captureIdentity(
      page,
      "../.superpowers/figma/q1/evidence/live-pdf-ready.png",
    );
    fs.writeFileSync(
      "../.superpowers/figma/q1/evidence/live-pdf-terminal.json",
      JSON.stringify({ ...ids, observation }, null, 2),
    );
  });

  test("existing owned unsupported Turn reconciles to an actual refusal after the controller runner", async ({
    page,
  }) => {
    test.skip(
      process.env.FIGMA_CONTROLLER_PROOF !== "1",
      "Controller-processed preserved refusal required.",
    );
    const artifact =
      "../.superpowers/figma/q1/evidence/live-refusal-pending.json";
    test.skip(
      !fs.existsSync(artifact),
      "Preserved owned refusal observation required.",
    );
    const ids = JSON.parse(fs.readFileSync(artifact, "utf8")) as {
      workspaceId: string;
      conversationPath: string;
      turnId: string;
    };
    if (
      !/^\/workspaces\/[a-f0-9-]+\/conversations\/[a-f0-9-]+$/.test(
        ids.conversationPath,
      ) ||
      !ids.conversationPath.startsWith(`/workspaces/${ids.workspaceId}/`)
    )
      throw new Error("Owned refusal scope rejected.");
    const identity = realm.users.find(
      (user) => user.username === "m5-delete-user",
    );
    if (!identity) throw new Error("Owned synthetic identity missing.");
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    await page.goto(ids.conversationPath);
    await expect(
      page.getByText("Loading history…", { exact: true }),
    ).toBeHidden();
    const response = await page.request.get(
      `/api/v1${ids.conversationPath}/turns/${ids.turnId}`,
    );
    expect(response.ok()).toBe(true);
    const turn = (await response.json()) as TurnResponse;
    expect(turn.status).toBe("refused");
    expect(turn.result?.decision).toBe("REFUSAL");
    expect(turn.result?.citations).toEqual([]);
    await expect(
      page.getByRole("heading", {
        name: "I don’t have enough evidence to answer that.",
      }),
    ).toBeVisible();
    await captureIdentity(
      page,
      "../.superpowers/figma/q1/evidence/live-refusal.png",
    );
    fs.writeFileSync(
      "../.superpowers/figma/q1/evidence/live-refusal-terminal.json",
      JSON.stringify(
        {
          ...ids,
          status: turn.status,
          decision: turn.result?.decision,
          citationCount: turn.result?.citations.length,
        },
        null,
        2,
      ),
    );
  });
});
