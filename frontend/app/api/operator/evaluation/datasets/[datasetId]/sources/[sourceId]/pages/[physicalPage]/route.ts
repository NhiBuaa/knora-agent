import { proxyEvaluationPath } from "../../../../../../../_evaluation-proxy";

export async function GET(
  request: Request,
  {
    params,
  }: {
    params: Promise<{
      datasetId: string;
      sourceId: string;
      physicalPage: string;
    }>;
  },
) {
  const { datasetId, sourceId, physicalPage } = await params;
  if (!/^[1-9]\d*$/.test(physicalPage))
    return Response.json({ detail: "INVALID_PAGE" }, { status: 400 });
  return proxyEvaluationPath(
    request,
    (workspaceId) =>
      `/v1/workspaces/${workspaceId}/evaluation/datasets/${encodeURIComponent(datasetId)}/sources/${encodeURIComponent(sourceId)}/pages/${physicalPage}`,
    ["documents:read"],
  );
}
