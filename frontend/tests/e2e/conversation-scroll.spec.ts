import { expect, test, type Page, type Route } from "@playwright/test";
import type { TurnResponse } from "../../generated/knora-openapi";
import { answered, prepareFixture } from "./support/figma-state-fixtures";

const historyPath = "**/conversations/*/turns?**";
function turns(
  first = 51,
  last = 100,
  conversationId = "fixture-conversation",
): TurnResponse[] {
  return Array.from({ length: last - first + 1 }, (_, index) => {
    const sequence = first + index;
    return {
      ...answered,
      id: `${conversationId}-turn-${sequence}`,
      conversation_id: conversationId,
      sequence,
      question: `Question number ${sequence}`,
      result: {
        ...answered.result!,
        answer: `${"A paragraph of synthetic conversation history.\n\n".repeat(sequence === last ? 55 : 2)}End of answer ${sequence}. [[E1]]`,
      },
    };
  });
}
async function reply(
  route: Route,
  items: TurnResponse[],
  next_cursor: string | null = null,
) {
  await route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ items, next_cursor }),
  });
}
async function atLatest(page: Page, sequence = 100) {
  await expect(
    page.getByText(`End of answer ${sequence}.`, { exact: false }).last(),
  ).toBeAttached();
  await expect
    .poll(() =>
      page.locator(".conversation-scroll").evaluate((element) => {
        const last = element.querySelector("ol > li:last-child")!;
        const viewport = element.getBoundingClientRect();
        const message = last.getBoundingClientRect();
        return (
          message.bottom <= viewport.bottom && message.bottom > viewport.top
        );
      }),
    )
    .toBe(true);
  await expect
    .poll(() =>
      page
        .locator(".conversation-scroll")
        .evaluate(
          (element) =>
            element.scrollHeight - element.scrollTop - element.clientHeight,
        ),
    )
    .toBeLessThan(2);
}
async function readOlder(page: Page) {
  const history = page.locator(".conversation-scroll");
  const bounds = (await history.boundingBox())!;
  await page.mouse.move(
    bounds.x + bounds.width / 2,
    bounds.y + bounds.height / 2,
  );
  await page.mouse.wheel(0, -1800);
  await expect
    .poll(() =>
      history.evaluate(
        (element) =>
          element.scrollHeight - element.scrollTop - element.clientHeight,
      ),
    )
    .toBeGreaterThan(500);
  return history.evaluate((element) => element.scrollTop);
}

for (const viewport of [
  { width: 1440, height: 960 },
  { width: 390, height: 844 },
]) {
  test.describe(`Conversation opening scroll ${viewport.width}`, () => {
    test.use({
      viewport,
      isMobile: viewport.width < 960,
      hasTouch: viewport.width < 960,
    });

    test("positions only after a delayed history response has rendered", async ({
      page,
    }) => {
      const unexpected = await prepareFixture(page, "128:107");
      let release!: () => void;
      const held = new Promise<void>((resolve) => {
        release = resolve;
      });
      let requested = false;
      await page.route(historyPath, async (route) => {
        requested = true;
        await held;
        await reply(route, turns());
      });
      await page.reload();
      await expect.poll(() => requested).toBe(true);
      await expect(
        page.getByRole("listitem", { name: "Question 100", exact: true }),
      ).toHaveCount(0);
      expect(
        await page
          .locator(".conversation-scroll")
          .evaluate((element) => element.scrollTop),
      ).toBe(0);
      release();
      await atLatest(page);
      expect(unexpected).toEqual([]);
    });

    test("opens at the true latest message and keeps reading position during older pagination", async ({
      page,
    }, info) => {
      const unexpected = await prepareFixture(page, "128:107");
      await page.route(historyPath, (route) =>
        reply(
          route,
          route.request().url().includes("cursor=") ? turns(1, 50) : turns(),
          route.request().url().includes("cursor=") ? null : "older-page",
        ),
      );
      await page.reload();
      await atLatest(page);
      await expect(
        page.getByRole("listitem", { name: "Question 1", exact: true }),
      ).toHaveCount(0);
      expect(await page.evaluate(() => window.scrollY)).toBe(0);
      const panels = await page
        .locator(".conversation-rail-column, .conversation-inspector-column")
        .evaluateAll((elements) =>
          elements.map((element) => ({
            top: element.getBoundingClientRect().top,
            scroll: element.scrollTop,
          })),
        );
      await page.screenshot({ path: info.outputPath("latest.png") });
      await readOlder(page);
      const anchor = page.getByRole("listitem", {
        name: "Question 60",
        exact: true,
      });
      await anchor.evaluate((element) => {
        const history = element.closest(".conversation-scroll")!;
        history.scrollTop +=
          element.getBoundingClientRect().top -
          history.getBoundingClientRect().top -
          40;
      });
      const top = (await anchor.boundingBox())!.y;
      await page
        .getByRole("button", { name: "Load more Turns", exact: true })
        .evaluate((element: HTMLButtonElement) => element.click());
      await expect(
        page.getByRole("listitem", { name: "Question 1", exact: true }),
      ).toBeAttached();
      await expect
        .poll(async () => (await anchor.boundingBox())!.y)
        .toBeCloseTo(top, 0);
      await page
        .getByRole("button", {
          name: viewport.width < 960 ? "Open evidence" : "Close evidence",
          exact: true,
        })
        .click();
      await page
        .getByRole("button", {
          name: viewport.width < 960 ? "Close evidence" : "Open evidence",
          exact: true,
        })
        .click();
      await expect
        .poll(async () => (await anchor.boundingBox())!.y)
        .toBeCloseTo(top, 0);
      expect(
        await page
          .locator(".conversation-rail-column, .conversation-inspector-column")
          .evaluateAll((elements) =>
            elements.map((element) => ({
              top: element.getBoundingClientRect().top,
              scroll: element.scrollTop,
            })),
          ),
      ).toEqual(panels);
      expect(await page.evaluate(() => window.scrollY)).toBe(0);
      expect(unexpected).toEqual([]);
    });

    test("waits for slow history and ignores a previous Conversation response when switching", async ({
      page,
    }) => {
      const unexpected = await prepareFixture(page, "128:107");
      let release!: () => void;
      const held = new Promise<void>((resolve) => {
        release = resolve;
      });
      let requested = false;
      let responded = false;
      await page.route(historyPath, async (route) => {
        if (route.request().url().includes("fixture-conversation/")) {
          requested = true;
          await held;
          await reply(route, turns());
          responded = true;
        } else await reply(route, turns(101, 150, "fixture-conversation-0"));
      });
      await page.reload();
      await expect.poll(() => requested).toBe(true);
      await expect(
        page.getByRole("listitem", { name: "Question 100", exact: true }),
      ).toHaveCount(0);
      if (viewport.width < 960)
        await page
          .getByRole("button", { name: "Show conversations", exact: true })
          .click();
      await page
        .getByRole("link", { name: "Policy exceptions", exact: true })
        .click();
      await atLatest(page, 150);
      const reading = await readOlder(page);
      release();
      await expect.poll(() => responded).toBe(true);
      await page.evaluate(
        () =>
          new Promise<void>((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
          ),
      );
      await expect(
        page.getByRole("listitem", { name: "Question 100", exact: true }),
      ).toHaveCount(0);
      expect(
        await page
          .locator(".conversation-scroll")
          .evaluate((element) => element.scrollTop),
      ).toBeCloseTo(reading, 0);
      if (viewport.width < 960)
        await page
          .getByRole("button", { name: "Show conversations", exact: true })
          .click();
      await page
        .getByRole("link", { name: "Annual reporting structure", exact: true })
        .click();
      await atLatest(page);
      expect(unexpected).toEqual([]);
    });

    test("polling a pending answer does not pull a reader back down", async ({
      page,
    }) => {
      const unexpected = await prepareFixture(page, "128:107");
      const items = turns();
      items[49] = {
        ...items[49],
        status: "processing",
        stage: "generating",
        result: null,
      };
      let release!: () => void;
      const held = new Promise<void>((resolve) => {
        release = resolve;
      });
      await page.route(historyPath, (route) => reply(route, items));
      await page.route(
        "**/turns/fixture-conversation-turn-100",
        async (route) => {
          await held;
          await route.fulfill({
            contentType: "application/json",
            body: JSON.stringify(turns()[49]),
          });
        },
      );
      await page.reload();
      await expect(
        page.getByRole("listitem", { name: "Question 100", exact: true }),
      ).toBeAttached();
      await expect
        .poll(() =>
          page
            .locator(".conversation-scroll")
            .evaluate(
              (element) =>
                element.scrollHeight - element.scrollTop - element.clientHeight,
            ),
        )
        .toBeLessThan(2);
      const reading = await readOlder(page);
      release();
      await expect(
        page.getByText("End of answer 100.", { exact: false }).last(),
      ).toBeAttached();
      expect(
        await page
          .locator(".conversation-scroll")
          .evaluate((element) => element.scrollTop),
      ).toBeCloseTo(reading, 0);
      expect(unexpected).toEqual([]);
    });

    test("a successful empty history does not arm a scroll for a later submission", async ({
      page,
    }) => {
      const unexpected = await prepareFixture(page, "128:107");
      await page.route(historyPath, (route) => reply(route, []));
      await page.route("**/conversations/fixture-conversation/turns", (route) =>
        route.fulfill({
          contentType: "application/json",
          body: JSON.stringify(turns(1, 1)[0]),
        }),
      );
      await page.reload();
      await expect(
        page.getByRole("heading", {
          name: "Grounded answers from your workspace",
          exact: true,
        }),
      ).toBeVisible();
      expect(
        await page
          .locator(".conversation-scroll")
          .evaluate((element) => element.scrollTop),
      ).toBe(0);
      await page
        .getByLabel("Question", { exact: true })
        .fill("A new synthetic question");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      await expect(
        page.getByRole("listitem", { name: "Question 1", exact: true }),
      ).toBeAttached();
      expect(
        await page
          .locator(".conversation-scroll")
          .evaluate((element) => element.scrollTop),
      ).toBe(0);
      expect(unexpected).toEqual([]);
    });

    test("user scrolling while fonts settle cancels the pending opening scroll", async ({
      page,
    }) => {
      const unexpected = await prepareFixture(page, "128:107");
      await page.route(historyPath, (route) => reply(route, turns()));
      await page.addInitScript(() => {
        let release!: () => void;
        const ready = new Promise<void>((resolve) => {
          release = resolve;
        });
        Object.defineProperty(document.fonts, "ready", { get: () => ready });
        (window as unknown as { releaseFonts: () => void }).releaseFonts =
          release;
      });
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(
        page.getByRole("listitem", { name: "Question 100", exact: true }),
      ).toBeAttached();
      const history = page.locator(".conversation-scroll");
      const bounds = (await history.boundingBox())!;
      const touch =
        viewport.width < 960 ? await page.context().newCDPSession(page) : null;
      const swipe = async (from: number, to: number) => {
        await touch!.send("Input.dispatchTouchEvent", {
          type: "touchStart",
          touchPoints: [{ x: bounds.x + 50, y: from }],
        });
        for (let step = 1; step <= 5; step++)
          await touch!.send("Input.dispatchTouchEvent", {
            type: "touchMove",
            touchPoints: [
              { x: bounds.x + 50, y: from + ((to - from) * step) / 5 },
            ],
          });
        await touch!.send("Input.dispatchTouchEvent", {
          type: "touchEnd",
          touchPoints: [],
        });
      };
      if (touch) await swipe(bounds.y + 450, bounds.y + 250);
      else {
        await page.mouse.move(bounds.x + 50, bounds.y + 100);
        await page.mouse.wheel(0, 400);
      }
      await expect
        .poll(() => history.evaluate((element) => element.scrollTop))
        .toBeGreaterThan(100);
      if (touch) await swipe(bounds.y + 250, bounds.y + 350);
      else await page.mouse.wheel(0, -150);
      await page.evaluate(() =>
        (window as unknown as { releaseFonts: () => void }).releaseFonts(),
      );
      await page.evaluate(
        () =>
          new Promise<void>((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
          ),
      );
      expect(
        await history.evaluate(
          (element) =>
            element.scrollHeight - element.scrollTop - element.clientHeight,
        ),
      ).toBeGreaterThan(500);
      await touch?.detach();
      expect(unexpected).toEqual([]);
    });
  });
}
