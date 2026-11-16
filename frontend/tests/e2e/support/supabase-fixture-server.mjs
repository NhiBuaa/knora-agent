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
let currentPassword = "Password123!";
let refreshCallCount = 0;

const mockWorkspaces = [
  {
    id: "ws-default-workspace",
    name: "Default Workspace",
    owner_id: testSubject,
    archived: false,
    created_at: new Date().toISOString(),
    revision: 1,
  },
];
const mockDocumentsMap = new Map();
const mockConversationsMap = new Map();
const mockTurnsMap = new Map();

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

  // Fixture stats & barrier controls
  if (url.pathname === "/fixture-stats/refresh-count") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ count: refreshCallCount }));
    return;
  }
  if (
    url.pathname === "/fixture-stats/reset-refresh-count" ||
    url.pathname === "/fixture-stats/reset"
  ) {
    refreshCallCount = 0;
    mockWorkspaces.length = 0;
    mockWorkspaces.push({
      id: "ws-default-workspace",
      name: "Default Workspace",
      owner_id: testSubject,
      archived: false,
      created_at: new Date().toISOString(),
      revision: 1,
    });
    mockDocumentsMap.clear();
    mockConversationsMap.clear();
    mockTurnsMap.clear();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", count: 0 }));
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
    if (
      (email === "testuser@example.test" || email?.includes("expiring")) &&
      (password === "Password123!" || password === currentPassword)
    ) {
      const sessionId = randomUUID();
      const refreshToken = `ref_${randomUUID()}`;
      activeSessions.set(sessionId, {
        refreshToken,
        subject: testSubject,
        revoked: false,
      });
      const expiresIn = email.includes("concurrent-expiring")
        ? 35
        : email.includes("expiring")
          ? 5
          : 3600;
      const accessToken = await createToken(testSubject, sessionId, expiresIn);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          access_token: accessToken,
          token_type: "bearer",
          expires_in: expiresIn,
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

  // Signup / Registration
  if (url.pathname === "/auth/v1/signup") {
    const { email, password } = await readJson();
    if (!email || !password || password.length < 8) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          error: "validation_failed",
          msg: "Password should be at least 8 characters",
        }),
      );
      return;
    }
    const newSubject = randomUUID();
    const sessionId = randomUUID();
    const refreshToken = `ref_${randomUUID()}`;
    activeSessions.set(sessionId, {
      refreshToken,
      subject: newSubject,
      revoked: false,
    });
    const accessToken = await createToken(newSubject, sessionId, 3600);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        access_token: accessToken,
        token_type: "bearer",
        expires_in: 3600,
        refresh_token: refreshToken,
        user: { id: newSubject, email },
      }),
    );
    return;
  }

  // Refresh Token
  if (
    url.pathname === "/auth/v1/token" &&
    url.searchParams.get("grant_type") === "refresh_token"
  ) {
    refreshCallCount++;
    // Add a small 150ms delay barrier so concurrent callers overlap
    await new Promise((r) => setTimeout(r, 150));

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
        const scope = url.searchParams.get("scope");
        if (scope === "global") {
          for (const sess of activeSessions.values()) {
            if (sess.subject === payload.sub) {
              sess.revoked = true;
            }
          }
        } else if (
          payload.session_id &&
          activeSessions.has(payload.session_id)
        ) {
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
    if (req.method === "PUT") {
      const { password } = await readJson();
      if (password) {
        currentPassword = password;
      }
    }
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

  // Central Auth Guard Helper for resource endpoints
  async function authenticateRequest() {
    const authHeader = req.headers.authorization;
    if (!authHeader?.startsWith("Bearer ")) {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }));
      return null;
    }
    const token = authHeader.slice(7);
    try {
      const { payload } = await jwtVerify(token, jwkSet, {
        issuer: ISSUER,
        audience: AUDIENCE,
      });
      const sid = payload.session_id;
      if (sid && activeSessions.has(sid)) {
        const sess = activeSessions.get(sid);
        if (sess.revoked) {
          res.writeHead(401, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }));
          return null;
        }
      }
      return payload;
    } catch {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }));
      return null;
    }
  }

  // Workspace Authorization Helper
  function authorizeWorkspace(wsId, subject) {
    const ws = mockWorkspaces.find((w) => w.id === wsId);
    if (!ws) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { code: "WORKSPACE_NOT_FOUND" } }));
      return null;
    }
    if (ws.owner_id && ws.owner_id !== subject) {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { code: "WORKSPACE_ACCESS_DENIED" } }));
      return null;
    }
    return ws;
  }

  // Backend Session Route (/v1/auth/session)
  if (url.pathname === "/v1/auth/session") {
    const payload = await authenticateRequest();
    if (!payload) return;
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(
      JSON.stringify({
        issuer: ISSUER,
        subject: payload.sub,
        session_id: payload.session_id,
        capabilities: ["documents:read", "documents:write", "questions:ask"],
      }),
    );
    return;
  }

  // Knora Workspaces API (/v1/workspaces/resolve)
  if (url.pathname === "/v1/workspaces/resolve" && req.method === "POST") {
    const payload = await authenticateRequest();
    if (!payload) return;
    const body = await readJson();

    let userWorkspaces = mockWorkspaces.filter(
      (w) => w.owner_id === payload.sub,
    );
    if (userWorkspaces.length === 0) {
      const autoWs = {
        id: `ws-${payload.sub.slice(0, 8)}`,
        name: "Default Workspace",
        owner_id: payload.sub,
        archived: false,
        created_at: new Date().toISOString(),
        revision: 1,
      };
      mockWorkspaces.push(autoWs);
      userWorkspaces = [autoWs];
    }

    const targetWorkspace =
      userWorkspaces.find((w) => w.id === body.hint_id && !w.archived) ||
      userWorkspaces.find((w) => !w.archived) ||
      null;
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        state: targetWorkspace ? "ACTIVE" : "NO_ACTIVE_WORKSPACE",
        workspace: targetWorkspace,
      }),
    );
    return;
  }

  // Knora Workspaces List & Creation (/v1/workspaces)
  if (url.pathname === "/v1/workspaces") {
    const payload = await authenticateRequest();
    if (!payload) return;

    if (req.method === "GET") {
      const userWorkspaces = mockWorkspaces.filter(
        (w) => w.owner_id === payload.sub,
      );
      const archivedParam = url.searchParams.get("archived") === "true";
      const filtered = userWorkspaces.filter(
        (w) => w.archived === archivedParam,
      );
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          items: filtered,
          next_cursor: null,
        }),
      );
      return;
    }

    if (req.method === "POST") {
      const { name } = await readJson();
      const newWs = {
        id: `ws-${randomUUID().slice(0, 8)}`,
        name: name || "New Workspace",
        owner_id: payload.sub,
        archived: false,
        created_at: new Date().toISOString(),
        revision: 1,
      };
      mockWorkspaces.push(newWs);
      res.writeHead(201, { "Content-Type": "application/json" });
      res.end(JSON.stringify(newWs));
      return;
    }
  }

  // Knora Single Workspace (/v1/workspaces/:workspaceId)
  const singleWsMatch = url.pathname.match(/^\/v1\/workspaces\/([^/]+)$/);
  if (singleWsMatch && req.method === "GET") {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(singleWsMatch[1]);
    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(ws));
    return;
  }

  // Knora Workspace Conversations & Documents sub-routes
  const convMatch = url.pathname.match(
    /^\/v1\/workspaces\/([^/]+)\/conversations$/,
  );
  if (convMatch) {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(convMatch[1]);
    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;

    if (!mockConversationsMap.has(wsId)) {
      mockConversationsMap.set(wsId, []);
    }
    const convs = mockConversationsMap.get(wsId);

    if (req.method === "GET") {
      const archivedParam = url.searchParams.get("archived") === "true";
      const filtered = convs.filter((c) => c.archived === archivedParam);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ items: filtered, next_cursor: null }));
      return;
    }

    if (req.method === "POST") {
      const convId = `conv-${randomUUID().slice(0, 8)}`;
      const newConv = {
        id: convId,
        workspace_id: wsId,
        title: "New conversation",
        title_source: "default",
        archived: false,
        revision: 1,
        updated_at: new Date().toISOString(),
      };
      convs.unshift(newConv);
      res.writeHead(201, { "Content-Type": "application/json" });
      res.end(JSON.stringify(newConv));
      return;
    }
  }

  // Single conversation (/v1/workspaces/:workspaceId/conversations/:conversationId)
  const singleConvMatch = url.pathname.match(
    /^\/v1\/workspaces\/([^/]+)\/conversations\/([^/]+)(?:\/(archive|restore))?$/,
  );
  if (singleConvMatch && !url.pathname.includes("/turns")) {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(singleConvMatch[1]);
    const convId = decodeURIComponent(singleConvMatch[2]);
    const action = singleConvMatch[3];

    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;

    const convs = mockConversationsMap.get(wsId) || [];
    const conv = convs.find((c) => c.id === convId && c.workspace_id === wsId);
    if (!conv) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          error: {
            code: "CONVERSATION_NOT_FOUND",
            message: "Conversation not found",
          },
        }),
      );
      return;
    }
    if (action === "archive") {
      conv.archived = true;
      conv.revision++;
      conv.updated_at = new Date().toISOString();
    }
    if (action === "restore") {
      conv.archived = false;
      conv.revision++;
      conv.updated_at = new Date().toISOString();
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(conv));
    return;
  }

  // Conversation Turns (/v1/workspaces/:workspaceId/conversations/:conversationId/turns)
  const turnsMatch = url.pathname.match(
    /^\/v1\/workspaces\/([^/]+)\/conversations\/([^/]+)\/turns$/,
  );
  if (turnsMatch) {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(turnsMatch[1]);
    const convId = decodeURIComponent(turnsMatch[2]);

    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;

    // Ràng buộc conversation phải thuộc workspace đã authorize
    const convs = mockConversationsMap.get(wsId) || [];
    const conv = convs.find((c) => c.id === convId && c.workspace_id === wsId);
    if (!conv) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          error: {
            code: "CONVERSATION_NOT_FOUND",
            message: "Conversation not found",
          },
        }),
      );
      return;
    }

    const turnKey = `${wsId}:${convId}`;
    if (!mockTurnsMap.has(turnKey)) {
      mockTurnsMap.set(turnKey, []);
    }
    const turns = mockTurnsMap.get(turnKey);

    if (req.method === "GET") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ items: turns, next_cursor: null }));
      return;
    }

    if (req.method === "POST") {
      const { question } = await readJson();
      const sequence = turns.length + 1;
      const turnId = `turn-${randomUUID().slice(0, 8)}`;

      // Update conversation title
      conv.title = (question || "Conversation")
        .replace(/\s+/g, " ")
        .slice(0, 80);
      conv.title_source = "question";
      conv.updated_at = new Date().toISOString();

      // Check uploaded documents to cite
      const docs = mockDocumentsMap.get(wsId) || [];
      const sourceDoc = docs[0];
      const docId = sourceDoc
        ? sourceDoc.document_id
        : `doc-${randomUUID().slice(0, 8)}`;
      const docName = sourceDoc
        ? sourceDoc.source_name
        : "Teacher Manh - Guidelines 2024.pdf";

      const citation = {
        evidence_id: `evi-${randomUUID().slice(0, 8)}`,
        document_id: docId,
        document_version_id: `ver-${randomUUID().slice(0, 8)}`,
        source_name: docName,
        source_key: docName,
        content_checksum: "sha256:guidelines2024checksum",
        start_line: 42,
        end_line: 58,
        page_start: 3,
        page_end: 4,
        heading_path: [
          "Quy định trình bày báo cáo",
          "Cấu trúc các chương gợi ý",
        ],
        excerpt:
          "Báo cáo đề tài tốt nghiệp được cấu trúc thành 5 chương chính: Chương 1: Giới thiệu đề tài; Chương 2: Cơ sở lý thuyết; Chương 3: Phân tích & thiết kế; Chương 4: Cài đặt & thử nghiệm; Chương 5: Kết luận & hướng phát triển.",
      };

      const answerText = `Theo tài liệu hướng dẫn (**${docName}**), báo cáo tốt nghiệp thường được gợi ý cấu trúc thành **5 chương** chính:

1. **Chương 1: Mở đầu / Giới thiệu** – Trình bày bối cảnh, tính cấp thiết, mục tiêu và phạm vi đề tài.
2. **Chương 2: Cơ sở lý thuyết và công nghệ liên quan** – Tổng quan kiến thức lý thuyết, nền tảng công nghệ và các công cụ sử dụng.
3. **Chương 3: Phân tích và thiết kế hệ thống** – Đặc tả yêu cầu, biểu đồ ca sử dụng (Use case), kiến trúc hệ thống và thiết kế cơ sở dữ liệu.
4. **Chương 4: Hiện thực và kết quả thử nghiệm** – Cài đặt ứng dụng, hiện thực các tính năng chính, giao diện và đánh giá kết quả thực nghiệm.
5. **Chương 5: Kết luận và hướng phát triển** – Tổng kết các đóng góp đạt được, hạn chế còn tồn đọng và đề xuất định hướng phát triển tiếp theo.`;

      const newTurn = {
        id: turnId,
        conversation_id: convId,
        sequence,
        question: question || "",
        status: "answered",
        stage: null,
        error_code: null,
        result: {
          answer: answerText,
          citations: [citation],
          decision: "ANSWER",
          refusal_reason: null,
          trace_id: `tr-${randomUUID().slice(0, 8)}`,
          workspace_id: wsId,
        },
      };

      turns.push(newTurn);

      res.writeHead(201, { "Content-Type": "application/json" });
      res.end(JSON.stringify(newTurn));
      return;
    }
  }

  // Single Turn details (/v1/workspaces/:workspaceId/conversations/:conversationId/turns/:turnId)
  const singleTurnMatch = url.pathname.match(
    /^\/v1\/workspaces\/([^/]+)\/conversations\/([^/]+)\/turns\/([^/]+)$/,
  );
  if (singleTurnMatch && req.method === "GET") {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(singleTurnMatch[1]);
    const convId = decodeURIComponent(singleTurnMatch[2]);
    const turnId = decodeURIComponent(singleTurnMatch[3]);

    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;

    // Ràng buộc conversation phải thuộc workspace đã authorize
    const convs = mockConversationsMap.get(wsId) || [];
    const conv = convs.find((c) => c.id === convId && c.workspace_id === wsId);
    if (!conv) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          error: {
            code: "CONVERSATION_NOT_FOUND",
            message: "Conversation not found",
          },
        }),
      );
      return;
    }

    const turnKey = `${wsId}:${convId}`;
    const turns = mockTurnsMap.get(turnKey) || [];
    const turn = turns.find(
      (t) => t.id === turnId && t.conversation_id === convId,
    );
    if (!turn) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          error: { code: "TURN_NOT_FOUND", message: "Turn not found" },
        }),
      );
      return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(turn));
    return;
  }

  const docMatch = url.pathname.match(/^\/v1\/workspaces\/([^/]+)\/documents$/);
  if (docMatch) {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(docMatch[1]);
    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;

    if (!mockDocumentsMap.has(wsId)) {
      mockDocumentsMap.set(wsId, []);
    }
    const docs = mockDocumentsMap.get(wsId);

    if (req.method === "GET") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ documents: docs, next_cursor: null }));
      return;
    }

    if (req.method === "POST") {
      const docId = `doc-${randomUUID().slice(0, 8)}`;
      const jobId = `job-${randomUUID().slice(0, 8)}`;
      const versionId = `ver-${randomUUID().slice(0, 8)}`;

      let sourceName = "Uploaded-Document.pdf";
      const chunks = [];
      for await (const chunk of req) {
        chunks.push(chunk);
      }
      const rawBody = Buffer.concat(chunks).toString("latin1");
      const filenameMatch = rawBody.match(/filename="([^"]+)"/i);
      if (filenameMatch) {
        sourceName = filenameMatch[1];
      }

      const newDoc = {
        document_id: docId,
        source_name: sourceName,
        source_key: sourceName,
        workspace_id: wsId,
        archived: false,
        revision: 1,
        serving_state: "current",
        ingestion_status: "succeeded",
        indexing_status: "succeeded",
        embedding_readiness: "ready",
        lexical_readiness: "ready",
        answer_availability: "available",
      };
      docs.unshift(newDoc);

      res.writeHead(201, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          document_id: docId,
          document_version_id: versionId,
          ingestion_job_id: jobId,
          status: "succeeded",
          submission_outcome: "created",
        }),
      );
      return;
    }
  }

  // Ingestion Jobs polling route
  const jobMatch = url.pathname.match(
    /^\/v1\/workspaces\/([^/]+)\/ingestion-jobs\/([^/]+)$/,
  );
  if (jobMatch && req.method === "GET") {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(jobMatch[1]);
    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;

    const jobId = jobMatch[2];
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        ingestion_job_id: jobId,
        status: "succeeded",
        indexing_status: "succeeded",
        poll_after_seconds: 1,
      }),
    );
    return;
  }

  // Single document actions
  const singleDocMatch = url.pathname.match(
    /^\/v1\/workspaces\/([^/]+)\/documents\/([^/]+)(?:\/(archive|unarchive))?$/,
  );
  if (singleDocMatch) {
    const payload = await authenticateRequest();
    if (!payload) return;
    const wsId = decodeURIComponent(singleDocMatch[1]);
    const docId = decodeURIComponent(singleDocMatch[2]);
    const action = singleDocMatch[3];

    const ws = authorizeWorkspace(wsId, payload.sub);
    if (!ws) return;

    const docs = mockDocumentsMap.get(wsId) || [];
    let doc = docs.find((d) => d.document_id === docId);
    if (!doc) {
      doc = {
        document_id: docId,
        source_name: "Document",
        source_key: "Document",
        workspace_id: wsId,
        archived: false,
        revision: 1,
        serving_state: "current",
        ingestion_status: "succeeded",
        indexing_status: "succeeded",
      };
      docs.push(doc);
    }
    if (action === "archive") doc.archived = true;
    if (action === "unarchive") doc.archived = false;
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(doc));
    return;
  }

  res.writeHead(404).end();
});

server.on("error", (err) => {
  console.error(
    `Supabase test fixture server error on port ${PORT}:`,
    err.message,
  );
  process.exit(1);
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(
    `Supabase test fixture server listening on http://127.0.0.1:${PORT}`,
  );
});
