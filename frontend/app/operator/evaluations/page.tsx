import { redirect } from "next/navigation";
import { Field } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";

export default async function EvaluationsPage({
  searchParams,
}: {
  searchParams?: Promise<{ reportId?: string; workspaceId?: string }>;
}) {
  const { reportId, workspaceId } = (await searchParams) ?? {};
  if (reportId?.trim())
    redirect(
      `/operator/evaluations/${encodeURIComponent(reportId.trim())}${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  return (
    <>
      <PageHeader title="Evaluations" />
      <form action="/operator/evaluations" method="get">
        <Field id="report-id" label="Report ID">
          <input name="reportId" required />
        </Field>
        <Field id="report-workspace-id" label="Workspace ID">
          <input name="workspaceId" />
        </Field>
        <button type="submit">Open report</button>
      </form>
    </>
  );
}
