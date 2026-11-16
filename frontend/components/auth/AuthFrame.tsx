import React from "react";
import Link from "next/link";
import Image from "next/image";
import "@/app/auth/auth.css";

export function AuthFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className="knora-auth-frame">
      <aside className="knora-brand-panel" aria-label="Knora">
        <Link href="/" className="knora-brand-mark">
          <Image
            src="/brand/knora-leaf.svg"
            width={18}
            height={18}
            alt=""
            unoptimized
          />
          <span>Knora</span>
        </Link>
        <div className="knora-brand-copy">
          <p className="knora-eyebrow">EVIDENCE-FIRST KNOWLEDGE</p>
          <h2>
            <span>Grounded answers,</span>
            <span>verified by evidence.</span>
          </h2>
          <p className="knora-brand-description">
            Work with your documents, inspect supporting passages, and keep
            every answer tied to its source.
          </p>
          <div className="knora-evidence-cues">
            <span className="knora-evidence-cue knora-evidence-cue--sources">
              SOURCES
            </span>
            <span className="knora-evidence-cue knora-evidence-cue--pages">
              PAGE RANGES
            </span>
            <span className="knora-evidence-cue knora-evidence-cue--provenance">
              PROVENANCE
            </span>
          </div>
        </div>
        <p className="knora-brand-footnote">
          Secure sign-in · You’ll return to Knora after authentication.
        </p>
      </aside>
      <div className="knora-auth-main">
        <div className="knora-auth-card">{children}</div>
      </div>
    </main>
  );
}
