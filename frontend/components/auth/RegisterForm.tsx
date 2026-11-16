"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EyeIcon, EyeOffIcon } from "@/components/auth/AuthIcons";

export function RegisterForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!email || !password || !passwordConfirm) {
      setError("Please complete all required fields.");
      return;
    }

    if (password !== passwordConfirm) {
      setError("Passwords do not match. Check your password confirmation.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
          displayName: displayName.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          error?: string;
        };
        setError(data.error || "Account couldn’t be created.");
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
      <h1>Create your Knora account</h1>
      <p className="knora-auth-description">
        Start with a secure account, then create or restore the workspace you
        need. If you previously had an account, registering with the same email
        keeps your workspace data intact.
      </p>

      {error && (
        <div className="knora-notice" role="alert">
          <strong>Account couldn’t be created</strong>
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

        <div className="knora-field">
          <label htmlFor="display-name" className="knora-label">
            Display name (optional)
          </label>
          <input
            id="display-name"
            name="displayName"
            type="text"
            autoComplete="name"
            className="knora-input"
            placeholder="Your name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        <div className="knora-field">
          <label htmlFor="password" className="knora-label">
            Password
          </label>
          <div className="knora-password-wrapper">
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
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

        <div className="knora-field">
          <label htmlFor="password-confirm" className="knora-label">
            Confirm password
          </label>
          <div className="knora-password-wrapper">
            <input
              id="password-confirm"
              name="passwordConfirm"
              type={showConfirmPassword ? "text" : "password"}
              autoComplete="new-password"
              className="knora-input"
              placeholder="••••••••••••"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              disabled={isSubmitting}
              required
            />
            <button
              type="button"
              className="knora-password-toggle"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              aria-label={
                showConfirmPassword
                  ? "Hide confirm password"
                  : "Show confirm password"
              }
              title={
                showConfirmPassword
                  ? "Hide confirm password"
                  : "Show confirm password"
              }
            >
              {showConfirmPassword ? <EyeIcon /> : <EyeOffIcon />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          className="knora-button-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Creating account..." : "Create account"}
        </button>

        <p className="knora-disclaimer">
          Account registration is handled by the secure identity service. Knora
          never receives your password.
        </p>

        <p className="knora-secondary">
          Already have an account? <Link href="/auth/login">Sign in</Link>
        </p>
      </form>
    </>
  );
}
