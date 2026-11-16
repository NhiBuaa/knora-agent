import http from "node:http";
import { randomUUID } from "node:crypto";
import {
  generateKeyPair,
  exportJWK,
  SignJWT,
  jwtVerify,
  createLocalJWKSet,
} from "jose";

const PORT = Number(process.env.SUPABASE_FIXTURE_PORT || "54321");
const ISSUER = `http://127.0.0.1:${PORT}/auth/v1`;
const AUDIENCE = "authenticated";

// Generate in-memory ES256 key pair
const { publicKey, privateKey } = await generateKeyPair("ES256");
const jwk = {
  ...(await exportJWK(publicKey)),
  kid: "supabase-e2e-fixture-key",
  alg: "ES256",
};
const jwkSet = createLocalJWKSet({ keys: [jwk] });

const testSubject = "ca0af038-9a87-4e0c-9dd3-2f3d47fc6bf1";
const activeSessions = new Map(); // sessionId -> { refreshToken, subject, revoked }

async function createToken(subject, sessionId, expiresIn = 3600) {
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({
    role: "authenticated",
    is_anonymous: false,
    session_id: sessionId,
  })
    .setProtectedHeader({ alg: "ES256", kid: "supabase-e2e-fixture-key" })
    .setIssuer(ISSUER)
    .setAudience(AUDIENCE)
    .setSubject(subject)
    .setIssuedAt(now)
    .setExpirationTime(now + expiresIn)
    .sign(privateKey);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  res.setHeader("access-control-allow-origin", "*");
  res.setHeader("access-control-allow-headers", "*");
  res.setHeader("access-control-allow-methods", "*");

  if (req.method === "OPTIONS") {
    res.writeHead(204).end();
    return;
  }

  // Body parser helper
  async function readJson() {
    return new Promise((resolve, reject) => {
      let body = "";
      req.on("data", (chunk) => {
        body += chunk;
      });
      req.on("end", () => {
        try {
          resolve(body ? JSON.parse(body) : {});
        } catch (err) {
          reject(err);
        }
      });
      req.on("error", reject);
    });
  }

  // Health check
  if (
    url.pathname === "/auth/v1/health" ||
    url.pathname === "/fixture-health"
  ) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  // JWKS
  if (url.pathname === "/auth/v1/.well-known/jwks.json") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ keys: [jwk] }));
    return;
  }

  // Password Login
  if (
    url.pathname === "/auth/v1/token" &&
    url.searchParams.get("grant_type") === "password"
  ) {
    const { email, password } = await readJson();
    if (email === "testuser@example.test" && password === "Password123!") {
      const sessionId = randomUUID();
      const refreshToken = `ref_${randomUUID()}`;
      activeSessions.set(sessionId, {
        refreshToken,
        subject: testSubject,
        revoked: false,
      });
      const accessToken = await createToken(testSubject, sessionId);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          access_token: accessToken,
          token_type: "bearer",
          expires_in: 3600,
          refresh_token: refreshToken,
          user: { id: testSubject, email },
        }),
      );
      return;
    }
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        error: "invalid_grant",
        error_description: "Invalid login credentials",
      }),
    );
    return;
  }

  // Refresh Token
  if (
    url.pathname === "/auth/v1/token" &&
    url.searchParams.get("grant_type") === "refresh_token"
  ) {
    const { refresh_token } = await readJson();
    let matchedSessionId = null;
    let matchedSession = null;
    for (const [sid, sess] of activeSessions.entries()) {
      if (sess.refreshToken === refresh_token) {
        matchedSessionId = sid;
        matchedSession = sess;
        break;
      }
    }
    if (!matchedSession || matchedSession.revoked) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          error: "invalid_grant",
          error_description:
            "Invalid Refresh Token: Already Revoked or Expired",
        }),
      );
      return;
    }
    const newRefreshToken = `ref_${randomUUID()}`;
    matchedSession.refreshToken = newRefreshToken;
    const newAccessToken = await createToken(
      matchedSession.subject,
      matchedSessionId,
    );
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        access_token: newAccessToken,
        token_type: "bearer",
        expires_in: 3600,
        refresh_token: newRefreshToken,
        user: { id: matchedSession.subject },
      }),
    );
    return;
  }

  // Logout / Revocation
  if (url.pathname === "/auth/v1/logout") {
    const authHeader = req.headers.authorization;
    if (authHeader?.startsWith("Bearer ")) {
      try {
        const token = authHeader.slice(7);
        const { payload } = await jwtVerify(token, jwkSet, {
          issuer: ISSUER,
          audience: AUDIENCE,
        });
        if (payload.session_id && activeSessions.has(payload.session_id)) {
          activeSessions.get(payload.session_id).revoked = true;
        }
      } catch {
        // Token was invalid, still succeed or report
      }
    }
    res.writeHead(204).end();
    return;
  }

  // User details / update
  if (url.pathname === "/auth/v1/user") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({ id: testSubject, email: "testuser@example.test" }),
    );
    return;
  }

  // Recovery endpoints
  if (url.pathname === "/auth/v1/recover") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({}));
    return;
  }
  if (url.pathname === "/auth/v1/verify") {
    const sessionId = randomUUID();
    const refreshToken = `ref_${randomUUID()}`;
    activeSessions.set(sessionId, {
      refreshToken,
      subject: testSubject,
      revoked: false,
    });
    const accessToken = await createToken(testSubject, sessionId, 300);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        access_token: accessToken,
        token_type: "bearer",
        expires_in: 300,
        refresh_token: refreshToken,
        user: { id: testSubject },
      }),
    );
    return;
  }

  // Backend Session Route (/v1/auth/session)
  if (url.pathname === "/v1/auth/session") {
    const authHeader = req.headers.authorization;
    if (!authHeader?.startsWith("Bearer ")) {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }));
      return;
    }
    const token = authHeader.slice(7);
    try {
      const { payload } = await jwtVerify(token, jwkSet, {
        issuer: ISSUER,
        audience: AUDIENCE,
      });
      const sid = payload.session_id;
      const sess = activeSessions.get(sid);
      if (sess && sess.revoked) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }));
        return;
      }
      res.writeHead(200, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      });
      res.end(
        JSON.stringify({
          issuer: ISSUER,
          subject: payload.sub,
          session_id: sid,
          capabilities: ["documents:read", "documents:write", "questions:ask"],
        }),
      );
      return;
    } catch {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }));
      return;
    }
  }

  res.writeHead(404).end();
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(
    `Supabase test fixture server listening on http://127.0.0.1:${PORT}`,
  );
});
