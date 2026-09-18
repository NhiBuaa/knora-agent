import type { KnoraApiPath, KnoraApiResponseFor, OperatorEvaluationResponse, OperatorOperationsResponse, OperatorTraceResponse } from "../../generated/knora-openapi";

export type OperatorSession = { accessToken: string; workspaceId: string };
export type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export function sessionFromCookies(values: { accessToken?: string; workspaceId?: string }): OperatorSession | null {
  if (!values.accessToken || !values.workspaceId) return null;
  return { accessToken: values.accessToken, workspaceId: values.workspaceId };
}

export async function forwardOperatorRequest(
  url: string,
  session: Pick<OperatorSession, "accessToken">,
  fetcher: Fetcher = fetch,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.accessToken}`);
  headers.set("Accept", "application/json");
  return fetcher(url, { ...init, headers, body: undefined });
}

export async function readOperatorResource<P extends KnoraApiPath>(
  path: P,
  session: OperatorSession,
  init?: RequestInit,
): Promise<{ response: Response; data?: KnoraApiResponseFor<P> }> {
  const baseUrl = process.env.KNORA_BACKEND_URL ?? "http://127.0.0.1:8000";
  const url = `${baseUrl}${path}`;
  const response = await forwardOperatorRequest(url, session, fetch, init);
  if (!response.ok) return { response };
  return { response, data: (await response.json()) as KnoraApiResponseFor<P> };
}

export function isOperatorEvaluation(value: unknown): value is OperatorEvaluationResponse {
  return !!value && typeof value === "object" && "report_id" in value && "availability" in value;
}

export function isOperatorOperations(value: unknown): value is OperatorOperationsResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as { metrics?: unknown; histograms?: unknown };
  return isRecord(candidate.metrics) && isRecord(candidate.histograms);
}

export function isOperatorTrace(value: unknown): value is OperatorTraceResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as { trace_id?: unknown; candidates?: unknown };
  return typeof candidate.trace_id === "string" && Array.isArray(candidate.candidates);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
