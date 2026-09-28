import Link from "next/link";
import { PageHeader } from "@/components/ui/PageHeader";
import { Field } from "@/components/ui/Field";

export default function OperatorPage() {
  return (
    <>
      <PageHeader
        title="Operator observations"
        description="Workspace-scoped traces, evaluations, and operational observations."
      />
      <ul>
        <li>
          <Link href="/operator/traces">Question traces</Link>
        </li>
        <li>
          <Link href="/operator/evaluations">Evaluation reports</Link>
        </li>
        <li>
          <Link href="/operator/operations">Operational metrics</Link>
        </li>
      </ul>
      <form action="/operator/operations" method="get">
        <h2>Select a workspace</h2>
        <Field id="operator-workspace-id" label="Workspace ID">
          <input name="workspaceId" required />
        </Field>
        <button type="submit">Open Workspace observations</button>
      </form>
    </>
  );
}
