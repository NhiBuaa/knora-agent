import { expect, test } from "@playwright/test";
import { prepareFixture } from "./support/figma-state-fixtures";
import { randomUUID } from "node:crypto";
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
        const guidance = page.getByRole("region", { name: lookup.heading });
        await expect(guidance).toBeVisible();
        const submit = page.getByRole("button", {
          name: `Open ${lookup.kind}`,
        });
        await expect(submit).toBeDisabled();
        const assets = await page
          .locator(
            'img[src="/brand/knora-leaf.svg"], .workspace-caret-small img',
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
        expect(assets[1].width).toBeCloseTo(6.98995, 1);
        expect(assets[1].height).toBeCloseTo(4.48492, 1);
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
        writeLookupGeometry(evidence, { ...geometry, assets });
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
