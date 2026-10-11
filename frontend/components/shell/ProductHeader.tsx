import React from "react";
import Link from "next/link";
import Image from "next/image";
import { routes } from "@/lib/navigation/routes";

export type ProductHeaderProps = {
  activeSection: "conversations" | "documents" | "operator";
  workspaceId: string | null;
  canOpenOperator: boolean;
  account: React.ReactNode;
};

export function ProductHeader({
  activeSection,
  workspaceId,
  canOpenOperator,
  account,
}: ProductHeaderProps) {
  const destinations = [
    {
      section: "conversations",
      label: "Conversations",
      href: workspaceId ? routes.conversations(workspaceId) : "/workspaces",
    },
    {
      section: "documents",
      label: "Documents",
      href: workspaceId ? routes.documents(workspaceId) : "/workspaces",
    },
    ...(canOpenOperator
      ? [{ section: "operator", label: "Operator", href: "/operator" }]
      : []),
  ];
  return (
    <header className="kn-product-header grid h-16 grid-cols-[1fr_auto_1fr] items-center border-b border-border bg-surface px-6 text-text-primary max-md:h-auto max-md:min-h-16 max-md:grid-cols-[1fr_auto] max-md:gap-x-3 max-md:gap-y-1 max-md:px-4 max-md:pt-3">
      <Link
        href="/workspaces"
        className="kn-product-brand flex items-center gap-2.5 font-display text-xl font-semibold"
      >
        <Image
          src="/brand/knora-leaf.svg"
          width={18}
          height={18}
          alt=""
          unoptimized
        />
        <span>Knora</span>
      </Link>
      <nav
        aria-label="Primary navigation"
        className="flex items-center gap-[18px] text-sm font-medium max-md:col-span-2 max-md:row-start-2 max-md:justify-center max-md:gap-2.5"
      >
        {destinations.map(({ section, label, href }) => (
          <Link
            key={section}
            href={href}
            aria-current={activeSection === section ? "page" : undefined}
            className={
              activeSection === section
                ? "kn-product-nav-link border-action text-action-text"
                : "kn-product-nav-link border-transparent text-text-muted"
            }
          >
            {label}
          </Link>
        ))}
      </nav>
      <div className="flex items-center justify-end gap-3 max-md:col-start-2 max-md:row-start-1">
        {account}
      </div>
    </header>
  );
}
