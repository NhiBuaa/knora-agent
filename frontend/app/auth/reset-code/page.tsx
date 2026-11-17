"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthFrame } from "@/components/auth/AuthFrame";

function ResetCodeForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get("email") || "";

  const [digits, setDigits] = useState<string[]>(["", "", "", "", "", ""]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [resendCountdown, setResendCountdown] = useState<number>(0);

  const inputRefs = [
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
  ];
  const autoSubmittedRef = useRef(false);

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = setInterval(() => {
      setResendCountdown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCountdown]);

  const submitCode = async (codeToVerify: string) => {
    if (isSubmitting || autoSubmittedRef.current) return;
    if (codeToVerify.length !== 6) {
      setError("Please enter the 6-digit verification code.");
      return;
    }
    if (!email) {
      setError("Missing email reference. Please start again.");
      return;
    }

    autoSubmittedRef.current = true;
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/auth/recovery/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), code: codeToVerify }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          error?: string;
        };
        setError(
          data.error || "Check the code or request a new one, then try again.",
        );
        setIsSubmitting(false);
        autoSubmittedRef.current = false;
        setDigits(["", "", "", "", "", ""]);
        inputRefs[0].current?.focus();
        return;
      }

      const data = (await response.json().catch(() => ({}))) as {
        redirect?: string;
      };
      router.push(data.redirect || "/auth/new-password");
    } catch {
      setError("Unable to verify code. Check your connection.");
      setIsSubmitting(false);
      autoSubmittedRef.current = false;
    }
  };

  const applyDigits = (value: string, startIdx = 0) => {
    const clean = value.replace(/\D/g, "");
    if (!clean) return;

    const newDigits = [...digits];
    for (let i = 0; i < clean.length && startIdx + i < 6; i++) {
      newDigits[startIdx + i] = clean[i];
    }
    setDigits(newDigits);

    const fullCode = newDigits.join("");
    const nextIdx = Math.min(startIdx + clean.length, 5);
    inputRefs[nextIdx].current?.focus();
    inputRefs[nextIdx].current?.select();

    if (fullCode.length === 6 && !autoSubmittedRef.current) {
      submitCode(fullCode);
    }
  };

  const handleDigitChange = (
    e: React.ChangeEvent<HTMLInputElement>,
    index: number,
  ) => {
    const raw = e.target.value;
    const clean = raw.replace(/\D/g, "");

    if (clean.length > 1) {
      applyDigits(clean, index);
      return;
    }

    const singleDigit = clean.slice(-1);
    const newDigits = [...digits];
    newDigits[index] = singleDigit;
    setDigits(newDigits);

    if (singleDigit && index < 5) {
      inputRefs[index + 1].current?.focus();
      inputRefs[index + 1].current?.select();
    }

    const fullCode = newDigits.join("");
    if (fullCode.length === 6 && !autoSubmittedRef.current) {
      submitCode(fullCode);
    }
  };

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement>,
    index: number,
  ) => {
    if (e.key === "Backspace") {
      if (!digits[index] && index > 0) {
        e.preventDefault();
        const newDigits = [...digits];
        newDigits[index - 1] = "";
        setDigits(newDigits);
        inputRefs[index - 1].current?.focus();
      } else if (digits[index]) {
        const newDigits = [...digits];
        newDigits[index] = "";
        setDigits(newDigits);
      }
    } else if (e.key === "ArrowLeft" && index > 0) {
      e.preventDefault();
      inputRefs[index - 1].current?.focus();
      inputRefs[index - 1].current?.select();
    } else if (e.key === "ArrowRight" && index < 5) {
      e.preventDefault();
      inputRefs[index + 1].current?.focus();
      inputRefs[index + 1].current?.select();
    }
  };

  const handlePaste = (
    e: React.ClipboardEvent<HTMLInputElement>,
    index: number,
  ) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text");
    applyDigits(pasted, index);
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fullCode = digits.join("").trim();
    if (fullCode.length !== 6) {
      setError("Please enter the 6-digit verification code.");
      return;
    }
    submitCode(fullCode);
  };

  const handleResend = async () => {
    if (!email || resendCountdown > 0) return;
    setResendStatus("Resending code...");
    try {
      await fetch("/api/auth/recovery/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      setResendStatus("New code sent if account exists.");
      setResendCountdown(60);
    } catch {
      setResendStatus("Failed to resend code.");
    }
  };

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
          <label htmlFor="otp-digit-0" className="knora-label">
            Six-digit reset code
          </label>
          <div
            className={`knora-otp-digits ${error ? "knora-otp-digits--error" : ""}`}
            role="group"
            aria-label="Verification code digits"
          >
            {digits.map((digit, idx) => (
              <input
                key={idx}
                ref={inputRefs[idx]}
                id={`otp-digit-${idx}`}
                name={idx === 0 ? "code" : `code-digit-${idx}`}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={idx === 0 ? 6 : 1}
                autoComplete={idx === 0 ? "one-time-code" : "off"}
                className={`knora-otp-digit ${digit ? "knora-otp-digit--filled" : ""}`}
                value={digit}
                onChange={(e) => handleDigitChange(e, idx)}
                onKeyDown={(e) => handleKeyDown(e, idx)}
                onPaste={(e) => handlePaste(e, idx)}
                onFocus={(e) => e.target.select()}
                disabled={isSubmitting}
                required
                autoFocus={idx === 0}
                aria-label={`Digit ${idx + 1} of 6`}
                data-otp-index={idx}
              />
            ))}
          </div>
        </div>

        <button
          type="submit"
          aria-label="Verify code"
          className="knora-button-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Verifying..." : "Verify code"}
        </button>

        <div className="knora-otp-utilities">
          <button
            type="button"
            className="knora-link knora-resend-btn"
            onClick={handleResend}
            disabled={resendCountdown > 0}
          >
            {resendCountdown > 0
              ? `Resend code (${resendCountdown}s)`
              : "Resend code"}
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
