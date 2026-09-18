import { EvaluationView } from "../../../../components/operator/EvaluationView";
import { isOperatorEvaluation } from "../../../../lib/operator/api";
import { readOperatorBff } from "../../../../lib/operator/bff";

export default async function EvaluationDetailPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  let response: Response;
  try {
    response = await readOperatorBff(`/api/operator/evaluations/${encodeURIComponent(reportId)}`);
  } catch {
    return <p role="status">Evaluation observation unavailable.</p>;
  }
  if (response.status === 401) return <p role="alert">Sign in to inspect this evaluation.</p>;
  if (response.status === 403) return <p role="alert">You are not authorized to inspect this evaluation.</p>;
  if (!response.ok) return <p role="status">Evaluation observation unavailable.</p>;
  const data: unknown = await response.json();
  if (!isOperatorEvaluation(data)) return <p role="status">Evaluation observation unavailable.</p>;
  return <EvaluationView evaluation={data} />;
}
