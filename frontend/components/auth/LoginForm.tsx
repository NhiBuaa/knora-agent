"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EyeIcon, EyeOffIcon } from "@/components/auth/AuthIcons";

export function LoginForm({
  signedOutReason: initialSignedOutReason,
  reset: initialReset,
}: {
  signedOutReason?: string;
  reset?: boolean;
} = {}) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [signedOutReason, setSignedOutReason] = useState<string | undefined>(
    () => {
      if (initialSignedOutReason !== undefined) return initialSignedOutReason;
      if (typeof window !== "undefined") {
        try {
          return (
            new URLSearchParams(window.location.search).get("signed-out") ||
            undefined
          );
        } catch {
          return undefined;
        }
      }
      return undefined;
    },
  );

  const [reset, setReset] = useState<boolean | undefined>(() => {
    if (initialReset !== undefined) return initialReset;
    if (typeof window !== "undefined") {
      try {
        return new URLSearchParams(window.location.search).get("reset") === "1";
      } catch {
        return undefined;
      }
    }
    return undefined;
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const params = new URLSearchParams(window.location.search);
        if (initialSignedOutReason === undefined) {
          setSignedOutReason(params.get("signed-out") || undefined);
        }
        if (initialReset === undefined) {
          setReset(params.get("reset") === "1");
        }
      } catch {
        // ignore
      }
    }
  }, [initialSignedOutReason, initialReset]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          error?: string;
        };
        setError(
          data.error === "Invalid credentials"
            ? "Sign-in details weren’t accepted. Check your email and password."
            : data.error || "Sign-in details weren’t accepted.",
        );
        setIsSubmitting(false);
        return;
      }

      const data = (await response.json().catch(() => ({}))) as {
        redirect?: string;
      };
      const target = data.redirect || "/workspaces";
      router.push(target);
    } catch {
      setError("Unable to connect to the authentication service. Try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <h1>Sign in to Knora</h1>
      <p className="knora-auth-description">Continue to your workspace.</p>

      {reset && (
        <div className="knora-notice" role="status">
          <strong>Password updated</strong>
          <p>Your password has been changed. Sign in with your new password.</p>
        </div>
      )}

      {signedOutReason === "retryable" && (
        <div className="knora-notice" role="alert">
          <strong>Session revocation warning</strong>
          <p>
            Your local session was ended, but provider session revocation could
            not be confirmed. Please close all browser windows or sign in again.
          </p>
        </div>
      )}

      {error && (
        <div className="knora-notice" role="alert">
          <strong>Sign-in details weren’t accepted</strong>
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
            autoComplete="username email"
            className="knora-input"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isSubmitting}
            required
            autoFocus
          />
        </div>

        <div className="knora-field">
          <div className="knora-label-row">
            <label htmlFor="password" className="knora-label">
              Password
            </label>
            <Link href="/auth/forgot-password" className="knora-link">
              Forgot your password?
            </Link>
          </div>
          <div className="knora-password-wrapper">
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              className="knora-input"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              required
            />
            <button
              type="button"
              className="knora-password-toggle"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              title={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeIcon /> : <EyeOffIcon />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          className="knora-button-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>

        <p className="knora-disclaimer">
          Your credentials are handled by the secure identity service, not by
          Knora application code.
        </p>

        <p className="knora-secondary">
          New to Knora? <Link href="/auth/register">Create account</Link>
        </p>
      </form>
    </>
  );
}
