import type {
  KnoraApiPath,
  KnoraApiResponseFor,
} from "@/generated/knora-openapi";

export type RequestOptions = RequestInit & { accessToken?: string };
export async function knoraRequest<P extends KnoraApiPath>(
  path: P,
  init: RequestOptions = {},
): Promise<KnoraApiResponseFor<P>> {
  const base =
    process.env.KNORA_API_URL ??
    process.env.NEXT_PUBLIC_KNORA_API_URL ??
    "http://localhost:8000";
  const headers = new Headers(init.headers);
  if (init.accessToken)
    headers.set("authorization", `Bearer ${init.accessToken}`);
  if (init.body && !headers.has("content-type"))
    headers.set("content-type", "application/json");
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!response.ok)
    throw new KnoraApiError(response.status, await safeJson(response));
  return (await response.json()) as KnoraApiResponseFor<P>;
}
export class KnoraApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`Knora API request failed: ${status}`);
  }
}
async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
