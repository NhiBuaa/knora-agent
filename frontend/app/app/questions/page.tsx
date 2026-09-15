import { QuestionWorkspace } from "@/components/questions/QuestionWorkspace";
export default function QuestionsPage() { return <QuestionWorkspace workspaceId={process.env.NEXT_PUBLIC_DEFAULT_WORKSPACE_ID ?? "default"} />; }
