import React from "react";
import { AuthFrame } from "@/components/auth/AuthFrame";
import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <AuthFrame>
      <RegisterForm />
    </AuthFrame>
  );
}
