"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthFrame } from "@/components/auth/AuthFrame";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!email || !email.includes("@")) {
      setError("Enter a valid email address and try again.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/recovery/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          error?: string;
        };
        setError(
          data.error || "Unable to send verification code. Try again later.",
        );
        setIsSubmitting(false);
        return;
      }

      router.push(`/auth/reset-code?email=${encodeURIComponent(email.trim())}`);
    } catch {
      setError("Unable to process request. Check your connection.");
      setIsSubmitting(false);
    }
  }

  return (
    <AuthFrame>
      <h1>Forgot your password?</h1>
      <p className="knora-auth-description">
        Enter the email for your account. If an account exists, we’ll send a
        6-digit verification code.
      </p>

      {error && (
        <div className="knora-notice" role="alert">
          <strong>Request not completed</strong>
          <p>{error}</p>
        </div>
      )}

      <form className="knora-form" onSubmit={handleSubmit} noValidate>
        <div className="knora-field">
          <label htmlFor="email" className="knora-label">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            className="knora-input"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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
          {isSubmitting ? "Sending code..." : "Send verification code"}
        </button>

        <p className="knora-disclaimer">
          For privacy, Knora won’t confirm whether an account exists for this
          email.
        </p>

        <p className="knora-secondary">
          Remembered it? <Link href="/auth/login">Back to sign in</Link>
        </p>
      </form>
    </AuthFrame>
  );
}
