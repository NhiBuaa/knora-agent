import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
export default async function HomePage(props: {
  searchParams?: Promise<{ "signed-out"?: string; state?: string }>;
}) {
  const session = await getSession();
  if (!session) {
    const params = await props.searchParams;
    const signedOut = params?.["signed-out"];
    if (signedOut) {
      redirect(`/api/auth/login?signed-out=${encodeURIComponent(signedOut)}`);
    }
    redirect("/api/auth/login");
  }
  redirect("/workspaces");
}
