import { expect, test, type Page } from "@playwright/test";
import {
  prepareFixture,
  prototypeTrace,
  visualStates,
  fixtureStates,
  fixtureResponse,
  statePath,
  conversation as referenceConversation,
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

for (const state of ["228:293", "228:326"]) {
  test(`Authentication outcome ${state} renders readable tinted evidence cues`, async ({
    page,
  }) => {
    const unexpected = await prepareFixture(page, state);
    const evidence =
      "../.superpowers/figma/q1/evidence/auth-outcome-cues-2026-10-10";
    fs.mkdirSync(evidence, { recursive: true });
    for (const theme of ["light", "dark"]) {
      await page.evaluate((value) => {
        document.documentElement.dataset.theme = value;
      }, theme);
      const cues = await page
        .locator(".kn-auth-outcome__cue--sources, .kn-auth-outcome__cue--pages")
        .evaluateAll((elements) =>
          elements.map((element) => {
            const style = getComputedStyle(element);
            return {
              label: element.textContent!.trim(),
              background: style.backgroundColor,
              color: style.color,
              height: element.getBoundingClientRect().height,
              pages: element.classList.contains("kn-auth-outcome__cue--pages"),
            };
          }),
        );
      const present = cues.every(
        (cue) => cue.background !== "rgba(0, 0, 0, 0)",
      );
      await page.screenshot({
        path: `${evidence}/${present ? "green" : "red"}-${state.replace(":", "-")}-${theme}.png`,
      });
      fs.writeFileSync(
        `${evidence}/${present ? "green" : "red"}-${state.replace(":", "-")}-${theme}.json`,
        JSON.stringify(cues, null, 2),
      );
      expect(cues).toHaveLength(3);
      for (const cue of cues) {
        expect(cue.height).toBe(26);
        expect(cue.background).toBe(
          theme === "light"
            ? cue.pages
              ? "rgb(230, 245, 235)"
              : "rgb(244, 234, 230)"
            : cue.pages
              ? "rgb(22, 62, 39)"
              : "rgb(52, 37, 31)",
        );
        const luminance = (color: string) => {
          const values = color
            .match(/[\d.]+/g)!
            .slice(0, 3)
            .map((value) => Number(value) / 255)
            .map((value) =>
              value <= 0.04045
                ? value / 12.92
                : ((value + 0.055) / 1.055) ** 2.4,
            );
          return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
        };
        const values = [luminance(cue.color), luminance(cue.background)].sort(
          (a, b) => b - a,
        );
        expect((values[0] + 0.05) / (values[1] + 0.05)).toBeGreaterThanOrEqual(
          4.5,
        );
      }
    }
    await expect(
      page.getByRole("link", {
        name: state === "228:293" ? "Try again" : "Try signing in again",
        exact: true,
      }),
    ).toHaveAttribute("href", "/api/auth/login");
    expect(unexpected).toEqual([]);
  });
}

for (const state of ["154:431", "166:211", "166:290", "183:490"]) {
  test(`Workspace source ${state} preserves the desktop state origin`, async ({
    page,
  }) => {
    const unexpected = await prepareFixture(page, state);
    const block = page.locator(
      state === "183:490" ? ".workspace-denied" : ".workspace-archives",
    );
    const box = (await block.boundingBox())!;
    const evidence =
      "../.superpowers/figma/q1/evidence/workspace-state-origin-2026-10-10";
    fs.mkdirSync(evidence, { recursive: true });
    const conforms =
      state === "183:490"
        ? Math.abs(box.y - 279) < 1 && Math.abs(box.height - 330) < 1
        : Math.abs(box.y - 108) < 1;
    await page.screenshot({
      path: `${evidence}/${conforms ? "green" : "red"}-${state.replace(":", "-")}.png`,
    });
    fs.writeFileSync(
      `${evidence}/${conforms ? "green" : "red"}-${state.replace(":", "-")}.json`,
      JSON.stringify(box, null, 2),
    );
    if (state === "183:490") {
      expect(box.x).toBeCloseTo(400, 0);
      expect(box.y).toBeCloseTo(279, 0);
      expect(box.width).toBe(640);
      expect(box.height).toBe(330);
      await expect(
        block.getByRole("link", { name: "Choose another workspace" }),
      ).toHaveAttribute("href", "/workspaces");
      const action = block.getByRole("link", {
        name: "Choose another workspace",
      });
      await expect(action).toHaveCSS("color", "rgb(255, 255, 255)");
      expect((await action.boundingBox())!.height).toBe(40);
      expect(
        await action.evaluate((element) => {
          const text = document.createRange();
          text.selectNodeContents(element);
          return text.getBoundingClientRect().height <= 20;
        }),
      ).toBe(true);
    } else {
      expect(box.x).toBeCloseTo(120, 0);
      expect(box.y).toBeCloseTo(108, 0);
      expect(box.width).toBe(1200);
      if (state !== "154:431")
        expect(
          (await block.locator(".workspace-archives-empty").boundingBox())!
            .height,
        ).toBe(655);
    }
    expect(unexpected).toEqual([]);
    await page.unrouteAll();
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileUnexpected = await prepareFixture(page, state);
    const mobileBlock = page.locator(
      state === "183:490" ? ".workspace-denied" : ".workspace-archives",
    );
    expect(
      await mobileBlock.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    if (state === "183:490")
      await expect(
        mobileBlock.getByRole("link", { name: "Choose another workspace" }),
      ).toBeInViewport();
    await page.screenshot({
      path: `${evidence}/mobile-${state.replace(":", "-")}.png`,
    });
    expect(mobileUnexpected).toEqual([]);
  });
}

for (const width of [252, 200]) {
  test(`Workspace Archive menu remains fully usable beside the ${width}px rail`, async ({
    page,
  }) => {
    const unexpected = await prepareFixture(page, "154:134");
    if (width === 200) {
      await page
        .getByRole("separator", {
          name: "Resize conversation rail",
          exact: true,
        })
        .press("Home");
      await page
        .getByRole("button", { name: "Workspace actions", exact: true })
        .press("ArrowDown");
    }
    const item = page.getByRole("menuitem", {
      name: "Archive workspace",
      exact: true,
    });
    const usable = await item.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return [box.left + 2, box.right - 2].every((x) =>
        element.contains(document.elementFromPoint(x, box.y + box.height / 2)),
      );
    });
    const evidence =
      "../.superpowers/figma/q1/evidence/rail-overflow-2026-10-10";
    await page.screenshot({
      path: `${evidence}/workspace-menu-${usable ? "green" : "red"}-${width}.png`,
    });
    expect(usable).toBe(true);
    await item.click();
    const dialog = page.getByRole("dialog", { name: /Archive workspace/i });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Workspace actions", exact: true }),
    ).toBeFocused();
    expect(unexpected).toEqual([]);
  });
}

for (const railMode of [
  "expanded",
  "minimum",
  "collapsed",
  "mobile",
] as const) {
  test(`long ${railMode} Conversation rail scrolls without covering its footer`, async ({
    page,
  }) => {
    const evidence = path.resolve(
      process.cwd(),
      "../.superpowers/figma/q1/evidence/rail-overflow-2026-10-10",
    );
    fs.mkdirSync(evidence, { recursive: true });
    if (railMode === "mobile")
      await page.setViewportSize({ width: 390, height: 844 });
    const unexpected = await prepareFixture(page, "128:110");
    await page.route(
      "**/api/v1/workspaces/fixture-workspace/conversations?*",
      async (route) => {
        if (route.request().method() !== "GET") return route.fallback();
        const secondPage = new URL(route.request().url()).searchParams.has(
          "cursor",
        );
        await route.fulfill({
          json: {
            items: Array.from(
              { length: secondPage ? 10 : 20 },
              (_, offset) => ({
                ...referenceConversation,
                id: `long-conversation-${secondPage ? offset + 20 : offset}`,
                title: `Long conversation ${secondPage ? offset + 20 : offset}`,
              }),
            ),
            next_cursor: secondPage ? null : "long-list-next-page",
          },
        });
      },
    );
    await page.reload();
    if (railMode === "mobile")
      await page
        .getByRole("button", { name: "Show conversations", exact: true })
        .click();
    const rail = page.getByRole("navigation", {
      name: "Conversations",
      exact: true,
    });
    if (railMode === "minimum")
      await page
        .getByRole("separator", {
          name: "Resize conversation rail",
          exact: true,
        })
        .press("Home");
    await rail
      .getByRole("searchbox", { name: "Search conversations", exact: true })
      .fill("Long");
    await expect(
      rail.getByRole("link", { name: "Long conversation 19", exact: true }),
    ).toHaveCount(1);
    const more = rail.getByRole("button", {
      name: "Load more Conversations",
      exact: true,
    });
    await more.scrollIntoViewIfNeeded();
    await expect(more).toBeInViewport();
    await more.click();
    await expect(
      rail.getByRole("link", { name: "Long conversation 29", exact: true }),
    ).toHaveCount(1);
    await expect(more).toBeHidden();
    if (railMode === "collapsed")
      await rail
        .getByRole("button", { name: "Collapse rail", exact: true })
        .click();
    const list = rail.getByRole("list");
    const scrollArea = list.locator("..");
    const geometry = await scrollArea.evaluate((element) => ({
      overflowY: getComputedStyle(element).overflowY,
      scrollHeight: element.scrollHeight,
      clientHeight: element.clientHeight,
    }));
    const phase = geometry.overflowY === "auto" ? "implemented" : "red";
    await page.screenshot({
      path: path.join(evidence, `${phase}-${railMode}.png`),
    });
    fs.writeFileSync(
      path.join(evidence, `${phase}-${railMode}.json`),
      JSON.stringify(geometry, null, 2),
    );
    expect(geometry.overflowY).toBe("auto");
    expect(geometry.scrollHeight).toBeGreaterThan(geometry.clientHeight);
    const footer = rail.getByRole("button", {
      name: railMode === "collapsed" ? "Expand rail" : "Collapse rail",
      exact: true,
    });
    await expect(footer).toBeInViewport();
    expect(
      await footer.evaluate((element) => {
        const box = element.getBoundingClientRect();
        return element.contains(
          document.elementFromPoint(
            box.x + box.width / 2,
            box.y + box.height / 2,
          ),
        );
      }),
    ).toBe(true);
    await scrollArea.evaluate((element) => {
      element.scrollTop = element.scrollHeight;
    });
    const last = rail.getByRole("link", {
      name: "Long conversation 29",
      exact: true,
    });
    await expect(last).toBeInViewport();
    await last.focus();
    await expect(last).toBeFocused();
    if (railMode !== "collapsed") {
      await expect(
        rail.getByRole("link", {
          name: "View archived Conversations",
          exact: true,
        }),
      ).toBeInViewport();
      const trigger = rail.getByRole("button", {
        name: "Actions for Long conversation 29",
        exact: true,
      });
      await trigger.press("ArrowDown");
      await expect(
        rail.getByRole("menuitem", { name: "Rename", exact: true }),
      ).toBeInViewport();
      for (const name of ["Rename", "Archive"]) {
        const item = rail.getByRole("menuitem", { name, exact: true });
        await expect(item).toBeInViewport();
        expect(
          await item.evaluate((element) => {
            const box = element.getBoundingClientRect();
            return element.contains(
              document.elementFromPoint(box.x + 2, box.y + box.height / 2),
            );
          }),
        ).toBe(true);
      }
      await page.screenshot({
        path: path.join(evidence, `menu-${railMode}.png`),
      });
      await page.keyboard.press("Escape");
      await expect(trigger).toBeFocused();
    }
    await page.screenshot({
      path: path.join(evidence, `scrolled-${railMode}.png`),
    });
    if (railMode === "mobile") {
      const drawer = page.getByRole("dialog", {
        name: "Conversations",
        exact: true,
      });
      expect(
        await drawer.evaluate(
          (element) => element.scrollHeight <= element.clientHeight + 1,
        ),
      ).toBe(true);
      await page
        .getByRole("button", { name: "Close Conversations", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Show conversations", exact: true }),
      ).toBeFocused();
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(unexpected).toEqual([]);
  });
}

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
  await expect
    .poll(() =>
      page.locator("main img, header img").evaluateAll((elements) =>
        elements.every((element) => {
          const image = element as HTMLImageElement;
          return image.complete && image.naturalWidth > 0;
        }),
      ),
    )
    .toBe(true);
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
        fits:
          element.scrollWidth <= element.clientWidth ||
          element.hasAttribute("data-source-overflow") ||
          Boolean(element.querySelector("[data-source-overflow]")),
        overflowY: style.overflowY,
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
        fontFamily: style.fontFamily,
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
    const label = main.querySelector(".workspace-selector-label")!;
    const title = main.querySelector("h1")!;
    const description = main.querySelector(":scope > p")!;
    const navigation = main.querySelector(
      'nav[aria-label="Operator navigation"]',
    )!;
    const divider = navigation.nextElementSibling;
    const lookup = main.querySelector("form");
    const guidance = main.querySelector(
      '[aria-labelledby="operator-trace-guidance-heading"], [aria-labelledby="operator-report-guidance-heading"]',
    );
    const origin = label.getBoundingClientRect().y;
    const relative = (element: Element) => ({
      ...box(element),
      top: element.getBoundingClientRect().y - origin,
    });
    const frameFlow = {
      origin,
      selector: relative(main.querySelector(".workspace-selector-heading")!),
      title: relative(title),
      description: {
        ...relative(description),
        ...word(description),
        lineHeight: getComputedStyle(description).lineHeight,
        maxWidth: getComputedStyle(description).maxWidth,
      },
      navigation: relative(navigation),
      divider:
        divider?.getAttribute("aria-hidden") === "true"
          ? relative(divider)
          : null,
      tabs: Array.from(navigation.querySelectorAll("a")).map((tab) => {
        const text = tab.querySelector("span") ?? tab;
        const style = getComputedStyle(tab);
        const rect = tab.getBoundingClientRect();
        return {
          ...relative(tab),
          offsetX: rect.x - navigation.getBoundingClientRect().x,
          offsetY: rect.y - navigation.getBoundingClientRect().y,
          label: word(text),
          labelOffsetY: text.getBoundingClientRect().y - rect.y,
          underlineTop: rect.height - parseFloat(style.borderBottomWidth),
          underlineHeight: parseFloat(style.borderBottomWidth),
          underlineColor: style.borderBottomColor,
          active: tab.getAttribute("aria-current") === "page",
        };
      }),
      lookup: lookup && relative(lookup),
      lookupLabel: lookup && relative(lookup.querySelector("label")!),
      guidance: guidance && relative(guidance),
    };
    const band = main.querySelector('dl[aria-label="Runtime signals"]');
    const columns = main.querySelector("article > div");
    const answer = main.querySelector(
      'section[aria-labelledby="observed-result-heading"] > p:last-of-type',
    );
    const badge = main.querySelector(
      'section[aria-labelledby="evaluation-heading"] > div > div > span',
    );
    const traceBadges = Array.from(
      main.querySelectorAll(
        'section[aria-labelledby="observed-result-heading"] .kn-status-badge, section[aria-labelledby="candidate-heading"] .kn-status-badge',
      ),
    ).map((element) => {
      const text = element.lastElementChild!;
      const rect = element.getBoundingClientRect();
      const textRect = text.getBoundingClientRect();
      return {
        ...box(element),
        label: text.textContent,
        kind: element.getAttribute("data-kind"),
        paddingLeft: getComputedStyle(element).paddingLeft,
        textOffsetX: textRect.x - rect.x,
        textOffsetY: textRect.y - rect.y,
        textHeight: textRect.height,
        iconVisible:
          getComputedStyle(element.firstElementChild!).display !== "none",
        text: word(text),
      };
    });
    const signals = main.querySelector(
      'dl[aria-label="Trace summary signals"]',
    );
    const result = main.querySelector(
      'section[aria-labelledby="observed-result-heading"]',
    );
    const resultSlot = (element: Element) => ({
      ...word(element),
      top:
        element.getBoundingClientRect().y - result!.getBoundingClientRect().y,
      lineHeight: getComputedStyle(element).lineHeight,
    });
    const traceContent = signals && {
      summary: box(signals),
      signals: Array.from(signals.children).map((cell) => {
        const label = cell.querySelector("dt")!;
        const value = cell.querySelector("dd")!;
        return {
          ...box(cell),
          minHeight: getComputedStyle(cell).minHeight,
          label: {
            ...box(label),
            lineHeight: getComputedStyle(label).lineHeight,
          },
          value: {
            ...box(value),
            lineHeight: getComputedStyle(value).lineHeight,
          },
          labelOffset:
            label.getBoundingClientRect().y - signals.getBoundingClientRect().y,
          valueOffset:
            value.getBoundingClientRect().y - signals.getBoundingClientRect().y,
        };
      }),
      resultRow: box(
        main.querySelector(
          'section[aria-labelledby="observed-result-heading"] > div',
        )!,
      ),
      explanation: box(
        main.querySelector('section[aria-labelledby="candidate-heading"] > p')!,
      ),
      resultHeading: resultSlot(result!.querySelector("h2")!),
      answer: resultSlot(answer!),
      citations: {
        ...resultSlot(result!.lastElementChild!),
        markers: Array.from(result!.lastElementChild!.children)
          .slice(1)
          .map(word),
      },
      provenanceHeading: resultSlot(main.querySelector("#candidate-heading")!),
      description: resultSlot(
        main.querySelector('section[aria-labelledby="candidate-heading"] > p')!,
      ),
      list: resultSlot(
        main.querySelector(
          'section[aria-labelledby="candidate-heading"] > ol',
        )!,
      ),
      candidates: Array.from(
        main.querySelectorAll(
          'section[aria-labelledby="candidate-heading"] > ol > li',
        ),
      ).map((candidate) => {
        const slot = (element: Element) => ({
          ...word(element),
          top:
            element.getBoundingClientRect().y -
            candidate.getBoundingClientRect().y,
          lineHeight: getComputedStyle(element).lineHeight,
          maxWidth: getComputedStyle(element).maxWidth,
        });
        return {
          ...box(candidate),
          top:
            candidate.getBoundingClientRect().y -
            result!.getBoundingClientRect().y,
          name: slot(candidate.querySelector("strong")!),
          badge: slot(candidate.querySelector(".kn-status-badge")!),
          metadata: slot(candidate.querySelector(":scope > p")!),
          excerpt: slot(candidate.querySelector(":scope > p:last-of-type")!),
          disclosure: slot(candidate.querySelector("summary")!),
        };
      }),
      contextRows: Array.from(
        main.querySelectorAll(
          'section[aria-labelledby="trace-context-heading"] dl > div',
        ),
      ).map((row) => ({
        ...box(row),
        minHeight: getComputedStyle(row).minHeight,
        paddingTop: getComputedStyle(row).paddingTop,
        lineHeight: getComputedStyle(row).lineHeight,
        gap: getComputedStyle(row).columnGap,
        label: box(row.querySelector("dt")!),
        value: box(row.querySelector("dd")!),
      })),
      headings: [
        "trace-context-heading",
        "citation-mapping-heading",
        "phase-timing-heading",
      ].map((id) => ({
        id,
        ...box(main.querySelector(`#${id}`)!),
        lineHeight: getComputedStyle(main.querySelector(`#${id}`)!).lineHeight,
      })),
    };
    const reportHeading = main.querySelector("#report-context-heading");
    const evaluationContent = reportHeading && {
      title: box(main.querySelector("#evaluation-heading")!),
      heading: {
        ...box(reportHeading),
        lineHeight: getComputedStyle(reportHeading).lineHeight,
      },
      explanation: (() => {
        const element = main.querySelector(
          'section[aria-labelledby="evaluation-heading"] > div > p',
        )!;
        return {
          ...box(element),
          text: element.textContent,
          minHeight: getComputedStyle(element).minHeight,
          maxWidth: getComputedStyle(element).maxWidth,
          lineHeight: getComputedStyle(element).lineHeight,
        };
      })(),
      contextRows: Array.from(reportHeading.nextElementSibling!.children).map(
        (row) => ({
          ...box(row),
          minHeight: getComputedStyle(row).minHeight,
          paddingTop: getComputedStyle(row).paddingTop,
          paddingBottom: getComputedStyle(row).paddingBottom,
          borderBottom: getComputedStyle(row).borderBottomWidth,
          gap: getComputedStyle(row).columnGap,
          label: {
            ...box(row.querySelector("dt")!),
            text: row.querySelector("dt")!.textContent,
            lineHeight: getComputedStyle(row.querySelector("dt")!).lineHeight,
          },
          value: {
            ...box(row.querySelector("dd")!),
            text: row.querySelector("dd")!.textContent,
            lineHeight: getComputedStyle(row.querySelector("dd")!).lineHeight,
          },
        }),
      ),
    };
    const accounting = main.querySelector(
      'section[aria-labelledby="operations-heading"] > h3 + dl',
    );
    const operationsContent =
      accounting &&
      (() => {
        const rows = (list: Element) =>
          Array.from(list.children).map((row) => ({
            ...box(row),
            minHeight: getComputedStyle(row).minHeight,
            borderBottom: getComputedStyle(row).borderBottomWidth,
            label: {
              ...word(row.querySelector("dt")!),
              lineHeight: getComputedStyle(row.querySelector("dt")!).lineHeight,
            },
            value: {
              ...word(row.querySelector("dd")!),
              lineHeight: getComputedStyle(row.querySelector("dd")!).lineHeight,
            },
          }));
        const buckets = main.querySelector(
          'dl[aria-label="Cumulative latency buckets"]',
        )!;
        const alerts = main.querySelector(
          'section[aria-labelledby="operations-heading"] [role="status"]',
        )!;
        return {
          accounting: {
            ...box(accounting),
            columnGap: getComputedStyle(accounting).columnGap,
            paddingRight: getComputedStyle(accounting).paddingRight,
            paddingBottom: getComputedStyle(accounting).paddingBottom,
            rows: rows(accounting),
          },
          buckets: {
            ...box(buckets),
            columnGap: getComputedStyle(buckets).columnGap,
            rowGap: getComputedStyle(buckets).rowGap,
            paddingBottom: getComputedStyle(buckets).paddingBottom,
            rows: rows(buckets),
          },
          alerts: {
            ...box(alerts),
            minHeight: getComputedStyle(alerts).minHeight,
            backgroundColor: getComputedStyle(alerts).backgroundColor,
            label: {
              ...word(alerts.firstElementChild!),
              lineHeight: getComputedStyle(alerts.firstElementChild!)
                .lineHeight,
            },
            body: {
              ...word(alerts.lastElementChild!),
              lineHeight: getComputedStyle(alerts.lastElementChild!).lineHeight,
            },
          },
        };
      })();
    return {
      frameFlow,
      workspaceLabel: box(main.querySelector(".workspace-selector-label")!),
      traceBadges,
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
      ...(traceContent ? { traceContent } : {}),
      ...(evaluationContent ? { evaluationContent } : {}),
      ...(operationsContent ? { operationsContent } : {}),
    };
  });
  const flow = geometry.frameFlow;
  const evaluation = state === "216:698" || state === "216:755";
  expect.soft(flow.description.fontSize).toBe("16px");
  expect.soft(flow.description.lineHeight).toBe(evaluation ? "24px" : "19px");
  // Font ink can extend beyond a source line allocation; visible overflow and
  // parent/navigation clearance prove the complete copy remains readable.
  expect.soft(flow.description.fits).toBe(true);
  expect.soft(flow.description.textFitsParent).toBe(true);
  expect.soft(flow.description.overflowY).toBe("visible");
  expect
    .soft(flow.description.ink.y + flow.description.ink.height)
    .toBeLessThanOrEqual(flow.navigation.y);
  expect.soft(flow.navigation.height).toBeGreaterThanOrEqual(42);
  expect.soft(flow.tabs.filter((tab) => tab.active)).toHaveLength(1);
  for (const tab of flow.tabs) {
    expect.soft(tab.fits).toBe(true);
    expect.soft(tab.label.textFitsParent).toBe(true);
    expect
      .soft(tab.fontWeight)
      .toBe(
        evaluation ? (tab.active ? "500" : "400") : tab.active ? "600" : "500",
      );
    expect.soft(tab.underlineHeight).toBe(2);
    expect
      .soft(tab.underlineColor)
      .toBe(tab.active ? "rgb(51, 161, 91)" : "rgba(0, 0, 0, 0)");
  }
  if (width === 1440) {
    expect.soft(flow.origin, "source content global origin").toBe(109);
    expect.soft(flow.selector).toMatchObject({ top: 18, height: 26 });
    expect.soft(flow.title).toMatchObject({ top: 58, height: 42 });
    expect
      .soft(flow.description)
      .toMatchObject({ top: 105, height: evaluation ? 24 : 19 });
    if (!operations && !evaluation)
      expect.soft(flow.description.maxWidth).toBe("870px");
    expect.soft(flow.navigation).toMatchObject({ top: 151, height: 42 });
    expect
      .soft(flow.divider, "source divider is separate from nav allocation")
      .toMatchObject({ top: 193, height: 1 });
    for (const [index, tab] of flow.tabs.entries()) {
      expect.soft(tab).toMatchObject({
        offsetX: [0, 104, 182][index],
        offsetY: 7.5,
        width: [76, 50, 82][index],
        height: 27,
        labelOffsetY: operations ? 0 : 5,
        underlineTop: 25,
      });
      expect
        .soft(tab.label.height, "allocated tab label region, distinct from ink")
        .toBe(evaluation ? 20 : 17);
    }
    if (flow.lookup && geometry.input && geometry.button) {
      expect.soft(flow.lookup).toMatchObject({ top: 211, height: 56 });
      expect.soft(flow.lookupLabel).toMatchObject({ top: 211, height: 13 });
      expect
        .soft(flow.lookupLabel?.fontWeight)
        .toBe(evaluation ? "500" : "600");
      expect.soft(geometry.input.y - flow.origin).toBe(229);
      expect.soft(geometry.button.y - flow.origin).toBe(229);
    }
    if (flow.guidance) expect.soft(flow.guidance.top).toBe(326);
  } else {
    expect.soft(flow.description.height).toBeGreaterThan(evaluation ? 24 : 19);
    expect
      .soft(flow.navigation.y)
      .toBeGreaterThanOrEqual(flow.description.y + flow.description.height);
    if (flow.lookup) expect.soft(flow.lookup.height).toBeGreaterThan(56);
  }
  expect
    .soft(geometry.workspaceLabel.fontSize, "Operator Workspace label")
    .toBe("11px");
  expect.soft(geometry.workspaceLabel.fontWeight).toBe("600");
  expect
    .soft(geometry.workspaceLabel.fontFamily.toLowerCase())
    .toContain("inter");
  for (const badge of geometry.traceBadges) {
    expect.soft(badge).toMatchObject({
      width: badge.label === "ANSWER" ? 110 : 150,
      height: 28,
      radius: "7px",
      fontSize: "12px",
      fontWeight: "600",
      paddingLeft: "10px",
      textOffsetX: 10,
      textOffsetY: 6,
      textHeight: 16,
      iconVisible: false,
      kind: "success",
      fits: true,
    });
    expect.soft(badge.fontFamily.toLowerCase()).toContain("inter");
    expect.soft(badge.text.lines).toBe(1);
    expect.soft(badge.text.textFitsParent).toBe(true);
  }
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
    expect.soft(geometry.input.fontSize).toBe(trace ? "13px" : "14px");
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
  if (geometry.traceContent) {
    const content = geometry.traceContent;
    for (const region of [content.answer, content.description]) {
      expect.soft(region.fits).toBe(true);
      expect.soft(region.textFitsParent).toBe(true);
    }
    for (const candidate of content.candidates) {
      for (const slot of [
        candidate.name,
        candidate.metadata,
        candidate.excerpt,
        candidate.disclosure,
      ]) {
        expect.soft(slot.fits).toBe(true);
        expect.soft(slot.textFitsParent).toBe(true);
      }
      expect.soft(candidate.height).toBeGreaterThanOrEqual(128);
      expect
        .soft(
          candidate.disclosure.top -
            candidate.excerpt.top -
            candidate.excerpt.height,
        )
        .toBe(8);
      expect.soft(candidate.disclosure.lineHeight).toBe("18px");
    }
    for (let index = 1; index < content.candidates.length; index++) {
      const previous = content.candidates[index - 1];
      expect
        .soft(content.candidates[index].y - previous.y - previous.height)
        .toBe(8);
    }
    for (const signal of content.signals) {
      expect.soft(signal.minHeight).toBe("82px");
      expect
        .soft(signal.label)
        .toMatchObject({ fontSize: "13px", lineHeight: "17px", fits: true });
      expect
        .soft(signal.value)
        .toMatchObject({ fontSize: "22px", lineHeight: "26px", fits: true });
    }
    expect
      .soft(
        content.headings.map(({ fontSize, lineHeight }) => [
          fontSize,
          lineHeight,
        ]),
      )
      .toEqual([
        ["20px", "24px"],
        ["18px", "22px"],
        ["18px", "22px"],
      ]);
    for (const row of content.contextRows) {
      expect.soft(row).toMatchObject({
        minHeight: "38px",
        fontSize: "13px",
        lineHeight: "17px",
        paddingTop: "7px",
        gap: "10px",
        fits: true,
      });
    }
    if (width === 1440) {
      expect.soft(content.resultHeading).toMatchObject({ top: 0, height: 24 });
      expect.soft(geometry.traceBadges[0].y - content.resultRow.y).toBe(0);
      expect
        .soft(content.answer)
        .toMatchObject({ top: 34, height: 40, width: 630, lineHeight: "20px" });
      expect
        .soft(content.citations)
        .toMatchObject({ top: 82, height: 24, lineHeight: "16px" });
      for (const marker of content.citations.markers) {
        expect.soft(marker.height).toBe(22);
        expect.soft(marker.width).toBeGreaterThanOrEqual(38);
      }
      expect
        .soft(content.provenanceHeading)
        .toMatchObject({ top: 126, height: 24 });
      expect.soft(content.description).toMatchObject({ top: 156, height: 18 });
      expect.soft(content.list.top).toBe(190);
      expect.soft(content.candidates[0].top).toBe(190);
      for (const candidate of content.candidates) {
        // Retained disclosure adds 26px to the source's 102px clipped row.
        expect.soft(candidate.height).toBe(128);
        expect
          .soft(candidate.name)
          .toMatchObject({ top: 7, height: 20, maxWidth: "420px" });
        expect
          .soft(candidate.badge)
          .toMatchObject({ top: 4, height: 28, width: 150 });
        expect
          .soft(candidate.metadata)
          .toMatchObject({ top: 33, height: 17, lineHeight: "16px" });
        expect.soft(candidate.excerpt).toMatchObject({
          top: 60,
          height: 20,
          maxWidth: "610px",
          lineHeight: "18px",
        });
        expect
          .soft(candidate.disclosure)
          .toMatchObject({ top: 88, height: 18 });
      }
      expect
        .soft(
          content.summary.height,
          "Trace outer summary includes both borders",
        )
        .toBe(84);
      for (const signal of content.signals) {
        expect.soft(signal.height).toBe(82);
        expect
          .soft(signal.labelOffset, "source label top from outer band")
          .toBe(15);
        expect
          .soft(signal.valueOffset, "source value top from outer band")
          .toBe(39);
      }
      expect.soft(content.resultRow.width).toBe(760);
      expect
        .soft(geometry.traceBadges[0].x - geometry.columns!.children[0].x)
        .toBe(650);
      expect.soft(content.explanation.width).toBe(730);
      for (const candidate of content.candidates) {
        expect.soft(candidate.width).toBe(760);
        expect.soft(candidate.name.width).toBeLessThanOrEqual(420);
        expect.soft(candidate.name.maxWidth).toBe("420px");
      }
      for (const row of content.contextRows) {
        expect.soft(row.height).toBe(38);
        expect.soft(row.label.width).toBe(170);
        expect.soft(row.value.width).toBe(200);
        expect.soft(row.label.y - row.y).toBe(7);
        expect.soft(row.value.y - row.y).toBe(7);
      }
      const contextOrigin = content.headings[0].y;
      expect.soft(content.headings[1].y - contextOrigin).toBe(205);
      expect.soft(content.headings[2].y - contextOrigin).toBe(318);
    }
  }
  if (geometry.evaluationContent) {
    const content = geometry.evaluationContent;
    expect.soft(content.heading).toMatchObject({
      fontSize: "22px",
      lineHeight: "24px",
      height: 24,
      fits: true,
    });
    expect.soft(content.explanation).toMatchObject({
      minHeight: "70px",
      maxWidth: "680px",
      fontSize: "16px",
      lineHeight: "20px",
      fits: true,
    });
    for (const row of content.contextRows) {
      expect.soft(row).toMatchObject({
        minHeight: "40px",
        paddingTop: "10px",
        paddingBottom: "5px",
        borderBottom: "1px",
        gap: "10px",
        fits: true,
      });
      expect.soft(row.label.lineHeight).toBe("24px");
      expect.soft(row.value.lineHeight).toBe("24px");
      expect.soft(row.label.fits).toBe(true);
      expect.soft(row.value.fits).toBe(true);
      expect.soft(row.height).toBeGreaterThanOrEqual(40);
    }
    if (width === 1440) {
      expect.soft(content.explanation.width).toBe(680);
      expect.soft(content.explanation.height).toBe(70);
      expect.soft(content.explanation.y - content.title.y).toBe(44);
      expect.soft(content.contextRows[0].label.y - content.heading.y).toBe(44);
      for (const row of content.contextRows) {
        expect.soft(row.label.width).toBe(170);
        expect
          .soft(row.value.width)
          .toBe(row.label.text === "Observation code" ? 300 : 200);
        expect.soft(row.label.y - row.y).toBe(10);
        expect.soft(row.value.y - row.y).toBe(10);
      }
      for (const [index, row] of content.contextRows.slice(0, 3).entries()) {
        expect.soft(row.height).toBe(40);
        expect.soft(row.y + row.height - 1 - row.label.y).toBe(29);
        expect
          .soft(content.contextRows[index + 1].label.y - row.label.y)
          .toBe(40);
      }
    } else {
      expect.soft(content.explanation.height).toBeGreaterThan(70);
      for (const row of content.contextRows) {
        expect.soft(row.height).toBeGreaterThan(40);
        expect.soft(row.value.y).toBeGreaterThan(row.label.y);
      }
    }
  }
  if (geometry.operationsContent) {
    const { accounting, buckets, alerts } = geometry.operationsContent;
    for (const [list, rowHeight, fontSize, textTop] of [
      [accounting, 49, "14px", 14],
      [buckets, 40, "13px", 10],
    ] as const) {
      expect.soft(list.columnGap).toBe("20px");
      for (const row of list.rows) {
        expect.soft(row.minHeight).toBe(`${rowHeight}px`);
        expect.soft(row.borderBottom).toBe("1px");
        expect.soft(row.height).toBeGreaterThanOrEqual(rowHeight);
        for (const text of [row.label, row.value]) {
          expect.soft(text).toMatchObject({
            fontSize,
            lineHeight: "20px",
            fits: true,
            textFitsParent: true,
          });
          expect.soft(text.y - row.y).toBe(textTop);
        }
        expect.soft(row.value.fontWeight).toBe("600");
      }
    }
    expect.soft(buckets.rowGap).toBe("6px");
    expect
      .soft(alerts)
      .toMatchObject({ minHeight: "70px", radius: "8px", fits: true });
    expect.soft(alerts.height).toBeGreaterThanOrEqual(70);
    expect.soft(alerts.backgroundColor).toBe("rgb(244, 234, 230)");
    expect.soft(alerts.label).toMatchObject({
      text: "ALERTS",
      fontSize: "11px",
      fontWeight: "600",
      lineHeight: "15px",
      height: 15,
      fits: true,
      textFitsParent: true,
    });
    expect.soft(alerts.body).toMatchObject({
      text: "Unavailable in the current Operator contract.",
      fontSize: "13px",
      lineHeight: "20px",
      fits: true,
      textFitsParent: true,
    });
    expect.soft(alerts.label.x - alerts.x).toBe(14);
    expect.soft(alerts.label.y - alerts.y).toBe(12);
    expect.soft(alerts.body.y - alerts.y).toBe(35);
    if (width === 1440) {
      expect.soft(accounting).toMatchObject({
        width: 1200,
        height: 148,
        paddingRight: "20px",
        paddingBottom: "1px",
      });
      expect
        .soft(buckets)
        .toMatchObject({ width: 760, height: 92, paddingBottom: "6px" });
      for (const [
        list,
        rowWidth,
        rowHeight,
        columnStep,
        rowStep,
        valueOffset,
      ] of [
        [accounting, 580, 49, 600, 49, 420],
        [buckets, 370, 40, 390, 46, 310],
      ] as const) {
        for (const [index, row] of list.rows.entries()) {
          expect.soft(row.width).toBe(rowWidth);
          expect.soft(row.height).toBe(rowHeight);
          expect.soft(row.x - list.x).toBe((index % 2) * columnStep);
          expect.soft(row.y - list.y).toBe(Math.floor(index / 2) * rowStep);
          expect.soft(row.label.x - row.x).toBe(0);
          expect.soft(row.value.x - row.x).toBe(valueOffset);
          expect.soft(row.label.height).toBe(20);
          expect.soft(row.value.height).toBe(20);
        }
      }
      expect
        .soft(buckets.rows.map((row) => row.value.width))
        .toEqual([60, 60, 60, 60]);
      expect.soft(alerts).toMatchObject({ width: 380, height: 70 });
      expect.soft(alerts.body.height).toBe(20);
    } else {
      expect
        .soft(accounting.rows.every((row) => row.width === accounting.width))
        .toBe(true);
      expect
        .soft(buckets.rows.every((row) => row.width === buckets.width))
        .toBe(true);
    }
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

  for (const viewport of [
    { width: 1440, height: 960 },
    { width: 390, height: 844 },
  ]) {
    test(`Document detail action height and cancellation at ${viewport.width}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const evidence =
        "../.superpowers/figma/q1/evidence/document-detail-action-height-2026-10-08";
      fs.mkdirSync(evidence, { recursive: true });
      const requests: string[] = [];
      const writes: string[] = [];
      const observations: unknown[] = [];
      page.on("request", (request) => {
        const pathname = new URL(request.url()).pathname;
        if (!pathname.startsWith("/api/")) return;
        const entry = `${request.method()} ${pathname}`;
        requests.push(entry);
        if (request.method() !== "GET") writes.push(entry);
      });
      for (const state of ["128:122", "128:125"]) {
        const requestStart = requests.length;
        const unexpected = await prepareFixture(page, state);
        const archived = state === "128:125";
        const article = page.locator("article");
        const overview = page.getByRole("region", {
          name: "Overview",
          exact: true,
        });
        await expect(article.getByRole("heading", { level: 1 })).toHaveText(
          "Teacher Manh – Guidelines 2024.pdf",
        );
        await expect(overview.locator("dl > div").nth(0)).toHaveText(
          `Status${archived ? "Archived" : "Ready"}`,
        );
        await expect(overview.locator("dl > div").nth(1)).toHaveText(
          `Available for new answers${archived ? "No" : "Yes"}`,
        );
        await expect(overview.locator("dl > div").nth(2)).toContainText(
          "Current: fixture-version",
        );
        await expect(overview.locator("dl > div").nth(2)).toContainText(
          "Served: fixture-version",
        );
        await expect(overview.locator("dl > div").nth(3)).not.toContainText(
          "Unavailable",
        );
        const source = page.getByRole("region", {
          name: "Source",
          exact: true,
        });
        await expect(source.getByRole("link")).toHaveAttribute(
          "href",
          "/workspaces/fixture-workspace/documents/fixture-document",
        );
        await source.getByText("Source details", { exact: true }).click();
        for (const value of ["guidelines-2024", "7", "succeeded"])
          await expect(
            source.locator("details dd").filter({ hasText: value }),
          ).toBeVisible();
        await source.getByText("Source details", { exact: true }).click();
        await expect(article.locator("input, textarea, select")).toHaveCount(0);

        await page.evaluate(async () => {
          await document.fonts.ready;
          await Promise.all(
            Array.from(document.images).map((img) => img.decode()),
          );
        });
        const assets = [
          { src: "/brand/knora-leaf.svg", size: 18 },
          ...(!archived ? [{ src: "/icons/figma/97a8a.svg", size: 7 }] : []),
        ];
        for (const asset of assets) {
          expect(fs.statSync(`public${asset.src}`).size).toBeGreaterThan(0);
          const image = page.locator(`img[src="${asset.src}"]`);
          await expect(image).toHaveCount(1);
          expect(
            await image.evaluate(
              (el: HTMLImageElement) => el.complete && el.naturalWidth > 0,
            ),
          ).toBe(true);
          const box = (await image.boundingBox())!;
          expect(box.width).toBeCloseTo(asset.size, 1);
          expect(box.height).toBeCloseTo(asset.size, 1);
        }
        await expect(
          overview.locator('img[src="/icons/figma/97a8a.svg"]'),
        ).toHaveCount(archived ? 0 : 1);

        const deletion = page.getByRole("button", {
          name: "Request deletion",
          exact: true,
        });
        await expect(deletion).toBeEnabled();
        const ordinaryNames = archived
          ? ["Restore document"]
          : ["Reprocess document", "Archive document"];
        const actions = [];
        for (const name of [...ordinaryNames, "Request deletion"]) {
          const button = page.getByRole("button", { name, exact: true });
          await expect(button).toBeEnabled();
          const box = (await button.boundingBox())!;
          actions.push({
            name,
            ...box,
            minHeight: await button.evaluate(
              (el) => getComputedStyle(el).minHeight,
            ),
          });
          if (viewport.width === 1440) expect(box.width).toBeCloseTo(298, 1);
          expect(box.x).toBeGreaterThanOrEqual(0);
          expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
          if (name !== "Request deletion") {
            expect(box.height).toBeCloseTo(42, 1);
            expect(
              await button.evaluate((el) => getComputedStyle(el).minHeight),
            ).toBe("42px");
          }
        }
        await expect(
          page.getByRole("button", {
            name: archived ? "Reprocess document" : "Restore document",
            exact: true,
          }),
        ).toHaveCount(0);
        const geometry = await page.evaluate(() => ({
          pageFits: document.documentElement.scrollWidth <= innerWidth,
          fields: Array.from(document.querySelectorAll("article dl > div")).map(
            (el) => ({
              text: el.textContent,
              height: el.getBoundingClientRect().height,
            }),
          ),
          assets: Array.from(document.images).map((img) => ({
            src: img.getAttribute("src"),
            width: img.getBoundingClientRect().width,
            height: img.getBoundingClientRect().height,
            loaded: img.complete && img.naturalWidth > 0,
          })),
        }));
        expect(geometry.pageFits).toBe(true);
        if ((await deletion.boundingBox())!.height !== 40) {
          fs.writeFileSync(
            `${evidence}/red-${state.replace(":", "-")}-${viewport.width}.json`,
            JSON.stringify({ viewport, actions, ...geometry }, null, 2),
          );
          await page.screenshot({
            path: `${evidence}/red-${state.replace(":", "-")}-${viewport.width}.png`,
            fullPage: true,
          });
        }
        expect((await deletion.boundingBox())!.height).toBeCloseTo(40, 1);
        expect(
          await deletion.evaluate((el) => getComputedStyle(el).minHeight),
        ).toBe("40px");
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({
          path: `${evidence}/implemented-${state.replace(":", "-")}-${viewport.width}.png`,
          fullPage: true,
        });

        await deletion.click();
        const dialog = page.getByRole("dialog", {
          name: "Request document deletion",
          exact: true,
        });
        await expect(dialog).toBeVisible();
        await expect(dialog).toContainText(
          "Teacher Manh – Guidelines 2024.pdf",
        );
        await expect(dialog).toContainText(
          archived ? "PDF source · Archived" : "PDF source · Ready",
        );
        const cancel = dialog.getByRole("button", {
          name: "Cancel",
          exact: true,
        });
        const confirm = dialog.getByRole("button", {
          name: "Request deletion",
          exact: true,
        });
        await expect(cancel).toBeEnabled();
        await expect(cancel).toBeFocused();
        await expect(confirm).toBeEnabled();
        const dialogBox = (await dialog.boundingBox())!;
        expect(dialogBox.x).toBeGreaterThanOrEqual(0);
        expect(dialogBox.y).toBeGreaterThanOrEqual(0);
        expect(dialogBox.x + dialogBox.width).toBeLessThanOrEqual(
          viewport.width,
        );
        expect(dialogBox.y + dialogBox.height).toBeLessThanOrEqual(
          viewport.height,
        );
        await page.screenshot({
          path: `${evidence}/dialog-${state.replace(":", "-")}-${viewport.width}.png`,
          fullPage: true,
        });
        await cancel.click();
        await expect(dialog).toBeHidden();
        await expect(deletion).toBeFocused();
        await deletion.press("Enter");
        await expect(dialog).toBeVisible();
        await expect(
          dialog.getByRole("button", { name: "Cancel", exact: true }),
        ).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(dialog).toBeHidden();
        await expect(deletion).toBeFocused();
        expect(requests.slice(requestStart).sort()).toEqual([
          "GET /api/v1/workspaces/fixture-workspace/documents/fixture-document",
        ]);
        expect(unexpected).toEqual([]);
        expect(writes).toEqual([]);
        observations.push({
          state,
          viewport,
          actions,
          ...geometry,
          dialog: dialogBox,
          cancelFocusReturned: true,
          escapeFocusReturned: true,
          requests: requests.slice(requestStart),
          unexpected: [...unexpected],
          writes: [...writes],
        });
      }
      fs.writeFileSync(
        `${evidence}/journey-${viewport.width}.json`,
        JSON.stringify(observations, null, 2),
      );
    });
  }

  for (const viewport of [
    { width: 1440, height: 960 },
    { width: 390, height: 844 },
  ]) {
    test(`Documents Upload trigger matches source allocation ${viewport.width} and retains dialog focus`, async ({
      page,
    }) => {
      const evidence =
        "../.superpowers/figma/q1/evidence/document-upload-trigger-2026-10-08";
      fs.mkdirSync(evidence, { recursive: true });
      const requests: string[] = [];
      const writes: string[] = [];
      page.on("request", (request) => {
        const pathname = new URL(request.url()).pathname;
        if (!pathname.startsWith("/api/")) return;
        const invocation = `${request.method()} ${pathname}`;
        requests.push(invocation);
        if (request.method() !== "GET") writes.push(invocation);
      });
      await page.setViewportSize(viewport);
      const unexpected = await prepareFixture(page, "128:120");
      const documents = page.getByRole("region", {
        name: "Documents",
        exact: true,
      });
      const trigger = documents.getByRole("button", {
        name: "Upload document",
        exact: true,
      });
      await page.evaluate(() => document.fonts.ready);
      await expect
        .poll(() =>
          page.locator("img").evaluateAll((images) =>
            images.every((element) => {
              const image = element as HTMLImageElement;
              return image.complete && image.naturalWidth > 0;
            }),
          ),
        )
        .toBe(true);
      const geometry = await trigger.evaluate((button) => {
        const style = getComputedStyle(button);
        const plus = button.querySelector("span")!;
        const plusBox = plus.getBoundingClientRect();
        const buttonBox = button.getBoundingClientRect();
        const label = button.lastChild as Text;
        const labelRange = document.createRange();
        labelRange.selectNodeContents(label);
        const labelBox = labelRange.getBoundingClientRect();
        const labelLines = labelRange.getClientRects().length;
        const images = Array.from(
          document.querySelectorAll<HTMLImageElement>(
            'img[src="/brand/knora-leaf.svg"], .documents-workspace-caret',
          ),
        ).map((image) => ({
          src: image.getAttribute("src"),
          width: image.getBoundingClientRect().width,
          height: image.getBoundingClientRect().height,
          loaded: image.complete && image.naturalWidth > 0,
        }));
        return {
          width: buttonBox.width,
          height: buttonBox.height,
          radius: parseFloat(style.borderTopLeftRadius),
          gap: parseFloat(style.columnGap),
          paddingLeft: parseFloat(style.paddingLeft),
          paddingRight: parseFloat(style.paddingRight),
          plusFont: parseFloat(getComputedStyle(plus).fontSize),
          labelFont: parseFloat(style.fontSize),
          plusWidth: plusBox.width,
          labelWidth: labelBox.width,
          labelLines,
          contentRequired:
            plusBox.width + parseFloat(style.columnGap) + labelBox.width,
          contentAvailable:
            buttonBox.width -
            parseFloat(style.paddingLeft) -
            parseFloat(style.paddingRight) -
            parseFloat(style.borderLeftWidth) -
            parseFloat(style.borderRightWidth),
          textFits:
            plusBox.left >= buttonBox.left &&
            labelBox.right <= buttonBox.right &&
            button.scrollWidth <= button.clientWidth,
          documentFits: document.documentElement.scrollWidth <= innerWidth,
          images,
        };
      });
      await captureIdentity(
        page,
        `${evidence}/header-128-120-${viewport.width}.png`,
      );
      fs.writeFileSync(
        `${evidence}/geometry-${viewport.width}.json`,
        JSON.stringify(
          { viewport, geometry, requests, unexpected, writes },
          null,
          2,
        ),
      );
      expect(geometry.width).toBe(154);
      expect(geometry.height).toBe(38);
      expect(geometry.plusFont).toBe(15);
      expect(geometry.labelFont).toBe(13);
      expect(geometry.gap).toBe(8);
      expect(geometry.radius).toBe(8);
      expect(geometry.contentRequired).toBeLessThanOrEqual(
        geometry.contentAvailable,
      );
      expect(geometry.labelLines).toBe(1);
      expect(geometry.paddingLeft).toBe(10);
      expect(geometry.paddingRight).toBe(10);
      expect(geometry.textFits).toBe(true);
      expect(geometry.documentFits).toBe(true);
      expect(geometry.images).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            src: "/brand/knora-leaf.svg",
            width: 18,
            height: 18,
            loaded: true,
          }),
          expect.objectContaining({
            src: "/icons/figma/d9407.svg",
            width: 8,
            height: 5,
            loaded: true,
          }),
        ]),
      );
      const dialog = page.getByRole("dialog", {
        name: "Upload document",
        exact: true,
      });
      await trigger.click();
      await expect(dialog).toBeVisible();
      await expect(
        dialog.getByRole("button", { name: "Upload document", exact: true }),
      ).toBeDisabled();
      await captureIdentity(
        page,
        `${evidence}/dialog-128-120-${viewport.width}.png`,
      );
      await dialog.getByRole("button", { name: "Cancel" }).click();
      await expect(dialog).toBeHidden();
      await expect(trigger).toBeFocused();
      await trigger.click();
      await expect(dialog).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
      await expect(trigger).toBeFocused();
      expect(unexpected).toEqual([]);
      expect(writes).toEqual([]);
      expect(requests.length).toBeGreaterThan(0);
    });
    test(`Documents local interactions ${viewport.width} verifies filters, menus and cancelled dialogs without mutations`, async ({
      page,
    }) => {
      const evidence =
        "../.superpowers/figma/q1/evidence/document-upload-trigger-2026-10-08/local-interactions";
      fs.mkdirSync(evidence, { recursive: true });
      const apiRequests: string[] = [];
      const writes: string[] = [];
      page.on("request", (request) => {
        const pathname = new URL(request.url()).pathname;
        if (!pathname.startsWith("/api/")) return;
        const invocation = `${request.method()} ${pathname}`;
        apiRequests.push(invocation);
        if (request.method() !== "GET") writes.push(invocation);
      });
      await page.setViewportSize(viewport);
      const unexpected = await prepareFixture(page, "128:120");
      const fixtureURL = page.url();
      const documents = page.getByRole("region", {
        name: "Documents",
        exact: true,
      });
      const rows = documents
        .getByRole("list", { name: "Documents" })
        .getByRole("listitem");
      const readyName = "Teacher Manh – Guidelines 2024.pdf";
      const archivedName = "Legacy handbook.pdf";
      const row = (name: string) =>
        rows.filter({ has: page.getByRole("link", { name, exact: true }) });
      const readyTrigger = row(readyName).getByRole("button", {
        name: `Actions for ${readyName}`,
        exact: true,
      });
      const archivedTrigger = row(archivedName).getByRole("button", {
        name: `Actions for ${archivedName}`,
        exact: true,
      });
      const readyMenu = page.getByRole("menu", {
        name: `Actions for ${readyName}`,
        exact: true,
      });
      const archivedMenu = page.getByRole("menu", {
        name: `Actions for ${archivedName}`,
        exact: true,
      });
      const geometry: unknown[] = [];
      const capture = async (state: string, selector: string) => {
        await page.evaluate(() => document.fonts.ready);
        await expect
          .poll(() =>
            page.locator("img").evaluateAll((images) =>
              images.every((element) => {
                const image = element as HTMLImageElement;
                return image.complete && image.naturalWidth > 0;
              }),
            ),
          )
          .toBe(true);
        const measured = await page.locator(selector).evaluate((surface) => {
          const box = (element: Element) => {
            const bounds = element.getBoundingClientRect();
            return {
              x: bounds.x,
              y: bounds.y,
              width: bounds.width,
              height: bounds.height,
            };
          };
          return {
            surface: box(surface),
            fits: surface.scrollWidth <= surface.clientWidth,
            pageFits: document.documentElement.scrollWidth <= window.innerWidth,
            controls: Array.from(
              surface.querySelectorAll('button, [role="menuitem"]'),
            ).map((control) => ({
              text: control.textContent,
              fits: control.scrollWidth <= control.clientWidth,
              ...box(control),
            })),
            assets: Array.from(
              document.querySelectorAll<HTMLImageElement>(
                'img[src="/brand/knora-leaf.svg"], .documents-workspace-caret',
              ),
            ).map((asset) => ({
              src: asset.getAttribute("src"),
              loaded: asset.complete && asset.naturalWidth > 0,
              ...box(asset),
            })),
          };
        });
        if (measured.surface.y + measured.surface.height > viewport.height) {
          fs.writeFileSync(
            `${evidence}/${state}-${viewport.width}-viewport-failure.json`,
            JSON.stringify(measured, null, 2),
          );
          await page.screenshot({
            path: `${evidence}/${state}-${viewport.width}-viewport-failure.png`,
            fullPage: true,
          });
        }
        expect(measured.fits).toBe(true);
        expect(measured.pageFits).toBe(true);
        expect(measured.surface.x).toBeGreaterThanOrEqual(0);
        expect(measured.surface.y).toBeGreaterThanOrEqual(0);
        expect(measured.surface.x + measured.surface.width).toBeLessThanOrEqual(
          viewport.width,
        );
        expect(
          measured.surface.y + measured.surface.height,
        ).toBeLessThanOrEqual(viewport.height);
        expect(measured.controls.every((control) => control.fits)).toBe(true);
        expect(measured.assets).toEqual(
          expect.arrayContaining([
            expect.objectContaining({
              src: "/brand/knora-leaf.svg",
              loaded: true,
              width: 18,
              height: 18,
            }),
            expect.objectContaining({
              src: "/icons/figma/d9407.svg",
              loaded: true,
              width: 8,
              height: 5,
            }),
          ]),
        );
        geometry.push({ state, ...measured });
        await page.screenshot({
          path: `${evidence}/${state}-${viewport.width}.png`,
          fullPage: true,
        });
      };

      await expect(rows).toHaveCount(5);
      await expect(
        documents.getByText("5 documents", { exact: true }),
      ).toBeVisible();
      const showArchived = documents.getByRole("checkbox", {
        name: "Show archived",
      });
      await expect(showArchived).toBeChecked();
      await expect(readyMenu).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(readyMenu).toBeHidden();
      await expect(readyTrigger).toBeFocused();
      await showArchived.uncheck();
      await expect(rows).toHaveCount(4);
      await expect(row(archivedName)).toHaveCount(0);
      await expect(
        documents.getByText("4 documents", { exact: true }),
      ).toBeVisible();
      // Edge 8 opens Ready actions with archived rows excluded.
      await readyTrigger.press("ArrowDown");
      await expect(readyMenu).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(readyTrigger).toBeFocused();
      await showArchived.check();
      await expect(rows).toHaveCount(5);
      await expect(row(archivedName)).toBeVisible();
      await expect(
        documents.getByText("5 documents", { exact: true }),
      ).toBeVisible();
      const search = documents.getByRole("searchbox", {
        name: "Search documents",
      });
      await search.fill("Reporting policy.pdf");
      await expect(rows).toHaveCount(1);
      await expect(row("Reporting policy.pdf")).toBeVisible();
      await expect(row(readyName)).toHaveCount(0);
      await expect(
        documents.getByText("1 document", { exact: true }),
      ).toBeVisible();
      await search.fill("No matching document local interaction");
      await expect(rows).toHaveCount(0);
      await expect(
        documents.getByText("No documents found.", { exact: true }),
      ).toBeVisible();
      await expect(
        documents.getByText("0 documents", { exact: true }),
      ).toBeVisible();
      await search.clear();
      await expect(rows).toHaveCount(5);
      await expect(
        documents.getByText("5 documents", { exact: true }),
      ).toBeVisible();

      await readyTrigger.press("ArrowDown");
      await expect(readyMenu.getByRole("menuitem")).toHaveText([
        "View details",
        "Reprocess document",
        "Archive document",
        "Request deletion",
      ]);
      const details = readyMenu.getByRole("menuitem", {
        name: "View details",
        exact: true,
      });
      const destination =
        "/workspaces/fixture-workspace/documents/fixture-document";
      const menuSlots = await readyMenu.evaluate((menu) => {
        const bounds = menu.getBoundingClientRect();
        const content = menu.closest('section[aria-label="Documents"]')!;
        const items = Array.from(menu.querySelectorAll('[role="menuitem"]'));
        return {
          rightInset: content.getBoundingClientRect().right - bounds.right,
          width: bounds.width,
          itemGap:
            items[1].getBoundingClientRect().top -
            items[0].getBoundingClientRect().bottom,
        };
      });
      expect.soft(menuSlots.width).toBe(200);
      expect.soft(menuSlots.itemGap).toBe(2);
      if (viewport.width === 1440) expect.soft(menuSlots.rightInset).toBe(5);
      await expect(details).toHaveAttribute("href", destination);
      await expect(
        row(readyName).getByRole("link", { name: readyName, exact: true }),
      ).toHaveAttribute("href", destination);
      await expect(details).toBeFocused();
      await page.keyboard.press("ArrowDown");
      await expect(
        readyMenu.getByRole("menuitem", {
          name: "Reprocess document",
          exact: true,
        }),
      ).toBeFocused();
      await page.keyboard.press("ArrowUp");
      await expect(details).toBeFocused();
      await capture("ready-menu", '[role="menu"]');
      await page.keyboard.press("Escape");
      await expect(readyTrigger).toBeFocused();

      const deletion = page.getByRole("dialog", {
        name: "Request document deletion",
        exact: true,
      });
      await readyTrigger.press("ArrowUp");
      await expect(
        readyMenu.getByRole("menuitem", {
          name: "Request deletion",
          exact: true,
        }),
      ).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(deletion).toBeVisible();
      await expect(
        deletion.getByText(readyName, { exact: true }),
      ).toBeVisible();
      await expect(
        deletion.getByRole("button", { name: "Cancel", exact: true }),
      ).toBeEnabled();
      // This is the existing confirmation control; it is deliberately never invoked.
      await expect(
        deletion.getByRole("button", { name: "Request deletion", exact: true }),
      ).toBeEnabled();
      await deletion
        .getByRole("button", { name: "Cancel", exact: true })
        .click();
      await expect(deletion).toBeHidden();
      await expect(readyTrigger).toBeFocused();
      await readyTrigger.press("ArrowUp");
      await page.keyboard.press("Enter");
      await expect(deletion).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(deletion).toBeHidden();
      await expect(readyTrigger).toBeFocused();

      await archivedTrigger.evaluate((trigger) =>
        trigger.scrollIntoView({ block: "center" }),
      );
      await archivedTrigger.press("ArrowDown");
      await expect(archivedMenu.getByRole("menuitem")).toHaveText([
        "View details",
        "Restore document",
        "Request deletion",
      ]);
      await expect(
        archivedMenu.getByRole("menuitem", {
          name: "Reprocess document",
          exact: true,
        }),
      ).toHaveCount(0);
      await capture("archived-menu", '[role="menu"]');
      await page.keyboard.press("Escape");
      await expect(archivedMenu).toBeHidden();
      await expect(archivedTrigger).toBeFocused();
      await archivedTrigger.press("ArrowUp");
      await page.keyboard.press("Enter");
      await expect(deletion).toBeVisible();
      await expect(
        deletion.getByText(archivedName, { exact: true }),
      ).toBeVisible();
      await expect(
        deletion.getByRole("button", { name: "Request deletion", exact: true }),
      ).toBeEnabled();
      await capture("archived-deletion-confirm", "dialog[open]");
      await deletion
        .getByRole("button", { name: "Cancel", exact: true })
        .click();
      await expect(deletion).toBeHidden();
      await expect(archivedTrigger).toBeFocused();

      const uploadTrigger = documents.getByRole("button", {
        name: "Upload document",
        exact: true,
      });
      const uploadTriggerGeometry = await uploadTrigger.boundingBox();
      const upload = page.getByRole("dialog", {
        name: "Upload document",
        exact: true,
      });
      await uploadTrigger.click();
      await expect(upload).toBeVisible();
      await expect(
        upload.getByRole("button", { name: "Upload document", exact: true }),
      ).toBeDisabled();
      await upload.getByLabel("Document file", { exact: true }).setInputFiles({
        name: "Reporting policy.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from(
          "%PDF-1.4\nlocal selected-file presentation only; never submitted",
        ),
      });
      await expect(
        upload.getByText("Reporting policy.pdf", { exact: true }),
      ).toBeVisible();
      await expect(
        upload.getByRole("button", { name: "Upload document", exact: true }),
      ).toBeEnabled();
      await capture("upload-selected", "dialog[open]");
      await upload.getByRole("button", { name: "Cancel", exact: true }).click();
      await expect(upload).toBeHidden();
      await expect(uploadTrigger).toBeFocused();
      await uploadTrigger.click();
      await expect(upload).toBeVisible();
      await expect(
        upload.getByText("Reporting policy.pdf", { exact: true }),
      ).toHaveCount(0);
      await expect(
        upload.getByText("SELECTED FILE", { exact: true }),
      ).toHaveCount(0);
      await expect(
        upload.getByLabel("Document file", { exact: true }),
      ).toHaveValue("");
      await expect(
        upload.getByRole("button", { name: "Upload document", exact: true }),
      ).toBeDisabled();
      await page.keyboard.press("Escape");
      await expect(upload).toBeHidden();
      await expect(uploadTrigger).toBeFocused();
      await expect(rows).toHaveCount(5);
      await expect(
        documents.getByText("5 documents", { exact: true }),
      ).toBeVisible();
      // The state-driven host is never used to claim a production destination transition.
      expect(page.url()).toBe(fixtureURL);
      expect(unexpected).toEqual([]);
      expect(writes).toEqual([]);
      expect(apiRequests.length).toBeGreaterThan(0);
      fs.writeFileSync(
        `${evidence}/journey-${viewport.width}.json`,
        JSON.stringify(
          {
            viewport,
            state: "128:120",
            geometry,
            uploadTriggerGeometry,
            apiRequests,
            unexpected,
            writes,
            urlCheck: { destination, fixtureURL, navigationInvoked: false },
            limits:
              "Local controls only; no upload, reprocess, archive, restore or deletion submission, production destination, lifecycle or authorization acceptance.",
          },
          null,
          2,
        ),
      );
    });
  }

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
        // The header's Next Image is lazy: fonts/hydration ready does not imply
        // its SVG has finished loading. Await readiness before reading geometry.
        await expect
          .poll(() =>
            page.locator("main img, header img").evaluateAll((elements) =>
              elements.every((element) => {
                const image = element as HTMLImageElement;
                return image.complete && image.naturalWidth > 0;
              }),
            ),
          )
          .toBe(true);
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
                !element.closest("[data-source-overflow]") &&
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
            await details.locator("summary").focus();
            await page.keyboard.press("Enter");
            await expect(details).toHaveAttribute("open", "");
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
            for (const value of await details.locator("dd").all())
              await expect(value).toBeVisible();
            const collapsedHeight =
              sourceGeometry.traceContent!.candidates[index].height;
            const expandedHeight = await details
              .locator("..")
              .evaluate(
                (candidate) => candidate.getBoundingClientRect().height,
              );
            expect(expandedHeight).toBeGreaterThan(collapsedHeight);
            const artifact = `${evidence}-geometry.json`;
            const captured = JSON.parse(fs.readFileSync(artifact, "utf8"));
            captured.disclosureGrowth ??= [];
            captured.disclosureGrowth.push({
              index,
              collapsedHeight,
              expandedHeight,
            });
            fs.writeFileSync(artifact, JSON.stringify(captured, null, 2));
            await details.locator("summary").focus();
            await page.keyboard.press("Enter");
            await expect(details).not.toHaveAttribute("open", "");
            await page.keyboard.press("Enter");
            await expect(details).toHaveAttribute("open", "");
          }
          for (const heading of [
            "Additional provenance",
            "Provider accounting",
            "M4 lifecycle evidence",
          ]) {
            await page.getByText(heading, { exact: true }).focus();
            await page.keyboard.press("Enter");
          }
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
          const expandedFit = await page
            .locator("article")
            .evaluate((article) => {
              const overflowing = Array.from(
                article.querySelectorAll("p, dt, dd, code, summary"),
              )
                .filter((element) => {
                  const rect = element.getBoundingClientRect();
                  return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    (rect.left < 0 ||
                      rect.right > innerWidth ||
                      element.scrollWidth > element.clientWidth)
                  );
                })
                .map((element) => element.textContent);
              return {
                pageWidth: document.documentElement.scrollWidth,
                overflowing,
              };
            });
          expect(expandedFit.pageWidth).toBeLessThanOrEqual(width);
          expect(expandedFit.overflowing).toEqual([]);
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
    test(`archived Conversation collapsed panels retain controls and evidence at ${width}`, async ({
      page,
    }) => {
      const height = width === 1440 ? 960 : 844;
      await page.setViewportSize({ width, height });
      const unexpected = await prepareFixture(page, "128:119");
      const panels = page.locator(".conversation-panels");
      const inspector = page.getByRole("complementary", { name: /evidence/i });
      const history = page
        .getByRole("region", { name: "Conversation workspace" })
        .locator("ol");
      await expect(history).toContainText(
        "How many chapters are in the report?",
      );
      const retainedHistory = await history.textContent();
      if (width === 1440) {
        await page
          .getByRole("button", { name: "Collapse rail", exact: true })
          .click();
        await expect(panels).toHaveAttribute("data-rail", "collapsed");
        await expect(
          page.getByRole("button", { name: "Expand rail", exact: true }),
        ).toBeVisible();
        await expect(
          page.locator(".conversation-rail-column"),
        ).toHaveJSProperty("clientWidth", 72);
      } else {
        await expect(page.locator(".conversation-rail-column")).toHaveCount(0);
        await page
          .getByRole("button", { name: "Open evidence", exact: true })
          .click();
      }
      await expect(inspector).toContainText("Select a citation");
      await expect(inspector).toContainText(
        "Choose a citation in the answer to inspect the exact supporting passage and its source context.",
      );
      const retainedEvidence = await inspector.textContent();
      await page
        .getByRole("button", { name: "Close evidence", exact: true })
        .click();
      await expect(panels).toHaveAttribute("data-inspector", "false");
      await expect(inspector).toHaveCount(0);
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "Open evidence", exact: true }),
      ).toBeVisible();
      await expect(history).toHaveText(retainedHistory!);
      const bar = page.locator('[aria-label="Archived conversation controls"]');
      const button = bar.getByRole("button", {
        name: "Restore conversation",
        exact: true,
      });
      await expect(bar.getByRole("status")).toHaveText(
        "Archived conversation · Read-only",
      );
      await expect(button).toBeEnabled();
      await expect(page.getByLabel("Question", { exact: true })).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "Ask", exact: true }),
      ).toHaveCount(0);
      for (const citation of [1, 2])
        await expect(
          page.getByRole("button", {
            name: new RegExp(`citation ${citation}`, "i"),
          }),
        ).toBeVisible();
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(
          Array.from(document.images).map((img) => img.decode()),
        );
      });
      const geometry = await bar.evaluate((element) => {
        const measure = (node: Element) => {
          const box = node.getBoundingClientRect();
          const css = getComputedStyle(node);
          return {
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            radius: css.borderRadius,
            fontSize: css.fontSize,
            fontWeight: css.fontWeight,
            paddingLeft: css.paddingLeft,
            paddingRight: css.paddingRight,
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
          };
        };
        return {
          panel: measure(element.closest("section")!),
          outer: measure(element.parentElement!),
          bar: measure(element),
          label: measure(element.querySelector('[role="status"]')!),
          button: measure(element.querySelector("button")!),
          assets: Array.from(document.images).map((img) => ({
            src: img.getAttribute("src"),
            complete: img.complete,
            naturalWidth: img.naturalWidth,
            ...measure(img),
          })),
          noHorizontalOverflow:
            document.documentElement.scrollWidth <= innerWidth,
        };
      });
      expect(geometry.bar.width).toBe(
        geometry.panel.width - (width === 1440 ? 48 : 32),
      );
      expect(geometry.outer.width).toBe(geometry.panel.width);
      expect(geometry.bar.radius).toBe("10px");
      expect(geometry.bar.paddingLeft).toBe("14px");
      expect(geometry.bar.paddingRight).toBe("8px");
      expect(geometry.label.fontSize).toBe("13px");
      expect(geometry.label.fontWeight).toBe("400");
      expect(geometry.button.width).toBe(151);
      expect(geometry.button.height).toBe(34);
      expect(geometry.button.radius).toBe("8px");
      expect(geometry.button.fontSize).toBe("13px");
      expect(geometry.button.fontWeight).toBe("600");
      for (const control of [geometry.label, geometry.button])
        expect(control.scrollWidth).toBeLessThanOrEqual(control.clientWidth);
      expect(geometry.noHorizontalOverflow).toBe(true);
      expect(geometry.outer.y + geometry.outer.height).toBeLessThanOrEqual(
        height,
      );
      if (width === 1440) {
        expect(geometry.panel.width).toBe(1360);
        expect(geometry.bar.width).toBe(1312);
        expect(geometry.outer.height).toBe(72);
        expect(geometry.bar.height).toBe(48);
      } else {
        expect(geometry.bar.height).toBeGreaterThanOrEqual(48);
      }
      await button.focus();
      await page.keyboard.press("Shift+Tab");
      await expect(button).not.toBeFocused();
      await page.keyboard.press("Tab");
      await expect(button).toBeFocused();
      const evidence = `../.superpowers/figma/q1/evidence/archived-conversation-bar-2026-10-08/collapsed-128-119-${width}`;
      writeLookupGeometry(evidence, {
        source: "128:119",
        composition: "collapsed",
        viewport: { width, height },
        rail: await panels.getAttribute("data-rail"),
        inspectorOpen: await panels.getAttribute("data-inspector"),
        retainedHistory,
        retainedEvidence,
        geometry,
      });
      await page.screenshot({
        path: `${evidence}.png`,
        animations: "disabled",
      });
      // Read-only fixture controls must not invoke restore or question endpoints.
      expect(unexpected).toEqual([]);
    });
    test(`archived Conversation bar uses source controls and preserves history at ${width}`, async ({
      page,
    }) => {
      const height = width === 1440 ? 960 : 844;
      await page.setViewportSize({ width, height });
      const unexpected = await prepareFixture(page, "128:119");
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(
          Array.from(document.images).map((img) => img.decode()),
        );
      });
      const button = page.getByRole("button", {
        name: "Restore conversation",
        exact: true,
      });
      const bar = button.locator("..");
      const label = bar.getByRole("status");
      const outer = bar.locator("..");
      const geometry = await bar.evaluate((element) => {
        const control = element.querySelector("button")!;
        const controlStyle = getComputedStyle(control);
        const measure = document.createElement("canvas").getContext("2d")!;
        measure.font = `${controlStyle.fontWeight} ${controlStyle.fontSize} ${controlStyle.fontFamily}`;
        const bounds = (node: Element) => {
          const box = node.getBoundingClientRect();
          const css = getComputedStyle(node);
          return {
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            minHeight: css.minHeight,
            radius: css.borderRadius,
            paddingLeft: css.paddingLeft,
            paddingRight: css.paddingRight,
            fontSize: css.fontSize,
            fontWeight: css.fontWeight,
            fontFamily: css.fontFamily,
            lineHeight: css.lineHeight,
            margin: css.margin,
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
          };
        };
        return {
          outer: bounds(element.parentElement!),
          bar: bounds(element),
          label: bounds(element.querySelector('[role="status"]')!),
          button: bounds(element.querySelector("button")!),
          buttonTextWidth: measure.measureText(control.textContent!).width,
          fontLoaded: document.fonts.check(`600 13px inter`),
          fontFaces: Array.from(document.fonts).map((font) => ({
            family: font.family,
            status: font.status,
            weight: font.weight,
          })),
          copy: element.textContent,
          assets: Array.from(document.querySelectorAll("img")).map((img) => ({
            src: img.getAttribute("src"),
            complete: img.complete,
            naturalWidth: img.naturalWidth,
            ...bounds(img),
          })),
          history: Array.from(document.querySelectorAll("ol > li")).map(
            (turn) => turn.textContent,
          ),
          evidence: document.querySelector('[aria-label="Evidence Inspector"]')
            ?.textContent,
          noHorizontalOverflow:
            document.documentElement.scrollWidth <= innerWidth,
        };
      });
      const evidence = `../.superpowers/figma/q1/evidence/archived-conversation-bar-2026-10-08/implemented-128-119-${width}`;
      writeLookupGeometry(evidence, {
        source: "128:119",
        viewport: { width, height },
        geometry,
      });
      await page.screenshot({
        path: `${evidence}.png`,
        animations: "disabled",
      });
      await expect(label).toHaveText("Archived conversation · Read-only");
      await expect(bar).toHaveAttribute(
        "aria-label",
        "Archived conversation controls",
      );
      await expect(page.getByLabel("Question", { exact: true })).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "Ask", exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByText("How many chapters are in the report?", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText(
          "The reporting guideline explicitly defines a seven-chapter structure. The chapter list and ordering are specified in the report-structure section of the indexed document.",
          { exact: true },
        ),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: /citation 1/i }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: /citation 2/i }),
      ).toBeVisible();
      expect(geometry.bar.minHeight).toBe("48px");
      expect(geometry.outer.minHeight).toBe("72px");
      expect(geometry.bar.radius).toBe("10px");
      expect(geometry.bar.paddingLeft).toBe("14px");
      expect(geometry.bar.paddingRight).toBe("8px");
      expect(geometry.label.fontSize).toBe("13px");
      expect(geometry.label.fontWeight).toBe("400");
      expect(geometry.label.margin).toBe("0px");
      expect(geometry.button.width).toBe(151);
      expect(geometry.button.height).toBe(34);
      expect(geometry.button.radius).toBe("8px");
      expect(geometry.button.fontSize).toBe("13px");
      expect(geometry.button.fontWeight).toBe("600");
      expect(geometry.button.lineHeight).toBe("16px");
      expect(geometry.fontLoaded).toBe(true);
      expect(
        geometry.assets.every(
          (asset) => asset.complete && asset.naturalWidth > 0,
        ),
      ).toBe(true);
      expect(geometry.noHorizontalOverflow).toBe(true);
      expect(geometry.label.scrollWidth).toBeLessThanOrEqual(
        geometry.label.clientWidth,
      );
      expect(geometry.button.scrollWidth).toBeLessThanOrEqual(
        geometry.button.clientWidth,
      );
      expect(geometry.outer.y + geometry.outer.height).toBeLessThanOrEqual(
        height,
      );
      if (width === 1440) {
        expect(geometry.outer.height).toBe(72);
        expect(geometry.bar.height).toBe(48);
        expect(geometry.bar.width).toBe(geometry.outer.width - 48);
      } else {
        expect(geometry.bar.height).toBeGreaterThanOrEqual(48);
        expect(geometry.bar.width).toBe(geometry.outer.width - 32);
      }
      await expect(button).toBeEnabled();
      await button.focus();
      await page.keyboard.press("Shift+Tab");
      await expect(button).not.toBeFocused();
      await page.keyboard.press("Tab");
      await expect(button).toBeFocused();
      // Restore is intentionally not invoked: fixture admission rejects this mutation.
      expect(unexpected).toEqual([]);
      await expect(outer).toBeVisible();
    });
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

  test("Evaluation unavailable badge matches source tone and desktop position", async ({
    page,
  }) => {
    await prepareFixture(page, "216:755");
    const badge = page.locator("#evaluation-heading + .kn-status-badge");
    const measured = await badge.evaluate((element) => {
      const box = element.getBoundingClientRect();
      const heading = element.previousElementSibling!.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        color: style.color,
        background: style.backgroundColor,
        radius: style.borderRadius,
        width: box.width,
        height: box.height,
        left: box.left - heading.left,
        top: box.top - heading.top,
      };
    });
    expect(measured).toEqual({
      color: "rgb(120, 65, 49)",
      background: "rgb(242, 228, 223)",
      radius: "8px",
      width: 92,
      height: 28,
      left: 383,
      top: 3,
    });
    await expect(badge.locator("span:last-child")).toHaveText("Unavailable");
    await expect(badge.locator('[aria-hidden="true"]')).toBeHidden();
  });

  test("Workspace selector options retain borderless source rows and keyboard focus", async ({
    page,
  }) => {
    await prepareFixture(page, "140:104");
    const popup = page.getByRole("region", { name: "Switch workspace" });
    const options = popup.locator(".workspace-selector-options > button");
    await expect(options).toHaveCount(3);
    const rows = await options.evaluateAll((buttons) =>
      buttons.map((button) => {
        const style = getComputedStyle(button);
        return {
          border: style.borderTopWidth,
          margin: style.margin,
          height: button.getBoundingClientRect().height,
          lineHeight: style.lineHeight,
          weight: style.fontWeight,
        };
      }),
    );
    for (const [index, row] of rows.entries()) {
      expect(row.border).toBe("0px");
      expect(row.margin).toBe("0px");
      expect(row.height).toBe(40);
      expect(row.lineHeight).toBe("16px");
      expect(row.weight).toBe(index === 0 ? "600" : "500");
    }
    expect(
      await options
        .nth(1)
        .evaluate(
          (button) =>
            button.getBoundingClientRect().top -
            button.previousElementSibling!.getBoundingClientRect().bottom,
        ),
    ).toBe(2);
    const create = popup.getByRole("button", { name: "+ Create workspace" });
    expect(
      await create.evaluate((button) => ({
        border: getComputedStyle(button).borderTopWidth,
        margin: getComputedStyle(button).margin,
        height: button.getBoundingClientRect().height,
      })),
    ).toEqual({ border: "0px", margin: "0px", height: 40 });
    await options.first().focus();
    await page.keyboard.press("ArrowDown");
    await expect(options.nth(1)).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", {
        name: "Switch workspace: Research workspace",
        exact: true,
      }),
    ).toBeFocused();
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

  test("native FTL reset presentation uses source labels and preserves accessible controls", async ({
    page,
  }) => {
    const evidence =
      "../.superpowers/figma/q1/evidence/otp-input-presentation-2026-10-08";
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
      for (const state of ["242:389", "242:272", "242:333", "246:311"]) {
        await page.route("**/native/blocked-action", (route) => route.abort());
        const unexpected = await prepareFixture(page, state);
        const password = state === "242:389";
        const request = state === "242:272";
        await expect(
          page.getByRole("heading", {
            name: request
              ? "Forgot your password?"
              : password
                ? "Choose a new password"
                : "Enter verification code",
            exact: true,
          }),
        ).toBeVisible();
        if (request) {
          await expect(page.locator(".knora-auth-description")).toHaveText(
            "Enter the email for your account. If an account exists, we’ll send a 6-digit verification code.",
          );
          await expect(
            page.getByRole("button", {
              name: "Send verification code",
              exact: true,
            }),
          ).toBeVisible();
          await expect(page.locator(".knora-secondary")).toContainText(
            "Remembered it?",
          );
          await expect(page.locator(".knora-disclaimer")).toHaveText(
            "For privacy, Knora won’t confirm whether an account exists for this email.",
          );
          await expect(page.locator("#email")).toHaveAttribute(
            "autocomplete",
            "email",
          );
        } else if (password) {
          await expect(page.locator(".knora-auth-description")).toHaveText(
            "Set a new password for your Knora account.",
          );
          await expect(
            page.getByLabel("Confirm new password", { exact: true }),
          ).toHaveAttribute("id", "password-confirm");
          await expect(
            page.getByRole("button", { name: "Reset password", exact: true }),
          ).toBeVisible();
          await expect(
            page.locator(".knora-auth .knora-disclaimer"),
          ).toHaveText(
            "After resetting your password, sign in again with the new password.",
          );
          await expect(
            page.locator('input[name="logout-sessions"]'),
          ).toHaveCount(1);
          for (const id of ["password-new", "password-confirm"]) {
            const input = page.locator(`#${id}`);
            await expect(input).toHaveAttribute("autocomplete", "new-password");
            await expect(input).toHaveValue("");
            await page.locator(`#${id}-show-password`).click();
            await expect(input).toHaveAttribute("type", "text");
            await page.locator(`#${id}-show-password`).click();
            await expect(input).toHaveAttribute("type", "password");
          }
        } else {
          await expect(page.locator(".knora-auth-description")).toHaveText(
            "If an account exists, we sent a 6-digit verification code to n***@example.test.",
          );
          await expect(
            page.getByRole("button", {
              name: "Use a different email",
              exact: true,
            }),
          ).toBeVisible();
          await expect(page.locator("#code")).toHaveValue("");
          await expect(page.locator("#code")).toHaveAttribute(
            "autocomplete",
            "one-time-code",
          );
          await expect(page.locator(".knora-otp-cells span")).toHaveCount(6);
          await expect(page.locator("#otp-retry")).toHaveText("00:30");
          await expect(page.locator("#otp-resend-label")).toHaveText(
            "Resend code in",
          );
          await expect(page.locator("#otp-expiry")).toHaveText(
            "The code expires after 5 minutes.",
          );
          if (state === "246:311")
            await expect(page.getByRole("alert")).toContainText(
              "Check the code or request a new one, then try again.",
            );
        }
        await expect(page.locator(".knora-auth form")).toHaveAttribute(
          "method",
          "post",
        );
        await expect(page.locator(".knora-auth form")).toHaveAttribute(
          "action",
          "/native/blocked-action",
        );
        await expect
          .poll(() =>
            page
              .locator(".knora-brand img")
              .evaluate(
                (element) =>
                  (element as HTMLImageElement).complete &&
                  (element as HTMLImageElement).naturalWidth > 0,
              ),
          )
          .toBe(true);
        expect(
          await page.locator(".knora-brand img").boundingBox(),
        ).toMatchObject({ width: 18, height: 18 });
        for (const eye of await page
          .locator('[id$="-show-password"] i')
          .all()) {
          expect(await eye.boundingBox()).toMatchObject({
            width: 18,
            height: 18,
          });
          expect(
            await eye.evaluate(
              (element) => getComputedStyle(element).backgroundImage,
            ),
          ).toContain("42cef.svg");
        }
        const geometry = await page.evaluate(() => {
          const measure = (element: Element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return {
              tag: element.tagName,
              id: element.id,
              text: element.textContent?.trim(),
              x: rect.x,
              y: rect.y,
              width: rect.width,
              height: rect.height,
              fits: element.scrollWidth <= element.clientWidth,
              fontSize: style.fontSize,
              lineHeight: style.lineHeight,
              radius: style.borderRadius,
              color: style.color,
              background: style.backgroundColor,
            };
          };
          return {
            viewport: { width: innerWidth, height: innerHeight },
            pageFits: document.documentElement.scrollWidth <= innerWidth,
            regions: Array.from(
              document.querySelectorAll(
                "#kc-page-title, .knora-auth, .knora-auth-description, .knora-auth label, .knora-auth input, .knora-auth button, .knora-secondary, .knora-disclaimer, .knora-notice, .knora-brand img, [id$='-show-password'] i",
              ),
            ).map(measure),
            inputValues: Array.from(
              document.querySelectorAll<HTMLInputElement>(
                "#code, #password-new, #password-confirm",
              ),
            ).map((input) => ({ id: input.id, empty: input.value === "" })),
          };
        });
        expect(geometry.pageFits).toBe(true);
        expect(geometry.inputValues.every((input) => input.empty)).toBe(true);
        const target = `${evidence}/implemented-${state.replace(":", "-")}-${width}`;
        writeLookupGeometry(target, geometry);
        await page.screenshot({
          path: `${target}.png`,
          fullPage: true,
          animations: "disabled",
        });
        expect(unexpected).toEqual([]);
      }
    }
  });

  test("native FTL OTP allocation and empty marks preserve one native input", async ({
    page,
    context,
  }) => {
    const evidence =
      "../.superpowers/figma/q1/evidence/otp-input-presentation-2026-10-08";
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
      for (const state of ["242:333", "246:311"]) {
        await page.route("**/native/blocked-action", (route) => route.abort());
        const unexpected = await prepareFixture(page, state);
        const input = page.getByRole("textbox", {
          name: "Six-digit reset code",
        });
        await expect(input).toHaveCount(1);
        await expect(input).toHaveValue("");
        for (const [attribute, value] of Object.entries({
          name: "code",
          type: "text",
          inputmode: "numeric",
          pattern: "[0-9]{6}",
          minlength: "6",
          maxlength: "6",
          autocomplete: "one-time-code",
          required: "",
          "aria-invalid": state === "246:311" ? "true" : "false",
          "aria-describedby":
            state === "246:311" ? "otp-error otp-expiry" : "otp-expiry",
        })) {
          await expect(input).toHaveAttribute(attribute, value);
        }
        await expect(page.locator(".knora-otp-cells")).toHaveAttribute(
          "aria-hidden",
          "true",
        );
        await expect(page.locator(".knora-otp-cells span")).toHaveCount(6);
        await expect(page.locator("form")).toHaveAttribute("method", "post");
        await expect(page.locator("form")).toHaveAttribute(
          "action",
          "/native/blocked-action",
        );
        const geometry = await page
          .locator(".knora-otp-entry")
          .evaluate((entry) => {
            const box = (element: Element) => {
              const rect = element.getBoundingClientRect();
              return {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
              };
            };
            const cells = Array.from(entry.querySelectorAll("span"));
            const grid = entry.querySelector(".knora-otp-cells")!;
            const input = entry.querySelector("input")!;
            const style = getComputedStyle(grid);
            const brand =
              document.querySelector<HTMLImageElement>(".knora-brand img")!;
            return {
              viewport: { width: innerWidth, height: innerHeight },
              wrapper: box(entry),
              form: box(entry.closest("form")!),
              input: box(input),
              cells: cells.map((cell) => ({
                ...box(cell),
                text: cell.textContent,
                mark: getComputedStyle(cell, "::before").content,
                markColor: getComputedStyle(cell, "::before").color,
                fontSize: getComputedStyle(cell).fontSize,
                fontWeight: getComputedStyle(cell).fontWeight,
              })),
              gridColumns: style.gridTemplateColumns,
              gap: style.columnGap,
              pointerEvents: style.pointerEvents,
              mutedColor: getComputedStyle(
                document.querySelector(".knora-auth-description")!,
              ).color,
              pageFits: document.documentElement.scrollWidth <= innerWidth,
              brand: {
                ...box(brand),
                loaded: brand.complete && brand.naturalWidth > 0,
                src: brand.getAttribute("src"),
              },
            };
          });
        const target = `${evidence}/otp-empty-${state.replace(":", "-")}-${width}`;
        writeLookupGeometry(target, geometry);
        await page.screenshot({
          path: `${target}.png`,
          fullPage: true,
          animations: "disabled",
        });
        expect
          .soft(geometry.wrapper.width)
          .toBe(width === 1440 ? 420 : geometry.form.width);
        expect(geometry.wrapper.height).toBe(56);
        expect(geometry.input.height).toBe(56);
        expect(geometry.input.width).toBe(geometry.wrapper.width);
        expect(geometry.gap).toBe("10px");
        expect(geometry.pointerEvents).toBe("none");
        expect(geometry.pageFits).toBe(true);
        expect(geometry.brand).toMatchObject({
          width: 18,
          height: 18,
          loaded: true,
          src: "/resources/images/ad252.svg",
        });
        for (const [index, cell] of geometry.cells.entries()) {
          expect(cell.height).toBe(56);
          expect(cell.fontSize).toBe("22px");
          expect(cell.fontWeight).toBe("600");
          expect.soft(cell.mark).toBe('"—"');
          expect.soft(cell.markColor).toBe(geometry.mutedColor);
          expect(cell.text).toBe("");
          if (width === 1440) {
            expect(cell.width).toBe(54);
            expect.soft(cell.x - geometry.wrapper.x).toBe(23 + index * 64);
          } else {
            expect(cell.width).toBeGreaterThan(0);
            expect(cell.width).toBeLessThan(54);
            expect(cell.x).toBeGreaterThanOrEqual(geometry.wrapper.x);
            expect(cell.x + cell.width).toBeLessThanOrEqual(
              geometry.wrapper.x + geometry.wrapper.width + 0.1,
            );
          }
          if (index > 0)
            expect(
              cell.x -
                (geometry.cells[index - 1].x + geometry.cells[index - 1].width),
            ).toBeCloseTo(10, 1);
        }
        await page.evaluate(() => navigator.clipboard.writeText("000042"));
        await input.focus();
        await expect(input).toBeFocused();
        await input.press("Control+V");
        await expect(input).toHaveValue("000042");
        await expect(page.locator(".knora-otp-cells")).toHaveText("000042");
        const pasted = await page
          .locator(".knora-otp-entry")
          .evaluate((entry) => ({
            value: entry.querySelector<HTMLInputElement>("input")!.value,
            cells: Array.from(entry.querySelectorAll("span")).map((cell) => ({
              text: cell.textContent,
              mark: getComputedStyle(cell, "::before").content,
            })),
          }));
        expect(pasted.cells.map((cell) => cell.mark)).toEqual(
          Array(6).fill("none"),
        );
        await input.fill("");
        await expect(input).toHaveValue("");
        await expect(page.locator(".knora-otp-cells")).toHaveText("");
        const cleared = await page
          .locator(".knora-otp-entry")
          .evaluate((entry) => ({
            value: entry.querySelector<HTMLInputElement>("input")!.value,
            cells: Array.from(entry.querySelectorAll("span")).map((cell) => ({
              text: cell.textContent,
              mark: getComputedStyle(cell, "::before").content,
            })),
          }));
        expect
          .soft(cleared.cells.map((cell) => cell.mark))
          .toEqual(Array(6).fill('"—"'));
        writeLookupGeometry(target, {
          ...geometry,
          inputTransitions: { pasted, cleared },
        });
        expect(unexpected).toEqual([]);
      }
    }
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
    await expect(page.locator("#otp-retry")).toHaveText("00:30");
    await expect(page.locator("#otp-resend-label")).toHaveText(
      "Resend code in",
    );
    await expect(page.locator("#otp-retry")).toHaveAttribute(
      "data-seconds",
      "30",
    );
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
    await expect(page.locator("#otp-retry")).toHaveText("00:01");
    await page.clock.setFixedTime(new Date(now.getTime() + 30_000));
    await page.clock.runFor(250);
    await expect(resend).toBeEnabled();
    await expect(page.locator("#otp-retry")).toHaveCount(0);
    await expect(resend).toHaveText("Resend code");
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
      await expect(page.locator("#otp-retry")).toHaveText("00:30");
      await expect(page.locator("#otp-resend-label")).toHaveText(
        "Resend code in",
      );
      await expect(page.locator("form")).toHaveAttribute("method", "post");
      await expect(page.locator("form")).toHaveAttribute(
        "action",
        "/native/blocked-action",
      );
      await input.fill("");
      await page.screenshot({
        path: "../.superpowers/figma/q1/evidence/otp-input-presentation-2026-10-08/otp-resend-no-js-enabled.png",
        animations: "disabled",
      });
    } finally {
      await context.close();
    }
  });

  test("small text on signature notices meets contrast in both themes", async ({
    page,
  }) => {
    for (const [state, selector] of [
      [
        "128:111",
        'aside[aria-label="Evidence Inspector"] blockquote > p:first-child',
      ],
      [
        "128:118",
        'aside[aria-label="Evidence Inspector"] blockquote > p:first-child',
      ],
      [
        "128:131",
        'section[aria-label="Deletion request"] > div > p:nth-child(2)',
      ],
    ]) {
      await prepareFixture(page, state);
      for (const theme of ["light", "dark"]) {
        await page.evaluate((value) => {
          document.documentElement.dataset.theme = value;
        }, theme);
        const ratio = await page.locator(selector).evaluate((label) => {
          const canvas = document.createElement("canvas");
          canvas.width = canvas.height = 1;
          const context = canvas.getContext("2d")!;
          const pixel = (color: string) => {
            context.clearRect(0, 0, 1, 1);
            context.fillStyle = color;
            context.fillRect(0, 0, 1, 1);
            return Array.from(context.getImageData(0, 0, 1, 1).data);
          };
          const layers = [];
          for (
            let node: Element | null = label;
            node;
            node = node.parentElement
          ) {
            layers.push(pixel(getComputedStyle(node).backgroundColor));
          }
          let background = [255, 255, 255];
          for (const layer of layers.reverse()) {
            const alpha = layer[3] / 255;
            background = background.map(
              (value, index) => layer[index] * alpha + value * (1 - alpha),
            );
          }
          const luminance = (rgb: number[]) => {
            const linear = rgb.slice(0, 3).map((value) => {
              const channel = value / 255;
              return channel <= 0.04045
                ? channel / 12.92
                : ((channel + 0.055) / 1.055) ** 2.4;
            });
            return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
          };
          const values = [
            luminance(pixel(getComputedStyle(label).color)),
            luminance(background),
          ].sort((a, b) => b - a);
          return (values[0] + 0.05) / (values[1] + 0.05);
        });
        expect(ratio, `${state} ${theme} notice text`).toBeGreaterThanOrEqual(
          4.5,
        );
      }
      await page.unrouteAll();
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
          ["--text-muted", "--surface-subtle"],
          ["--text-muted", "--page"],
          ["--action-text", "--page"],
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
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
      const unexpected = await prepareFixture(page, "128:109");
      const question = page.getByLabel("Question", { exact: true });
      await question.click();
      await expect(question).toBeFocused();
      await expect(question).toHaveValue("");
      await expect(
        page.getByRole("button", { name: "Ask", exact: true }),
      ).toBeDisabled();
      const focusEvidence =
        "../.superpowers/figma/q1/evidence/composer-focus-2026-10-10";
      fs.mkdirSync(focusEvidence, { recursive: true });
      await page.screenshot({ path: `${focusEvidence}/${width}.png` });
      const scroll = page.locator(".conversation-scroll");
      expect(
        await scroll.evaluate((area) => area.scrollWidth <= area.clientWidth),
      ).toBe(true);
      if (width === 390)
        await page.getByRole("button", { name: "Open evidence" }).click();
      const title = page.getByRole("heading", {
        name: "Evidence will appear here",
      });
      const typography = await title.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
          fontFamily: style.fontFamily.toLowerCase(),
          fontSize: style.fontSize,
          lineHeight: style.lineHeight,
        };
      });
      expect.soft(typography.fontFamily).toContain("inter");
      expect.soft(typography.fontSize).toBe("14px");
      expect.soft(typography.lineHeight).toBe("20px");
      if (width === 390) await page.keyboard.press("Escape");
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
        page.getByText("Archived conversation · Read-only"),
      ).toBeVisible();
      await expect(page.getByLabel("Question", { exact: true })).toHaveCount(0);
      await page.unrouteAll();
    }
  });
});

test.describe("guarded application journeys", () => {
  test.skip(
    process.env.FIGMA_TEST_MODE !== "application",
    "Dedicated guarded application project required.",
  );
  for (const viewport of [
    { width: 1440, height: 960 },
    { width: 800, height: 844 },
    { width: 801, height: 844 },
    { width: 390, height: 844 },
  ]) {
    test(`live account logout and forced sign-in at ${viewport.width}`, async ({
      page,
      context,
    }) => {
      await page.setViewportSize(viewport);
      const evidence =
        "../.superpowers/figma/q1/evidence/live-logout-prompt-2026-10-08";
      fs.mkdirSync(evidence, { recursive: true });
      const identity = realm.users.find((user) => user.username === "m5-user");
      if (!identity) throw new Error("Owned synthetic identity missing.");
      const businessWrites: { method: string; pathname: string }[] = [];
      context.on("request", (request) => {
        const pathname = new URL(request.url()).pathname;
        if (pathname.startsWith("/api/v1/") && request.method() !== "GET")
          businessWrites.push({ method: request.method(), pathname });
      });
      const applicationOrigin = "http://127.0.0.1:3300";
      const keycloakOrigin = "http://127.0.0.1:8380";
      const authorizationPath =
        "/realms/knora-dev/protocol/openid-connect/auth";
      const logoutPath = "/realms/knora-dev/protocol/openid-connect/logout";
      const readTransaction = () => {
        const authorization = new URL(page.url());
        // Only boolean checks may expose comparisons of native auth values.
        expect(authorization.origin === keycloakOrigin).toBe(true);
        expect(authorization.pathname === authorizationPath).toBe(true);
        expect(
          authorization.searchParams.get("redirect_uri") ===
            `${applicationOrigin}/api/auth/callback`,
        ).toBe(true);
        const transaction = {
          state: authorization.searchParams.get("state"),
          nonce: authorization.searchParams.get("nonce"),
          codeChallenge: authorization.searchParams.get("code_challenge"),
        };
        expect(
          Object.values(transaction).every((value) => Boolean(value)),
        ).toBe(true);
        return transaction;
      };
      const completeNativeLogin = async (reauthentication = false) => {
        if (reauthentication) {
          await expect(page.locator("#username")).toHaveCount(0);
          expect(
            (await page.locator("#kc-attempted-username").inputValue()) ===
              identity.username,
          ).toBe(true);
          await expect(page.locator("#kc-attempted-username")).toHaveAttribute(
            "readonly",
            "",
          );
        } else {
          await page.locator("#username").fill(identity.username);
        }
        const callback = page.waitForResponse(
          (response) =>
            new URL(response.url()).origin === applicationOrigin &&
            new URL(response.url()).pathname === "/api/auth/callback",
        );
        await page.locator("#password").fill(identity.credentials[0].value);
        await page.locator("#kc-login").click();
        const callbackStatus = (await callback).status();
        expect(callbackStatus).toBe(307);
        await page.waitForURL(
          (url) =>
            url.origin === applicationOrigin &&
            /^\/workspaces(?:\/[^?]+)?$/.test(url.pathname),
        );
        return callbackStatus;
      };
      const readSafeSession = async () => {
        const response = await page.request.get("/api/auth/session");
        expect(response.status()).toBe(200);
        const body = (await response.json()) as {
          session: {
            subject: string;
            capabilities: string[];
            workspaceIds: string[];
          } | null;
        };
        expect(body.session !== null).toBe(true);
        const session = body.session!;
        expect(
          typeof session.subject === "string" && session.subject.length > 0,
        ).toBe(true);
        expect(Array.isArray(session.capabilities)).toBe(true);
        expect(
          Object.keys(session).sort().join(",") ===
            "capabilities,subject,workspaceIds",
        ).toBe(true);
        return session;
      };

      await openFigmaLogin(page);
      const normalTransaction = readTransaction();
      const normalCallbackStatus = await completeNativeLogin();
      const normalSession = await readSafeSession();

      await page.goto(
        "/api/auth/login?prompt=login&returnTo=https://untrusted.example",
      );
      await expect(page.locator("#kc-form-login")).toBeVisible();
      await expect(page.locator("#password")).toBeVisible();
      expect((await page.locator("#password").inputValue()).length === 0).toBe(
        true,
      );
      const forcedTransaction = readTransaction();
      const forcedAuthorization = new URL(page.url());
      expect(forcedAuthorization.searchParams.get("prompt") === "login").toBe(
        true,
      );
      expect(!forcedAuthorization.searchParams.has("returnTo")).toBe(true);
      expect(
        !forcedAuthorization.toString().includes("untrusted.example"),
      ).toBe(true);
      const freshTransaction = {
        state: forcedTransaction.state !== normalTransaction.state,
        nonce: forcedTransaction.nonce !== normalTransaction.nonce,
        codeChallenge:
          forcedTransaction.codeChallenge !== normalTransaction.codeChallenge,
      };
      expect(Object.values(freshTransaction).every(Boolean)).toBe(true);
      const forcedNativeHorizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      expect(forcedNativeHorizontalOverflow).toBe(false);
      const restartTooltip = page.locator("#reset-login .kc-tooltip-text");
      await page.locator("#reset-login").hover();
      await expect(restartTooltip).toBeVisible();
      const tooltipGeometry = await restartTooltip.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const arrow = getComputedStyle(element, "::after");
        return {
          fitsViewport: rect.left >= 0 && rect.right <= innerWidth,
          arrowTop: arrow.top,
          arrowBottomColor: arrow.borderBottomColor,
          tooltipTop: style.top,
        };
      });
      if (viewport.width <= 800) {
        expect(tooltipGeometry).toEqual({
          fitsViewport: true,
          arrowTop: "-10px",
          arrowBottomColor: "rgb(0, 0, 0)",
          tooltipTop: "36px",
        });
      } else {
        expect(tooltipGeometry.fitsViewport).toBe(true);
      }
      await captureIdentity(
        page,
        `${evidence}/forced-sign-in-${viewport.width}.png`,
      );
      const forcedCallbackStatus = await completeNativeLogin(true);
      const forcedSession = await readSafeSession();
      expect(forcedSession.subject === normalSession.subject).toBe(true);

      await page.evaluate(() => {
        sessionStorage.setItem(
          "knora:conversation-panels:v1:test-scope",
          "test",
        );
        sessionStorage.setItem("unrelated-preference", "retained");
      });
      await page
        .getByRole("button", {
          name: `Account: ${forcedSession.subject}`,
          exact: true,
        })
        .click();
      await expect(page.getByText("Signed in", { exact: true })).toBeVisible();
      const logout = page.getByRole("menuitem", {
        name: "Log out",
        exact: true,
      });
      await expect(logout).toBeVisible();
      await captureIdentity(
        page,
        `${evidence}/account-menu-${viewport.width}.png`,
      );
      const logoutResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).origin === applicationOrigin &&
          new URL(response.url()).pathname === "/api/auth/logout",
      );
      await logout.focus();
      await logout.press("Enter");
      const logoutStatus = (await logoutResponse).status();
      expect(logoutStatus).toBe(303);
      await page.waitForURL(
        (url) => url.origin === keycloakOrigin && url.pathname === logoutPath,
      );
      // Keycloak may require its native SSO termination confirmation.
      const confirmation = page.locator("#kc-logout");
      const nativeConfirmationShown = await confirmation.isVisible();
      if (nativeConfirmationShown) await confirmation.click();
      await page.waitForURL((url) => url.origin === applicationOrigin);
      await expect(
        page.getByRole("heading", { name: "Signed out", exact: true }),
      ).toBeVisible();
      const signIn = page.getByRole("link", { name: "Sign in", exact: true });
      await expect(signIn).toBeVisible();
      const preferences = await page.evaluate(() => ({
        scopedRemoved:
          sessionStorage.getItem("knora:conversation-panels:v1:test-scope") ===
          null,
        unrelatedRetained:
          sessionStorage.getItem("unrelated-preference") === "retained",
      }));
      expect(preferences.scopedRemoved).toBe(true);
      expect(preferences.unrelatedRetained).toBe(true);
      const signedOutSession = await page.request.get("/api/auth/session");
      expect(signedOutSession.status()).toBe(200);
      expect((await signedOutSession.json()).session === null).toBe(true);
      const protectedRead = await page.request.get("/api/v1/workspaces");
      expect(protectedRead.status()).toBe(401);
      await signIn.click();
      await expect(page.locator("#kc-form-login")).toBeVisible();
      await expect(page.locator("#password")).toBeVisible();
      const freshAuthorization = new URL(page.url());
      expect(freshAuthorization.origin === keycloakOrigin).toBe(true);
      expect(freshAuthorization.pathname === authorizationPath).toBe(true);
      expect(!freshAuthorization.searchParams.has("prompt")).toBe(true);
      expect((await page.locator("#password").inputValue()).length === 0).toBe(
        true,
      );
      await captureIdentity(
        page,
        `${evidence}/fresh-sign-in-${viewport.width}.png`,
      );
      expect(businessWrites).toHaveLength(0);
      fs.writeFileSync(
        `${evidence}/journey-${viewport.width}.json`,
        JSON.stringify(
          {
            viewport,
            authorizationPath,
            callbackPath: "/api/auth/callback",
            normalCallbackStatus,
            forcedCallbackStatus,
            forcedNativeFormShown: true,
            forcedNativeUsernameLocked: true,
            forcedNativeHorizontalOverflow,
            promptLoginPreserved: true,
            untrustedReturnAbsent: true,
            fixedCallback: true,
            freshTransaction,
            safeSessionProjection: true,
            sameSubject: true,
            logoutStatus,
            logoutPath,
            nativeConfirmationShown,
            signedOutHeadingShown: true,
            preferences,
            signedOutSessionStatus: signedOutSession.status(),
            sessionNull: true,
            protectedReadStatus: protectedRead.status(),
            freshNativePasswordFormShown: true,
            businessWrites,
            naturalExpiryProved: false,
            resetCompletionProved: false,
          },
          null,
          2,
        ),
      );
    });
  }
  test("owned Workspace restores from the Conversation bottom bar while an archived Conversation stays archived", async ({
    page,
  }) => {
    const evidence =
      "../.superpowers/figma/q1/evidence/conversation-creation-2026-10-08";
    fs.mkdirSync(evidence, { recursive: true });
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
    const creationJourneys: {
      source: "draft" | "archived";
      status: number;
      destinationVerified: boolean;
    }[] = [];
    const createThroughButton = async (source: "draft" | "archived") => {
      const previousPath = new URL(page.url()).pathname;
      const responsePromise = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname === `/api/v1${base}/conversations`,
      );
      await page
        .getByRole("button", { name: "New Conversation", exact: true })
        .click();
      const response = await responsePromise;
      expect(response.status()).toBe(201);
      expect(response.request().headers()["idempotency-key"]).toBeTruthy();
      await page.waitForURL(
        (url) =>
          url.pathname.startsWith(`${base}/conversations/`) &&
          url.pathname !== previousPath,
      );
      const destination = new URL(page.url()).pathname;
      const persisted = await page.request.get(`/api/v1${destination}`);
      expect(persisted.status()).toBe(200);
      const conversation = (await persisted.json()) as ConversationResponse;
      expect(conversation.workspace_id).toBe(workspace.id);
      expect(conversation.archived).toBe(false);
      expect(destination).toBe(`${base}/conversations/${conversation.id}`);
      await expect(page.getByLabel("Question", { exact: true })).toHaveValue(
        "",
      );
      creationJourneys.push({
        source,
        status: response.status(),
        destinationVerified: true,
      });
      await captureIdentity(page, `${evidence}/created-from-${source}.png`);
    };
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
    await page
      .getByLabel("Question", { exact: true })
      .fill("Draft not submitted");
    await createThroughButton("draft");
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
    await expect(
      page.getByRole("button", { name: "New Conversation", exact: true }),
    ).toHaveCount(0);
    await captureIdentity(page, `${evidence}/workspace-archived.png`);
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
      page.getByText("Archived conversation · Read-only", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Restore conversation", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("Question", { exact: true })).toHaveCount(0);
    const retained = await page.request.get(
      `/api/v1${base}/conversations/${second.id}`,
    );
    expect((await retained.json()).archived).toBe(true);
    await captureIdentity(page, `${evidence}/conversation-still-archived.png`);
    await createThroughButton("archived");
    const stillArchived = await page.request.get(
      `/api/v1${base}/conversations/${second.id}`,
    );
    expect(stillArchived.status()).toBe(200);
    expect((await stillArchived.json()).archived).toBe(true);
    await page.goto(`${base}/conversations/${active.id}`);
    await expect(page.getByLabel("Question", { exact: true })).toBeVisible();
    await captureIdentity(page, `${evidence}/workspace-restored.png`);
    fs.writeFileSync(
      `${evidence}/journey.json`,
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
          creationJourneys,
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
      page.getByText("Archived conversation · Read-only", { exact: true }),
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
