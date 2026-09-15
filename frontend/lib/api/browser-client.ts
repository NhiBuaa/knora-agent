export async function browserRequest(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`/api${path}`, { ...init, headers: { "content-type": "application/json", ...init.headers }, cache: "no-store" });
}
