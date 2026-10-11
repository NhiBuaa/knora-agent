import React from "react";
import Link from "next/link";
import Image from "next/image";
import "./auth-outcome.css";

const outcomes = {
  unavailable: {
    badge: "Sign-in unavailable",
    heading: "Sign-in is temporarily unavailable",
    description:
      "Knora can’t start the secure sign-in flow right now. Your credentials have not been submitted.",
    retry: "Try again",
    footnote:
      "If this continues, the authentication service may be unavailable or misconfigured.",
  },
  failed: {
    badge: "Authentication failed",
    heading: "Couldn’t sign you in",
    description:
      "The authentication response couldn’t be verified. Start a new sign-in attempt to continue.",
    retry: "Try signing in again",
    footnote: "No workspace data was opened from this failed attempt.",
  },
} as const;

export function AuthOutcome({ outcome }: { outcome: keyof typeof outcomes }) {
  const content = outcomes[outcome];
  return (
    <main className="kn-auth-outcome bg-surface text-text-primary">
      <aside
        className="kn-auth-outcome__brand bg-surface-subtle"
        aria-label="Knora"
      >
        <div className="kn-auth-outcome__mark flex items-center gap-3 font-display text-[22px] font-semibold">
          <Image
            src="/brand/knora-leaf.svg"
            width={18}
            height={18}
            alt=""
            unoptimized
          />
          <span>Knora</span>
        </div>
        <div className="kn-auth-outcome__copy">
          <p className="text-[11px] leading-[13px] font-semibold text-text-muted">
            EVIDENCE-FIRST KNOWLEDGE
          </p>
          <h2 className="mt-[17px] font-display text-[38px] leading-[48px]">
            <span className="block">Grounded answers,</span>
            <span className="block">verified by evidence.</span>
          </h2>
          <p className="mt-4 max-w-[420px] text-base leading-[25px] text-text-muted">
            Work with your documents, inspect supporting passages, and keep
            every answer tied to its source.
          </p>
          <div className="mt-[30px] flex flex-wrap gap-2 text-[11px] font-semibold">
            <span className="kn-auth-outcome__cue kn-auth-outcome__cue--sources">
              SOURCES
            </span>
            <span className="kn-auth-outcome__cue kn-auth-outcome__cue--pages">
              PAGE RANGES
            </span>
            <span className="kn-auth-outcome__cue border border-border bg-surface">
              PROVENANCE
            </span>
          </div>
        </div>
        <p className="kn-auth-outcome__secure text-xs text-text-muted">
          Secure sign-in · You’ll return to Knora after authentication.
        </p>
      </aside>
      <div className="kn-auth-outcome__content">
        <span className="kn-auth-outcome__cue kn-auth-outcome__cue--sources text-[11px] font-semibold">
          {content.badge}
        </span>
        <h1 className="font-display text-[30px]">{content.heading}</h1>
        <p className="text-[15px] leading-[23px] text-text-muted">
          {content.description}
        </p>
        <Link
          href="/api/auth/login"
          className="kn-button inline-flex min-h-[42px] items-center justify-center rounded-lg bg-action px-5 text-sm font-semibold text-action-foreground hover:bg-action-hover active:bg-action-active"
          prefetch={false}
        >
          {content.retry}
        </Link>
        <p className="text-xs leading-[18px] text-text-muted">
          {content.footnote}
        </p>
      </div>
    </main>
  );
}
