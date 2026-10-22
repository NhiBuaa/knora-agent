import { proxyEvaluationPath } from "../../../../_evaluation-proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ datasetId: string }> },
) {
  const { datasetId } = await params;
  const version = new URL(request.url).searchParams.get("version");
  if (
    version !== null &&
    (!/^[1-9]\d*$/.test(version) || !Number.isSafeInteger(Number(version)))
  ) {
    return Response.json(
      { detail: "INVALID_VERSION" },
      { status: 400, headers: { "cache-control": "no-store" } },
    );
  }
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/gold${version === null ? "" : `?version=${version}`}`,
  );
}
