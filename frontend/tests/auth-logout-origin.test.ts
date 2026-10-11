// @vitest-environment node

import { describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/auth/logout/route";
import { encodeSession } from "@/lib/auth/session";

it.each([204, 503])(
  "uses server logout, with browser fallback on failure (%s)",
  async (status) => {
    vi.stubEnv("KEYCLOAK_ISSUER", "https://id.example/realms/knora");
    vi.stubEnv("KEYCLOAK_POST_LOGOUT_REDIRECT_URI", "https://app.example/");
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status }));
    vi.stubGlobal("fetch", fetcher);
    try {
      const cookie = await encodeSession({
        issuer: "https://id.example/realms/knora",
        subject: "fixture",
        accessToken: "test-access",
        refreshToken: "test-refresh",
        workspaceIds: [],
        capabilities: [],
      });
      const response = await POST(
        new Request("https://app.example/api/auth/logout", {
          method: "POST",
          headers: {
            host: "app.example",
            origin: "https://app.example",
            cookie: `knora_session=${cookie}`,
          },
        }),
      );
      expect(fetcher).toHaveBeenCalledOnce();
      const [url, options] = fetcher.mock.calls[0];
      expect(String(url)).toBe(
        "https://id.example/realms/knora/protocol/openid-connect/logout",
      );
      expect(options.method).toBe("POST");
      expect(options.body.get("refresh_token")).toBe("test-refresh");
      const location = new URL(response.headers.get("location")!);
      expect(location.origin).toBe(
        status === 204 ? "https://app.example" : "https://id.example",
      );
      expect(location.href).not.toContain("test-refresh");
      expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
    } finally {
      vi.unstubAllGlobals();
      vi.unstubAllEnvs();
    }
  },
);

describe("logout mutation", () => {
  it("accepts a browser same-origin POST when Next represents its internal URL as localhost", async () => {
    const response = await POST(
      new Request("http://localhost:3000/api/auth/logout", {
        method: "POST",
        headers: {
          host: "127.0.0.1:3000",
          origin: "http://127.0.0.1:3000",
          "sec-fetch-site": "same-origin",
        },
      }),
    );
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(
      "http://127.0.0.1:3000/?signed-out=1",
    );
  });
  it("does not clear cookies for a cross-site POST without Origin", async () => {
    const response = await POST(
      new Request("https://app.example/api/auth/logout", {
        method: "POST",
        headers: { "sec-fetch-site": "cross-site" },
      }),
    );

    expect(response.status).toBe(403);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});

it("starts Keycloak browser logout with an exact configured return and no token in the URL", async () => {
  const previousIssuer = process.env.KEYCLOAK_ISSUER;
  const previousReturn = process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI;
  process.env.KEYCLOAK_ISSUER = "https://id.example/realms/knora";
  process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI = "https://app.example/";
  try {
    const response = await POST(
      new Request(
        "https://app.example/api/auth/logout?next=https://evil.example",
        {
          method: "POST",
          headers: {
            host: "app.example",
            origin: "https://app.example",
            "sec-fetch-site": "same-origin",
          },
        },
      ),
    );
    const location = new URL(response.headers.get("location") ?? "");
    expect(response.status).toBe(303);
    expect(location.origin).toBe("https://id.example");
    expect(location.pathname).toBe(
      "/realms/knora/protocol/openid-connect/logout",
    );
    expect(location.searchParams.get("client_id")).toBe("knora-web");
    expect(location.searchParams.get("post_logout_redirect_uri")).toBe(
      "https://app.example/",
    );
    expect(location.searchParams.get("state")).toBe("knora-logout-complete");
    expect(location.searchParams.has("id_token_hint")).toBe(false);
    expect(location.href).not.toContain("evil.example");
    expect(response.headers.get("set-cookie")).toContain("knora_session=");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  } finally {
    if (previousIssuer === undefined) delete process.env.KEYCLOAK_ISSUER;
    else process.env.KEYCLOAK_ISSUER = previousIssuer;
    if (previousReturn === undefined)
      delete process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI;
    else process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI = previousReturn;
  }
});

it("clears the local session when the configured return does not match this origin", async () => {
  const previousIssuer = process.env.KEYCLOAK_ISSUER;
  const previousReturn = process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI;
  process.env.KEYCLOAK_ISSUER = "https://id.example/realms/knora";
  process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI = "https://another.example/";
  try {
    const response = await POST(
      new Request("https://app.example/api/auth/logout", {
        method: "POST",
        headers: { host: "app.example", origin: "https://app.example" },
      }),
    );
    expect(response.headers.get("location")).toBe(
      "https://app.example/?signed-out=1",
    );
    expect(response.headers.get("set-cookie")).toContain("knora_session=");
  } finally {
    if (previousIssuer === undefined) delete process.env.KEYCLOAK_ISSUER;
    else process.env.KEYCLOAK_ISSUER = previousIssuer;
    if (previousReturn === undefined)
      delete process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI;
    else process.env.KEYCLOAK_POST_LOGOUT_REDIRECT_URI = previousReturn;
  }
});
