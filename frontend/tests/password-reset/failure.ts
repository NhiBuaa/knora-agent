export function passwordResetFailure(stage: string, error: unknown): Error {
  const category =
    error instanceof Error && "matcherResult" in error
      ? "ASSERTION"
      : error instanceof Error && error.name === "TimeoutError"
        ? "TIMEOUT"
        : error instanceof Error &&
            error.message.startsWith("apiRequestContext.")
          ? "HTTP_REQUEST"
          : "ERROR";
  return new Error(`PASSWORD_RESET_REGRESSION_${stage}_${category}`);
}
