// @vitest-environment node

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  session: {
    policyVersion: 1 as const,
    rememberMe: false,
    sessionStartedAt: 1_800_000_000,
    sessionExpiresAt: 1_800_000_000 + 28_800,
    issuer: "https://id.example/realms/knora",
    subject: "alice",
    accessToken: "alice-access-token",
    refreshToken: "alice-refresh-token",
    sessionId: "alice-session-id",
    workspaceIds: ["workspace-a"],
    capabilities: ["chat:read", "chat:write"],
    expiresAt: 1_800_000_300,
    refreshExpiresAt: 1_800_001_800,
  },
}));

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async () => state.session),
}));

import { GET, POST } from "@/app/api/[...path]/route";

describe("Conversation identity guard in BFF", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () => new Response(JSON.stringify({ ok: true }), { status: 200 }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  const conversationPath = {
    params: Promise.resolve({
      path: ["v1", "workspaces", "workspace-a", "conversations"],
    }),
  };

  const turnsPath = {
    params: Promise.resolve({
      path: [
        "v1",
        "workspaces",
        "workspace-a",
        "conversations",
        "conv-1",
        "turns",
      ],
    }),
  };

  it("rejects composer POST when expected identity mismatches current session", async () => {
    const request = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations",
      {
        method: "POST",
        headers: {
          "x-knora-expected-issuer": "https://id.example/realms/knora",
          "x-knora-expected-subject": "bob", // alice is signed in!
          "content-type": "application/json",
        },
        body: JSON.stringify({ question: "Hello" }),
      },
    );
    const bodySpy = vi.spyOn(request, "arrayBuffer");

    const response = await POST(request, conversationPath);
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const json = await response.json();
    expect(json).toEqual({ detail: "SESSION_IDENTITY_MISMATCH" });
    expect(fetch).not.toHaveBeenCalled();
    expect(bodySpy).not.toHaveBeenCalled();
  });

  it("rejects composer POST when same subject but different issuer", async () => {
    const request = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations",
      {
        method: "POST",
        headers: {
          "x-knora-expected-issuer": "https://different-issuer.example",
          "x-knora-expected-subject": "alice",
          "content-type": "application/json",
        },
        body: JSON.stringify({ question: "Hello" }),
      },
    );

    const response = await POST(request, conversationPath);
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({
      detail: "SESSION_IDENTITY_MISMATCH",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects composer POST when expected identity headers are missing", async () => {
    const request = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: "Hello" }),
      },
    );

    const response = await POST(request, conversationPath);
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({
      detail: "SESSION_IDENTITY_MISMATCH",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects composer turns POST when only one identity header is provided", async () => {
    const request = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations/conv-1/turns",
      {
        method: "POST",
        headers: {
          "x-knora-expected-subject": "alice", // missing expected-issuer
          "content-type": "application/json",
        },
        body: JSON.stringify({ question: "Hello" }),
      },
    );

    const response = await POST(request, turnsPath);
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({
      detail: "SESSION_IDENTITY_MISMATCH",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards composer POST when expected identity matches current session and strips expected headers", async () => {
    const request = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations/conv-1/turns",
      {
        method: "POST",
        headers: {
          "x-knora-expected-issuer": "https://id.example/realms/knora",
          "x-knora-expected-subject": "alice",
          "Idempotency-Key": "stable-idempotency-key",
          "content-type": "application/json",
        },
        body: JSON.stringify({ question: "Keep this turn" }),
      },
    );

    const response = await POST(request, turnsPath);
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledOnce();

    const [forwardUrl, forwardInit] = vi.mocked(fetch).mock.calls[0];
    expect(forwardUrl).toContain(
      "/v1/workspaces/workspace-a/conversations/conv-1/turns",
    );

    const forwardedHeaders = new Headers(forwardInit!.headers);
    expect(forwardedHeaders.get("authorization")).toBe(
      "Bearer alice-access-token",
    );
    expect(forwardedHeaders.get("Idempotency-Key")).toBe(
      "stable-idempotency-key",
    );
    expect(forwardedHeaders.get("x-knora-expected-issuer")).toBeNull();
    expect(forwardedHeaders.get("x-knora-expected-subject")).toBeNull();

    const forwardedBody = new TextDecoder().decode(
      forwardInit!.body as ArrayBuffer,
    );
    expect(forwardedBody).toBe('{"question":"Keep this turn"}');
  });

  it("handles path variants (trailing slash, percent-encoding) for composer POST", async () => {
    const trailingSlashContext = {
      params: Promise.resolve({
        path: ["v1", "workspaces", "workspace-a", "conversations", ""],
      }),
    };

    const request = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations/",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: "Hello" }),
      },
    );

    const response = await POST(request, trailingSlashContext);
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({
      detail: "SESSION_IDENTITY_MISMATCH",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("checks GET requests with expected identity headers and permits matching or missing", async () => {
    // 1. GET with mismatching pair rejected
    const mismatchGet = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations/conv-1",
      {
        method: "GET",
        headers: {
          "x-knora-expected-issuer": "https://id.example/realms/knora",
          "x-knora-expected-subject": "bob",
        },
      },
    );
    const getContext = {
      params: Promise.resolve({
        path: ["v1", "workspaces", "workspace-a", "conversations", "conv-1"],
      }),
    };

    const mismatchResponse = await GET(mismatchGet, getContext);
    expect(mismatchResponse.status).toBe(401);
    expect(await mismatchResponse.json()).toEqual({
      detail: "SESSION_IDENTITY_MISMATCH",
    });
    expect(fetch).not.toHaveBeenCalled();

    // 2. GET with matching pair forwards and strips headers
    const matchingGet = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/conversations/conv-1",
      {
        method: "GET",
        headers: {
          "x-knora-expected-issuer": "https://id.example/realms/knora",
          "x-knora-expected-subject": "alice",
        },
      },
    );
    const matchingResponse = await GET(matchingGet, getContext);
    expect(matchingResponse.status).toBe(200);
    const [, init] = vi.mocked(fetch).mock.calls[0];
    const forwardedHeaders = new Headers(init!.headers);
    expect(forwardedHeaders.get("x-knora-expected-issuer")).toBeNull();
    expect(forwardedHeaders.get("x-knora-expected-subject")).toBeNull();

    // 3. GET without expected headers forwards normally (backward compatibility)
    vi.mocked(fetch).mockClear();
    const normalGet = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/documents",
      { method: "GET" },
    );
    const docContext = {
      params: Promise.resolve({
        path: ["v1", "workspaces", "workspace-a", "documents"],
      }),
    };
    const docResponse = await GET(normalGet, docContext);
    expect(docResponse.status).toBe(200);
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("permits unrelated non-composer POST without expected headers", async () => {
    const request = new Request(
      "https://app.example/api/v1/workspaces/workspace-a/documents",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: "doc-1" }),
      },
    );
    const docContext = {
      params: Promise.resolve({
        path: ["v1", "workspaces", "workspace-a", "documents"],
      }),
    };
    const response = await POST(request, docContext);
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledOnce();
  });
});
