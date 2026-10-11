import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
export default async function HomePage(_props: {
  searchParams?: Promise<{ "signed-out"?: string; state?: string }>;
}) {
  const session = await getSession();
  if (!session) redirect("/api/auth/login");
  redirect("/workspaces");
}
