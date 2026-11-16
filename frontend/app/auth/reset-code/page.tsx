"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthFrame } from "@/components/auth/AuthFrame";

function ResetCodeForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get("email") || "";

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resendStatus, setResendStatus] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    const sanitized = code.trim();
    if (!sanitized || sanitized.length !== 6) {
      setError("Please enter the 6-digit verification code.");
      return;
    }

    if (!email) {
      setError("Missing email reference. Please start again.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/recovery/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), code: sanitized }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          error?: string;
        };
        setError(
          data.error || "Check the code or request a new one, then try again.",
        );
        setIsSubmitting(false);
        return;
      }

      const data = (await response.json().catch(() => ({}))) as {
        redirect?: string;
      };
      router.push(data.redirect || "/auth/new-password");
    } catch {
      setError("Unable to verify code. Check your connection.");
      setIsSubmitting(false);
    }
  }

  async function handleResend() {
    if (!email) return;
    setResendStatus("Resending code...");
    try {
      await fetch("/api/auth/recovery/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      setResendStatus("New code sent if account exists.");
    } catch {
      setResendStatus("Failed to resend code.");
    }
  }

  return (
    <>
      <h1>Enter verification code</h1>
      <p className="knora-auth-description">
        {email
          ? `If an account exists, we sent a 6-digit verification code to ${email}.`
          : "Enter the 6-digit verification code sent to your email."}
      </p>

      {error && (
        <div className="knora-notice" role="alert">
          <strong>Code couldn’t be verified</strong>
          <p>{error}</p>
        </div>
      )}

      {resendStatus && (
        <div className="knora-notice knora-notice-success">
          <p>{resendStatus}</p>
        </div>
      )}

      <form className="knora-form" onSubmit={handleSubmit} noValidate>
        <div className="knora-field">
          <label htmlFor="code" className="knora-label">
            Six-digit reset code
          </label>
          <input
            id="code"
            name="code"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            autoComplete="one-time-code"
            className="knora-input"
            placeholder="123456"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            disabled={isSubmitting}
            required
            autoFocus
          />
        </div>

        <button
          type="submit"
          className="knora-button-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Verifying..." : "Verify code"}
        </button>

        <div className="knora-otp-utilities">
          <button
            type="button"
            className="knora-link"
            onClick={handleResend}
            style={{
              background: "none",
              border: 0,
              padding: 0,
              cursor: "pointer",
            }}
          >
            Resend code
          </button>
          <Link href="/auth/forgot-password" className="knora-link">
            Use a different email
          </Link>
        </div>

        <p className="knora-secondary">
          <Link href="/auth/login">Back to sign in</Link>
        </p>
      </form>
    </>
  );
}

export default function ResetCodePage() {
  return (
    <AuthFrame>
      <Suspense fallback={<div>Loading...</div>}>
        <ResetCodeForm />
      </Suspense>
    </AuthFrame>
  );
}
