import React from "react";
import { AuthOutcome } from "@/components/auth/AuthOutcome";

export default function FailedPage() {
  return <AuthOutcome outcome="failed" />;
}
