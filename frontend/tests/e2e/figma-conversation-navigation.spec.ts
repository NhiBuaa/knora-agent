import { randomUUID, createHash } from "node:crypto";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { captureIdentity, openFigmaLogin } from "./support/figma-auth";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import type { TurnResponse } from "../../generated/knora-openapi";

test("New Conversation leaves retained answers, citations, refusal and draft intact", async ({
  page,
}) => {
  const evidence =
    "../.superpowers/figma/q1/evidence/conversation-navigation-2026-10-09";
  mkdirSync(evidence, { recursive: true });
  const observation = JSON.parse(
    readFileSync(
      "../.superpowers/figma/q1/evidence/live-turn-terminal.json",
      "utf8",
    ),
  ) as {
    workspaceId: string;
    conversationPath: string;
    turnId: string;
  };
  const refusal = JSON.parse(
    readFileSync(
      "../.superpowers/figma/q1/evidence/live-refusal-terminal.json",
      "utf8",
    ),
  ) as typeof observation;
  expect(observation.conversationPath).toMatch(
    /^\/workspaces\/[a-f0-9-]+\/conversations\/[a-f0-9-]+$/,
  );
  expect(
    observation.conversationPath.startsWith(
      `/workspaces/${observation.workspaceId}/`,
    ),
  ).toBe(true);
  expect(refusal.conversationPath).toBe(observation.conversationPath);
  const identity = realm.users.find(
    (user) => user.username === "m5-delete-user",
  )!;
  await openFigmaLogin(page);
  await page.locator("#username").fill(identity.username);
  await page.locator("#password").fill(identity.credentials[0].value);
  await page.locator("#kc-login").click();
  await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
  const api = `/api/v1${observation.conversationPath}`;
  const readHistory = async () => {
    const response = await page.request.get(`${api}/turns`);
    expect(response.status()).toBe(200);
    return (await response.json()) as {
      items: TurnResponse[];
      next_cursor: string | null;
    };
  };
  const initial = await readHistory();
  expect(initial.next_cursor).toBeNull();
  expect(
    initial.items.find((turn) => turn.id === observation.turnId)?.status,
  ).toBe("answered");
  expect(initial.items.find((turn) => turn.id === refusal.turnId)?.status).toBe(
    "refused",
  );
  const digest = (value: unknown) =>
    createHash("sha256").update(JSON.stringify(value)).digest("hex");
  const before = digest(initial);
  const journeys: unknown[] = [];
  for (const state of [
    "answer",
    "citation",
    "refusal",
    "unsupported-draft",
  ] as const) {
    await page.goto(observation.conversationPath);
    await expect(
      page.getByText("Loading history…", { exact: true }),
    ).toBeHidden();
    if (state === "answer")
      await expect(
        page.getByText(
          initial.items.find((turn) => turn.id === observation.turnId)!.result!
            .answer!,
          { exact: true },
        ),
      ).toBeVisible();
    if (state === "citation") {
      await page
        .getByRole("button", { name: /citation 1/i })
        .first()
        .click();
      await expect(
        page.getByRole("complementary", { name: /evidence/i }),
      ).toContainText("q1-report-structure.md");
    }
    if (state === "refusal")
      await expect(
        page.getByRole("heading", {
          name: "I don’t have enough evidence to answer that.",
        }),
      ).toBeVisible();
    if (state === "unsupported-draft")
      await page
        .getByLabel("Question", { exact: true })
        .fill("What is the late-submission policy?");
    await captureIdentity(page, `${evidence}/${state}-before.png`);
    const created = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname ===
          `/api/v1/workspaces/${observation.workspaceId}/conversations`,
    );
    await page
      .getByRole("button", { name: "New Conversation", exact: true })
      .click();
    const response = await created;
    expect(response.status()).toBe(201);
    expect(response.request().headers()["idempotency-key"]).toBeTruthy();
    await expect(page).toHaveURL(/\/workspaces\/[^/]+\/conversations\/[^/]+$/);
    const destinationPath = new URL(page.url()).pathname;
    expect(destinationPath).toMatch(
      new RegExp(
        `^/workspaces/${observation.workspaceId}/conversations/[a-f0-9-]+$`,
      ),
    );
    expect(destinationPath).not.toBe(observation.conversationPath);
    const destinationId = destinationPath.split("/").at(-1)!;
    await expect(
      page.getByText("Loading history…", { exact: true }),
    ).toBeHidden();
    await expect(page.getByLabel("Question", { exact: true })).toHaveValue("");
    const detail = await page.request.get(`/api/v1${destinationPath}`);
    expect(detail.status()).toBe(200);
    expect((await detail.json()).id).toBe(destinationId);
    const empty = await page.request.get(`/api/v1${destinationPath}/turns`);
    expect(empty.status()).toBe(200);
    expect((await empty.json()).items).toEqual([]);
    expect(digest(await readHistory())).toBe(before);
    await captureIdentity(page, `${evidence}/${state}-created.png`);
    journeys.push({
      state,
      createStatus: 201,
      destinationPath,
      sourceHistoryUnchanged: true,
    });
    writeFileSync(
      `${evidence}/journey.json`,
      JSON.stringify(
        {
          runId: randomUUID(),
          sourcePath: observation.conversationPath,
          sourceHistoryHash: before,
          journeys,
          limitation:
            "Answer and refusal coexist in retained history; no artificial retrieval or interruption outcome is generated.",
        },
        null,
        2,
      ),
    );
  }
});
