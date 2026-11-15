"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthFrame } from "@/components/auth/AuthFrame";

export default function NewPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!password || !passwordConfirm) {
      setError("Please fill in both password fields.");
      return;
    }

    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/recovery/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password, passwordConfirm }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          error?: string;
          redirect?: string;
        };
        if (data.redirect) {
          router.push(data.redirect);
          return;
        }
        setError(data.error || "Your password couldn’t be updated.");
        setIsSubmitting(false);
        return;
      }

      const data = (await response.json().catch(() => ({}))) as {
        redirect?: string;
      };
      router.push(data.redirect || "/auth/login?reset=1");
    } catch {
      setError("Unable to update password. Check your connection.");
      setIsSubmitting(false);
    }
  }

  return (
    <AuthFrame>
      <h1>Choose a new password</h1>
      <p className="knora-auth-description">
        Set a new password for your Knora account.
      </p>

      {error && (
        <div className="knora-notice" role="alert">
          <strong>Your password couldn’t be updated</strong>
          <p>{error}</p>
        </div>
      )}

      <form className="knora-form" onSubmit={handleSubmit} noValidate>
        <div className="knora-field">
          <label htmlFor="new-password" className="knora-label">
            New password
          </label>
          <div className="knora-password-wrapper">
            <input
              id="new-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              className="knora-input"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              required
              autoFocus
            />
            <button
              type="button"
              className="knora-password-toggle"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </div>

        <div className="knora-field">
          <label htmlFor="password-confirm" className="knora-label">
            Confirm new password
          </label>
          <div className="knora-password-wrapper">
            <input
              id="password-confirm"
              name="passwordConfirm"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              className="knora-input"
              placeholder="••••••••••••"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              disabled={isSubmitting}
              required
            />
          </div>
        </div>

        <button
          type="submit"
          className="knora-button-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Resetting password..." : "Reset password"}
        </button>

        <p className="knora-disclaimer">
          After resetting your password, sign in again with the new password.
        </p>

        <p className="knora-secondary">
          <Link href="/auth/login">Back to sign in</Link>
        </p>
      </form>
    </AuthFrame>
  );
}
