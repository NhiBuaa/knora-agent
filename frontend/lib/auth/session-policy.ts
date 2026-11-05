export type SessionPolicy = {
  policyVersion: 1;
  rememberMe: boolean;
  sessionStartedAt: number;
  sessionExpiresAt: number;
};

export const SESSION_POLICY_VERSION = 1;
export const NORMAL_IDLE_TIMEOUT_SECONDS = 1_800; // 30 minutes
export const NORMAL_MAX_LIFESPAN_SECONDS = 28_800; // 8 hours
export const REMEMBER_ME_IDLE_TIMEOUT_SECONDS = 604_800; // 7 days
export const REMEMBER_ME_MAX_LIFESPAN_SECONDS = 2_592_000; // 30 days
export const ACCESS_TOKEN_MAX_LIFESPAN_SECONDS = 300; // 5 minutes
export const REFRESH_THRESHOLD_SECONDS = 30;
export const ANCHOR_FUTURE_TOLERANCE_SECONDS = 30;

export function policyFromClaims(
  claims: Record<string, unknown>,
  now: number,
): SessionPolicy {
  if (typeof claims.knora_remember_me !== "boolean") {
    throw new Error("SESSION_POLICY_INVALID");
  }
  const startedAt = claims.knora_session_started_at;
  if (
    typeof startedAt !== "number" ||
    !Number.isSafeInteger(startedAt) ||
    startedAt <= 0 ||
    startedAt > now + ANCHOR_FUTURE_TOLERANCE_SECONDS
  ) {
    throw new Error("SESSION_POLICY_INVALID");
  }

  const maxLifespan = claims.knora_remember_me
    ? REMEMBER_ME_MAX_LIFESPAN_SECONDS
    : NORMAL_MAX_LIFESPAN_SECONDS;
  const sessionExpiresAt = startedAt + maxLifespan;

  if (!Number.isSafeInteger(sessionExpiresAt) || sessionExpiresAt <= now) {
    throw new Error("SESSION_POLICY_INVALID");
  }

  return {
    policyVersion: SESSION_POLICY_VERSION,
    rememberMe: claims.knora_remember_me,
    sessionStartedAt: startedAt,
    sessionExpiresAt,
  };
}

export function isSessionPolicy(
  value: unknown,
  now: number,
): value is SessionPolicy {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  if (candidate.policyVersion !== SESSION_POLICY_VERSION) {
    return false;
  }
  if (typeof candidate.rememberMe !== "boolean") {
    return false;
  }
  const startedAt = candidate.sessionStartedAt;
  if (
    typeof startedAt !== "number" ||
    !Number.isSafeInteger(startedAt) ||
    startedAt <= 0 ||
    startedAt > now + ANCHOR_FUTURE_TOLERANCE_SECONDS
  ) {
    return false;
  }

  const expectedMax = candidate.rememberMe
    ? REMEMBER_ME_MAX_LIFESPAN_SECONDS
    : NORMAL_MAX_LIFESPAN_SECONDS;
  const expectedCap = startedAt + expectedMax;

  const expiresAt = candidate.sessionExpiresAt;
  if (
    typeof expiresAt !== "number" ||
    !Number.isSafeInteger(expiresAt) ||
    expiresAt !== expectedCap ||
    expiresAt <= now
  ) {
    return false;
  }

  return true;
}

export function tokenDeadlines(
  policy: SessionPolicy,
  expiresIn: unknown,
  refreshExpiresIn: unknown,
  requestedAt: number,
  now: number,
): { expiresAt: number; refreshExpiresAt: number } {
  if (!isSessionPolicy(policy, now)) {
    throw new Error("SESSION_TOKEN_RESPONSE_INVALID");
  }
  if (
    typeof requestedAt !== "number" ||
    !Number.isSafeInteger(requestedAt) ||
    requestedAt <= 0 ||
    requestedAt > now + ANCHOR_FUTURE_TOLERANCE_SECONDS
  ) {
    throw new Error("SESSION_TOKEN_RESPONSE_INVALID");
  }
  if (
    typeof expiresIn !== "number" ||
    !Number.isSafeInteger(expiresIn) ||
    expiresIn <= 0 ||
    expiresIn > ACCESS_TOKEN_MAX_LIFESPAN_SECONDS
  ) {
    throw new Error("SESSION_TOKEN_RESPONSE_INVALID");
  }
  if (
    typeof refreshExpiresIn !== "number" ||
    !Number.isSafeInteger(refreshExpiresIn) ||
    refreshExpiresIn <= 0
  ) {
    throw new Error("SESSION_TOKEN_RESPONSE_INVALID");
  }

  const idle = policy.rememberMe
    ? REMEMBER_ME_IDLE_TIMEOUT_SECONDS
    : NORMAL_IDLE_TIMEOUT_SECONDS;
  const rawExpiresAt = requestedAt + expiresIn;
  const rawRefreshExpiresAt = Math.min(
    requestedAt + refreshExpiresIn,
    requestedAt + idle,
    policy.sessionExpiresAt,
  );

  const expiresAt = Math.min(rawExpiresAt, policy.sessionExpiresAt);
  const refreshExpiresAt = rawRefreshExpiresAt;

  if (
    !Number.isSafeInteger(expiresAt) ||
    !Number.isSafeInteger(refreshExpiresAt)
  ) {
    throw new Error("SESSION_TOKEN_RESPONSE_INVALID");
  }

  if (
    expiresAt <= now ||
    refreshExpiresAt <= now ||
    expiresAt > refreshExpiresAt
  ) {
    throw new Error("SESSION_TOKEN_RESPONSE_INVALID");
  }

  return { expiresAt, refreshExpiresAt };
}
