import { QuestionWorkspace } from "@/components/questions/QuestionWorkspace";
import { getSession } from "@/lib/auth/session";
export default async function QuestionsPage() {
  const session = await getSession();
  const workspaceId = session?.workspaceIds[0];
  if (!workspaceId) return <p role="alert">No workspace is available for this session.</p>;
  return <QuestionWorkspace workspaceId={workspaceId} />;
}
