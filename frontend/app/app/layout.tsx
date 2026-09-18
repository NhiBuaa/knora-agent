import Link from "next/link";
export default function AppLayout({ children }: { children: React.ReactNode }) { return <main><nav><Link href="/app">Workspace</Link><Link href="/app/documents">Documents</Link><Link href="/app/questions">Questions</Link><form action="/api/auth/logout" method="post"><button type="submit">Log out</button></form></nav>{children}</main>; }
