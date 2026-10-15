// @vitest-environment node

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({ getSession: vi.fn() }));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined })),
}));

import { getSession } from "@/lib/auth/session";
import { proxyEvaluationPath } from "@/app/api/operator/_evaluation-proxy";

const target = (workspace: string) =>
  `/v1/workspaces/${workspace}/evaluation/runs`;
const session = {
  issuer: "https://id.example/realm",
  subject: "owner",
  accessToken: "server-only-token",
  workspaceIds: [],
  capabilities: ["operator:read", "evaluations:run", "questions:ask"],
  expiresAt: 1_900_000_000,
};

function request(method = "POST", origin = "https://app.example") {
  return new Request(
    "https://app.example/api/operator/evaluation/runs?workspaceId=workspace-a",
    {
      method,
      headers: {
        origin,
        "content-type": "application/json",
        authorization: "untrusted-browser-token",
        cookie: "untrusted-cookie",
      },
      ...(method === "GET" ? {} : { body: '{"dataset_id":"set-1"}' }),
    },
  );
}

describe("Evaluation BFF admission and transport", () => {
  beforeEach(() => {
    vi.mocked(getSession).mockResolvedValue(session);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}")),
    );
  });
  afterEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it("rejects cross-origin mutations before session lookup or backend effects", async () => {
    const result = await proxyEvaluationPath(
      request("POST", "https://evil.example"),
      target,
      ["evaluations:run"],
      "json",
    );
    expect(result.status).toBe(403);
    expect(getSession).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not grant launch from operator read alone", async () => {
    vi.mocked(getSession).mockResolvedValue({
      ...session,
      capabilities: ["operator:read"],
    });
    const result = await proxyEvaluationPath(
      request(),
      target,
      ["evaluations:run"],
      "json",
    );
    expect(result.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards JSON using only the server bearer and marks output private", async () => {
    const result = await proxyEvaluationPath(
      request(),
      target,
      ["evaluations:run"],
      "json",
    );
    expect(result.status).toBe(200);
    expect(result.headers.get("cache-control")).toBe("no-store");
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe(
      "http://127.0.0.1:8000/v1/workspaces/workspace-a/evaluation/runs",
    );
    const options = init as RequestInit;
    const headers = new Headers(options.headers);
    expect(headers.get("authorization")).toBe("Bearer server-only-token");
    expect(headers.has("cookie")).toBe(false);
    expect(options.cache).toBe("no-store");
    expect(new TextDecoder().decode(options.body as Uint8Array)).toBe(
      '{"dataset_id":"set-1"}',
    );
  });

  it("keeps multipart boundaries and streams authenticated PDF responses", async () => {
    const form = new FormData();
    form.append(
      "file",
      new Blob(["%PDF-fixture"], { type: "application/pdf" }),
      "fixture.pdf",
    );
    const upload = new Request(
      "https://app.example/api/operator/evaluation/datasets?workspaceId=workspace-a",
      {
        method: "POST",
        headers: { origin: "https://app.example" },
        body: form,
      },
    );
    const contentType = upload.headers.get("content-type");
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("%PDF-source", {
        headers: {
          "content-type": "application/pdf",
          "content-disposition": 'inline; filename="source.pdf"',
          "set-cookie": "must-not-forward",
        },
      }),
    );
    const result = await proxyEvaluationPath(upload, target, [], "multipart");
    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("content-type")).toBe(contentType);
    expect(new TextDecoder().decode(init.body as Uint8Array)).toContain(
      "%PDF-fixture",
    );
    expect(await result.text()).toBe("%PDF-source");
    expect(result.headers.get("content-type")).toBe("application/pdf");
    expect(result.headers.has("set-cookie")).toBe(false);
    expect(result.headers.get("x-content-type-options")).toBe("nosniff");
  });

  it("rejects oversized bodies without contacting the backend", async () => {
    const oversized = new Request(
      "https://app.example/api/operator/evaluation/runs?workspaceId=workspace-a",
      {
        method: "POST",
        headers: {
          origin: "https://app.example",
          "content-type": "application/json",
        },
        body: "x".repeat(262145),
      },
    );
    const result = await proxyEvaluationPath(oversized, target, [], "json");
    expect(result.status).toBe(413);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("reports backend failures and authorization without fabricating data", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('{"error":{"code":"WORKSPACE_ACCESS_DENIED"}}', {
        status: 403,
      }),
    );
    const denied = await proxyEvaluationPath(request("GET"), target);
    expect(denied.status).toBe(403);
    vi.mocked(fetch).mockRejectedValueOnce(
      new Error("secret endpoint unavailable"),
    );
    const unavailable = await proxyEvaluationPath(request("GET"), target);
    expect(unavailable.status).toBe(503);
    expect(await unavailable.text()).not.toContain("secret endpoint");
  });
});
