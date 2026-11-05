// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  isSessionPolicy,
  policyFromClaims,
  SESSION_POLICY_VERSION,
  SessionPolicy,
  tokenDeadlines,
} from "@/lib/auth/session-policy";

describe("SessionPolicy pure bounds and validation", () => {
  it.each([
    [false, 28_800, 1_800],
    [true, 2_592_000, 604_800],
  ] as const)("bounds mode %s", (rememberMe, maximum, idle) => {
    const start = 1_800_000_000;
    const p = policyFromClaims(
      {
        knora_remember_me: rememberMe,
        knora_session_started_at: start,
      },
      start,
    );
    expect(p.policyVersion).toBe(SESSION_POLICY_VERSION);
    expect(p.rememberMe).toBe(rememberMe);
    expect(p.sessionStartedAt).toBe(start);
    expect(p.sessionExpiresAt).toBe(start + maximum);
    expect(tokenDeadlines(p, 300, 9_000_000, start, start)).toEqual({
      expiresAt: start + 300,
      refreshExpiresAt: start + Math.min(idle, maximum),
    });
    expect(isSessionPolicy(p, start)).toBe(true);
    expect(isSessionPolicy(p, start + maximum)).toBe(false);
  });

  it("preserves rememberMe true even near maximum when refresh window is short", () => {
    const start = 1_800_000_000;
    const p = policyFromClaims(
      {
        knora_remember_me: true,
        knora_session_started_at: start,
      },
      start,
    );
    // At near-max: 60s before 30d cap
    const requestedAt = p.sessionExpiresAt - 60;
    const deadlines = tokenDeadlines(p, 50, 600, requestedAt, requestedAt);
    expect(deadlines.expiresAt).toBe(requestedAt + 50);
    expect(deadlines.refreshExpiresAt).toBe(p.sessionExpiresAt);
    expect(isSessionPolicy(p, requestedAt)).toBe(true);
  });

  it("rejects an anchor >30 seconds in the future", () => {
    const now = 1_800_000_000;
    expect(() =>
      policyFromClaims(
        {
          knora_remember_me: false,
          knora_session_started_at: now + 31,
        },
        now,
      ),
    ).toThrow("SESSION_POLICY_INVALID");

    // Anchor within 30s is accepted
    const validFuture = policyFromClaims(
      {
        knora_remember_me: false,
        knora_session_started_at: now + 30,
      },
      now,
    );
    expect(validFuture.sessionStartedAt).toBe(now + 30);
  });

  it.each([
    ["missing rememberMe", { knora_session_started_at: 1_800_000_000 }],
    [
      "string bool",
      { knora_remember_me: "true", knora_session_started_at: 1_800_000_000 },
    ],
    ["missing start", { knora_remember_me: false }],
    [
      "string start",
      { knora_remember_me: false, knora_session_started_at: "1800000000" },
    ],
    [
      "NaN start",
      { knora_remember_me: false, knora_session_started_at: Number.NaN },
    ],
    [
      "Infinity start",
      {
        knora_remember_me: false,
        knora_session_started_at: Number.POSITIVE_INFINITY,
      },
    ],
    ["zero start", { knora_remember_me: false, knora_session_started_at: 0 }],
    [
      "negative start",
      { knora_remember_me: false, knora_session_started_at: -1 },
    ],
    [
      "floating point start",
      { knora_remember_me: false, knora_session_started_at: 1_800_000_000.5 },
    ],
    [
      "expired anchor",
      { knora_remember_me: false, knora_session_started_at: 1_000_000_000 },
    ],
  ])("rejects invalid claims: %s", (_label, claims) => {
    const now = 1_800_000_000;
    expect(() =>
      policyFromClaims(claims as Record<string, unknown>, now),
    ).toThrow("SESSION_POLICY_INVALID");
  });

  it("isSessionPolicy validates object shape, safe integers, and rejects tampered cap", () => {
    const now = 1_800_000_000;
    const valid: SessionPolicy = {
      policyVersion: 1,
      rememberMe: false,
      sessionStartedAt: now,
      sessionExpiresAt: now + 28_800,
    };
    expect(isSessionPolicy(valid, now)).toBe(true);

    // Tampered cap
    expect(
      isSessionPolicy({ ...valid, sessionExpiresAt: now + 28_801 }, now),
    ).toBe(false);
    expect(
      isSessionPolicy({ ...valid, sessionExpiresAt: now + 2_592_000 }, now),
    ).toBe(false);

    // Wrong version
    expect(isSessionPolicy({ ...valid, policyVersion: 2 }, now)).toBe(false);

    // Not an object or null
    expect(isSessionPolicy(null, now)).toBe(false);
    expect(isSessionPolicy(undefined, now)).toBe(false);
    expect(isSessionPolicy("session", now)).toBe(false);
    expect(isSessionPolicy([], now)).toBe(false);

    // Expired
    expect(isSessionPolicy(valid, now + 28_800)).toBe(false);
    expect(isSessionPolicy(valid, now + 28_801)).toBe(false);
  });

  it.each([
    ["zero expiresIn", 0, 1800],
    ["negative expiresIn", -1, 1800],
    ["expiresIn > 300", 301, 1800],
    ["string expiresIn", "300", 1800],
    ["zero refreshExpiresIn", 300, 0],
    ["negative refreshExpiresIn", 300, -1],
    ["string refreshExpiresIn", 300, "1800"],
    ["NaN expiresIn", Number.NaN, 1800],
    ["Infinity refreshExpiresIn", 300, Number.POSITIVE_INFINITY],
  ])(
    "rejects invalid token response durations: %s",
    (_label, expiresIn, refreshExpiresIn) => {
      const now = 1_800_000_000;
      const policy: SessionPolicy = {
        policyVersion: 1,
        rememberMe: false,
        sessionStartedAt: now,
        sessionExpiresAt: now + 28_800,
      };
      expect(() =>
        tokenDeadlines(policy, expiresIn, refreshExpiresIn, now, now),
      ).toThrow("SESSION_TOKEN_RESPONSE_INVALID");
    },
  );

  it("handles latency and rejects responses arriving after calculated deadline", () => {
    const start = 1_800_000_000;
    const policy: SessionPolicy = {
      policyVersion: 1,
      rememberMe: false,
      sessionStartedAt: start,
      sessionExpiresAt: start + 28_800,
    };
    const requestedAt = start;
    // Response arrived 305s after request (past 300s access token lifespan)
    const arrival = start + 305;
    expect(() =>
      tokenDeadlines(policy, 300, 1800, requestedAt, arrival),
    ).toThrow("SESSION_TOKEN_RESPONSE_INVALID");
  });

  it("rejects token responses where expiresAt > refreshExpiresAt", () => {
    const start = 1_800_000_000;
    const policy: SessionPolicy = {
      policyVersion: 1,
      rememberMe: false,
      sessionStartedAt: start,
      sessionExpiresAt: start + 28_800,
    };
    // refresh_expires_in (100) is shorter than expires_in (200)
    expect(() => tokenDeadlines(policy, 200, 100, start, start)).toThrow(
      "SESSION_TOKEN_RESPONSE_INVALID",
    );
  });
});
