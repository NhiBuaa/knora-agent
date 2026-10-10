import { randomUUID, createHash } from "node:crypto";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { EncryptJWT, jwtDecrypt } from "jose";
import { captureIdentity, openFigmaLogin } from "./support/figma-auth";
import realm from "../../../test/fixtures/keycloak/figma-realm.json";
import type {
  ConversationResponse,
  TurnResponse,
} from "../../generated/knora-openapi";

test("live interrupted Turn reconciles history before an explicit retry", async ({
  page,
}) => {
  test.skip(
    process.env.FIGMA_CONTROLLER_PROOF !== "1",
    "Requires owned lease-expiry controller proof.",
  );
  test.setTimeout(150_000);
  const evidence =
    "../.verification/figma/q1/evidence/live-interruption-2026-10-10";
  mkdirSync(evidence, { recursive: true });
  const identity = realm.users.find(
    (user) => user.username === "m5-delete-user",
  )!;
  await openFigmaLogin(page);
  await page.locator("#username").fill(identity.username);
  await page.locator("#password").fill(identity.credentials[0].value);
  await page.locator("#kc-login").click();
  await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
  const create = async (pathname: string, data: unknown) =>
    page.evaluate(
      async ({ pathname, data, key }) => {
        const response = await fetch(pathname, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "content-type": "application/json",
            "Idempotency-Key": key,
          },
          body: JSON.stringify(data),
        });
        return { status: response.status, body: await response.json() };
      },
      { pathname, data, key: randomUUID() },
    );
  const name = `q1-interruption-${randomUUID()}`;
  const workspace = await create("/api/v1/workspaces", { name });
  expect(workspace.status).toBe(201);
  const workspaceId = workspace.body.id as string;
  const conversation = await create(
    `/api/v1/workspaces/${workspaceId}/conversations`,
    {},
  );
  expect(conversation.status).toBe(201);
  const conversationPath = `/workspaces/${workspaceId}/conversations/${conversation.body.id}`;
  await page.goto(conversationPath);
  const question = "Preserve this question after the worker lease expires.";
  await page.getByLabel("Question", { exact: true }).fill(question);
  const submitted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === `/api/v1${conversationPath}/turns`,
  );
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const admitted = await submitted;
  expect(admitted.status()).toBe(202);
  const turn = (await admitted.json()) as TurnResponse;
  expect(turn.status).toBe("queued");
  writeFileSync(
    `${evidence}/admission.json`,
    JSON.stringify(
      {
        workspaceId,
        workspaceName: name,
        conversationPath,
        turnId: turn.id,
        question,
        admittedAt: new Date().toISOString(),
      },
      null,
      2,
    ),
  );
  // Controller claims only this new owned Turn, lets the real 60s lease expire,
  // then uses the production recovery seam. No intercepted or SQL-forced status.
  await expect(
    page.getByRole("heading", {
      name: "The answer was interrupted.",
      exact: true,
    }),
  ).toBeVisible({ timeout: 120_000 });
  const historyPath = `/api/v1${conversationPath}/turns`;
  const history = async () =>
    page.evaluate(async (pathname) => {
      const response = await fetch(pathname, {
        credentials: "same-origin",
        cache: "no-store",
      });
      return {
        status: response.status,
        body: (await response.json()) as { items: TurnResponse[] },
      };
    }, historyPath);
  const before = await history();
  await expect(
    page.getByRole("heading", { name: "System error", exact: true }),
  ).toHaveCount(0);
  expect(before.status).toBe(200);
  expect(before.body.items).toHaveLength(1);
  expect(before.body.items[0]).toMatchObject({
    id: turn.id,
    status: "interrupted",
    error_code: "EXECUTION_OUTCOME_UNKNOWN",
    question,
    result: null,
  });
  await captureIdentity(page, `${evidence}/interrupted.png`);
  const unexpectedSubmissions: string[] = [];
  const observePost = (request: import("@playwright/test").Request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname.endsWith("/turns")
    )
      unexpectedSubmissions.push(request.url());
  };
  page.on("request", observePost);
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByLabel("Question", { exact: true })).toHaveValue(
    question,
  );
  await expect(page.getByLabel("Question", { exact: true })).toBeFocused();
  await expect(
    page.getByText("History checked. Send the same question when ready.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(unexpectedSubmissions).toEqual([]);
  expect((await history()).body).toEqual(before.body);
  await captureIdentity(page, `${evidence}/retry-draft.png`);
  page.off("request", observePost);
  const retried = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === `/api/v1${conversationPath}/turns`,
  );
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const retryResponse = await retried;
  expect(retryResponse.status()).toBe(202);
  expect(retryResponse.request().headers()["idempotency-key"]).toBeTruthy();
  const retryTurn = (await retryResponse.json()) as TurnResponse;
  expect(retryTurn.id).not.toBe(turn.id);
  expect(retryTurn.question).toBe(question);
  expect(retryTurn.status).toBe("queued");
  const after = await history();
  expect(after.body.items).toHaveLength(2);
  expect(after.body.items.find((item) => item.id === turn.id)).toEqual(
    before.body.items[0],
  );
  writeFileSync(
    `${evidence}/journey.json`,
    JSON.stringify(
      {
        workspaceId,
        conversationPath,
        interruptedTurnId: turn.id,
        retryTurnId: retryTurn.id,
        retryWithoutPost: true,
        explicitRetryStatus: retryResponse.status(),
        interruptedHistoryRetained: true,
      },
      null,
      2,
    ),
  );
});

test("real-time bounded session expiry preserves the draft and recovers through a new tab", async ({
  page,
  context,
}) => {
  try {
    const evidence =
      "../.verification/figma/q1/evidence/session-expiry-2026-10-10";
    mkdirSync(evidence, { recursive: true });
    const observation = JSON.parse(
      readFileSync(
        "../.verification/figma/q1/evidence/live-turn-terminal.json",
        "utf8",
      ),
    ) as { workspaceId: string; conversationPath: string; turnId: string };
    expect(observation.conversationPath).toMatch(
      new RegExp(
        `^/workspaces/${observation.workspaceId}/conversations/[a-f0-9-]+$`,
      ),
    );
    const identity = realm.users.find(
      (user) => user.username === "m5-delete-user",
    )!;
    await openFigmaLogin(page);
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.credentials[0].value);
    await page.locator("#kc-login").click();
    await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
    await page.goto(observation.conversationPath);
    await expect(
      page.getByText("Loading history…", { exact: true }),
    ).toBeHidden();
    const historyUrl = `/api/v1${observation.conversationPath}/turns`;
    const initialResponse = await page.request.get(historyUrl);
    expect(initialResponse.status()).toBe(200);
    const originalHistory = await initialResponse.json();
    expect(
      originalHistory.items.some(
        (turn: TurnResponse) =>
          turn.id === observation.turnId && turn.status === "answered",
      ),
    ).toBe(true);
    const draft = "Keep this draft while my session expires.";
    await page.getByLabel("Question", { exact: true }).fill(draft);

    // Use the real authenticated payload with a shortened test-only absolute
    // lifetime. No clock mocking, native token changes or intercepted responses.
    const cookie = (await context.cookies()).find(
      (item) => item.name === "knora_session",
    )!;
    expect(Boolean(cookie)).toBe(true);
    const key = createHash("sha256")
      .update("figma-e2e-test-session-secret-only")
      .digest();
    const { payload } = await jwtDecrypt(cookie.value, key);
    const deadline = Math.floor(Date.now() / 1000) + 4;
    expect(Number(payload.exp) > deadline).toBe(true);
    expect(cookie.expires > deadline).toBe(true);
    const bounded = await new EncryptJWT({
      ...payload,
      sessionExpiresAt: deadline,
    })
      .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
      .setExpirationTime(deadline)
      .encrypt(key);
    await context.addCookies([{ ...cookie, value: bounded }]);
    const beforeExpiry = await (
      await page.request.get("/api/auth/session")
    ).json();
    expect(Boolean(beforeExpiry.session?.subject)).toBe(true);
    await expect
      .poll(() => Date.now() >= deadline * 1000, { timeout: 8_000 })
      .toBe(true);
    expect(
      (await context.cookies()).some((item) => item.name === "knora_session"),
    ).toBe(true);
    const rejection = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === historyUrl,
    );
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    expect((await rejection).status()).toBe(401);
    await expect(
      page.getByText(/Your session has expired\. Keep this tab open/),
    ).toBeVisible();
    await expect(page.getByLabel("Question", { exact: true })).toHaveValue(
      draft,
    );
    await expect(
      page.getByRole("button", { name: "Ask", exact: true }),
    ).toBeDisabled();
    expect(
      (await (await page.request.get("/api/auth/session")).json()).session,
    ).toBeNull();
    await captureIdentity(page, `${evidence}/expired-draft.png`);

    const popupPromise = page.waitForEvent("popup");
    await page
      .getByRole("link", { name: "Sign in again", exact: true })
      .click();
    const popup = await popupPromise;
    try {
      await popup.waitForURL(/\/workspaces\/[a-f0-9-]+$/);
      const recovered = await (
        await popup.request.get("/api/auth/session")
      ).json();
      expect(recovered.session.subject).toBe(beforeExpiry.session.subject);
      await page
        .getByRole("button", { name: "Reload history", exact: true })
        .click();
      await expect(
        page.getByText(/Your session has expired\. Keep this tab open/),
      ).toBeHidden();
      await expect(page.getByLabel("Question", { exact: true })).toHaveValue(
        draft,
      );
      await expect(
        page.getByRole("button", { name: "Ask", exact: true }),
      ).toBeEnabled();
      const recoveredHistory = await page.request.get(historyUrl);
      expect(recoveredHistory.status()).toBe(200);
      expect(await recoveredHistory.json()).toEqual(originalHistory);
      await captureIdentity(page, `${evidence}/recovered-draft.png`);
      writeFileSync(
        `${evidence}/journey.json`,
        JSON.stringify(
          {
            realNativeLogin: true,
            shortenedAbsoluteSessionLifetimeSeconds: 4,
            clockMocked: false,
            browserCookieRetainedAtExpiry: true,
            expiredSubmissionStatus: 401,
            draftPreserved: true,
            recoveredIdentityUnchanged: true,
            historyUnchanged: true,
            retryEnabled: true,
            limitation:
              "Shortened signed fixture session; does not measure default TTL or provider refresh-token expiry.",
          },
          null,
          2,
        ),
      );
    } finally {
      await popup.close();
    }
  } catch {
    for (const current of context.pages())
      await current.goto("about:blank").catch(() => {});
    throw new Error(
      "Bounded session expiry journey failed; sensitive context removed.",
    );
  }
});

test("New Conversation leaves retained answers, citations, refusal and draft intact", async ({
  page,
}) => {
  const evidence =
    "../.verification/figma/q1/evidence/conversation-navigation-2026-10-09/distinct-destination";
  mkdirSync(evidence, { recursive: true });
  const observation = JSON.parse(
    readFileSync(
      "../.verification/figma/q1/evidence/live-turn-terminal.json",
      "utf8",
    ),
  ) as {
    workspaceId: string;
    conversationPath: string;
    turnId: string;
  };
  const refusal = JSON.parse(
    readFileSync(
      "../.verification/figma/q1/evidence/live-refusal-terminal.json",
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
    await expect(page).toHaveURL(
      (url) =>
        url.pathname !== observation.conversationPath &&
        new RegExp(
          `^/workspaces/${observation.workspaceId}/conversations/[a-f0-9-]+$`,
        ).test(url.pathname),
    );
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
    const destination = (await detail.json()) as ConversationResponse;
    expect(destination.id).toBe(destinationId);
    expect(destination.workspace_id).toBe(observation.workspaceId);
    expect(destination.archived).toBe(false);
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
