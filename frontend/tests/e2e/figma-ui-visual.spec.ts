import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  nativeStates,
  prepareFixture,
  visualStates,
} from "./support/figma-state-fixtures";

// Keep review evidence when a subsequent focused Playwright invocation clears outputDir.
const evidence = path.resolve(
  process.cwd(),
  "../.superpowers/figma/q1/evidence",
);
fs.mkdirSync(evidence, { recursive: true });
const capturePath = (name: string) => path.join(evidence, name);

for (const state of visualStates) {
  test(`source fixture ${state.id} ${state.name}`, async ({ page }, info) => {
    const unexpected = await prepareFixture(page, state.id);
    await expect(page.locator("body")).toBeVisible();
    expect(
      await page.evaluate(
        () =>
          Array.from(document.fonts).filter((font) => font.status === "loaded")
            .length,
      ),
    ).toBeGreaterThanOrEqual(2);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    if (
      !nativeStates.has(state.id) &&
      !["228:293", "228:326"].includes(state.id)
    ) {
      expect(
        (await page.locator(".kn-product-header").boundingBox())?.height,
      ).toBe(64);
    }
    const path = capturePath(`${state.id.replace(":", "-")}-1440x960.png`);
    await page.screenshot({ path, animations: "disabled" });
    await info.attach("source-fixture-capture", {
      path,
      contentType: "image/png",
    });
    expect(
      unexpected,
      "Unsupported fixture requests must remain visible as failures",
    ).toEqual([]);
  });
}

for (const viewport of [
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
]) {
  for (const state of [
    "128:110",
    "128:121",
    "128:122",
    "148:116",
    "194:194",
    "198:200",
    "206:206",
    "242:333",
  ]) {
    test(`responsive fixture ${state} ${viewport.width}x${viewport.height}`, async ({
      page,
    }, info) => {
      await page.setViewportSize(viewport);
      const unexpected = await prepareFixture(page, state);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      for (const dialog of await page.getByRole("dialog").all()) {
        const box = await dialog.boundingBox();
        expect(box!.x).toBeGreaterThanOrEqual(0);
        expect(box!.width).toBeLessThanOrEqual(viewport.width);
      }
      if (state === "128:110") {
        const composer = await page
          .getByRole("form", { name: "Question composer" })
          .boundingBox();
        expect(composer!.y + composer!.height).toBeLessThanOrEqual(
          viewport.height,
        );
      }
      await page.screenshot({
        path: capturePath(
          `${state.replace(":", "-")}-${viewport.width}x${viewport.height}.png`,
        ),
        animations: "disabled",
      });
      expect(unexpected).toEqual([]);
    });
  }
}

for (const state of ["128:110", "128:120", "152:128", "194:194", "242:333"]) {
  test(`dark and reduced motion fixture ${state}`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
    const unexpected = await prepareFixture(page, state);
    if (!nativeStates.has(state))
      await page.evaluate(
        () => (document.documentElement.dataset.theme = "dark"),
      );
    expect(
      await page.evaluate(
        () => matchMedia("(prefers-reduced-motion: reduce)").matches,
      ),
    ).toBe(true);
    await page.screenshot({
      path: capturePath(`${state.replace(":", "-")}-dark-reduced-motion.png`),
      animations: "disabled",
    });
    expect(unexpected).toEqual([]);
  });
}
