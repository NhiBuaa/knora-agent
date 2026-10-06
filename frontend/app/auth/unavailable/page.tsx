import React from "react";
import { AuthOutcome } from "@/components/auth/AuthOutcome";

export default function UnavailablePage() {
  return <AuthOutcome outcome="unavailable" />;
}
