import { redirect } from "next/navigation";
import { Field } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";

export default async function TracesPage({
  searchParams,
}: {
  searchParams?: Promise<{ traceId?: string; workspaceId?: string }>;
}) {
  const { traceId, workspaceId } = (await searchParams) ?? {};
  if (traceId?.trim())
    redirect(
      `/operator/traces/${encodeURIComponent(traceId.trim())}${workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ""}`,
    );
  return (
    <>
      <PageHeader title="Question traces" />
      <form action="/operator/traces" method="get">
        <Field id="trace-id" label="Trace ID">
          <input name="traceId" required />
        </Field>
        <Field id="trace-workspace-id" label="Workspace ID">
          <input name="workspaceId" />
        </Field>
        <button type="submit">Open trace</button>
      </form>
    </>
  );
}
