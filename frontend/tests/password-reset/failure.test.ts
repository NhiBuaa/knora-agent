import { describe, expect, it } from "vitest";
import { passwordResetFailure } from "./failure";

describe("password reset failure reporting", () => {
  it.each([
    [
      Object.assign(new Error("secret password OTP token"), {
        matcherResult: { actual: "secret" },
      }),
      "ASSERTION",
    ],
    [
      Object.assign(new Error("secret password OTP token"), {
        name: "TimeoutError",
      }),
      "TIMEOUT",
    ],
    [
      new Error("apiRequestContext.get: secret password OTP token"),
      "HTTP_REQUEST",
    ],
    [new Error("secret password OTP token"), "ERROR"],
    [null, "ERROR"],
  ])("retains only a safe category and stage (case %#)", (error, category) => {
    expect(passwordResetFailure("LOGIN", error).message).toBe(
      `PASSWORD_RESET_REGRESSION_LOGIN_${category}`,
    );
    expect(passwordResetFailure("LOGIN", error).cause).toBeUndefined();
  });
});
