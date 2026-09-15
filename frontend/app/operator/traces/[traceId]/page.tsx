import { TraceView } from "../../../../components/operator/TraceView";
import { isOperatorTrace } from "../../../../lib/operator/api";
import { readOperatorBff } from "../../../../lib/operator/bff";

export default async function TraceDetailPage({ params }: { params: { traceId: string } }) {
  const response = await readOperatorBff(`/api/operator/traces/${encodeURIComponent(params.traceId)}`);
  if (response.status === 401) return <p role="alert">Sign in to inspect this trace.</p>;
  if (response.status === 403) return <p role="alert">You are not authorized to inspect this trace.</p>;
  if (!response.ok) return <p role="status">Trace observation unavailable.</p>;
  const data: unknown = await response.json();
  if (!isOperatorTrace(data)) return <p role="status">Trace observation unavailable.</p>;
  return <TraceView trace={data} />;
}
