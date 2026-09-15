import Link from "next/link";
export default function WorkspacePage() { return <section><h1>Workspace</h1><p>Manage documents and ask questions in your selected workspace.</p><Link href="/app/documents">Manage documents</Link> · <Link href="/app/questions">Ask a question</Link></section>; }
