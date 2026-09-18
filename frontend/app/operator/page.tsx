import Link from "next/link";

export default function OperatorPage() {
  return <><h1>Operator observations</h1><p>Read-only views of backend-authorized execution observations.</p><ul><li><Link href="/operator/traces">Question traces</Link></li><li><Link href="/operator/evaluations">Evaluation reports</Link></li><li><Link href="/operator/operations">Operational metrics</Link></li></ul></>;
}
