"use client";

import React, { useState } from "react";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { Menu } from "@/components/ui/Menu";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { LeafLoading } from "@/components/ui/LeafLoading";
import { type ThemePreference } from "@/lib/theme";
import { clearConversationPanelPreferences } from "@/lib/conversations/panel-preferences";
import "./account-menu.css";

export function AccountMenu({
  subject,
  themePreference,
}: {
  subject: string;
  themePreference: ThemePreference;
}) {
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [appearancePreference, setAppearancePreference] =
    useState(themePreference);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  return (
    <div
      className="account-menu-root"
      data-logging-out={isLoggingOut ? "true" : undefined}
    >
      {isLoggingOut && (
        <div
          role="progressbar"
          aria-label="Signing out"
          aria-valuemin={0}
          aria-valuemax={100}
          className="kn-logout-progress-bar"
        />
      )}
      <Menu label={`Account: ${subject}`} locked={isLoggingOut}>
        <div className="account-menu">
          <h2 className="account-menu__title">Account</h2>
          <span className="account-menu__status">
            {isLoggingOut ? "Signing out..." : "Signed in"}
          </span>
          <span className="account-menu__identity">{subject}</span>
          <div className="account-menu__divider" />
          <button
            type="button"
            role="menuitem"
            aria-label="Appearance"
            className="account-menu__theme"
            disabled={isLoggingOut}
            aria-disabled={isLoggingOut ? "true" : undefined}
            onClick={() => {
              if (!isLoggingOut) setAppearanceOpen(true);
            }}
          >
            <span>Theme</span>
            <span className="account-menu__preference">
              {appearancePreference === "system"
                ? "System"
                : appearancePreference === "dark"
                  ? "Dark"
                  : "Light"}
            </span>
          </button>
          <form
            action="/api/auth/logout"
            method="post"
            onSubmit={(event) => {
              if (isLoggingOut) {
                event.preventDefault();
                return;
              }
              setIsLoggingOut(true);
              clearConversationPanelPreferences();
            }}
          >
            <button
              type="submit"
              role="menuitem"
              className="account-menu__logout"
              disabled={isLoggingOut}
              aria-busy={isLoggingOut ? "true" : undefined}
              data-loading={isLoggingOut ? "true" : undefined}
            >
              {isLoggingOut ? (
                <span className="account-menu__logout-loading">
                  <LeafLoading
                    compact
                    label="Signing out"
                    className="account-menu__logout-spinner"
                  />
                  <span>Signing out...</span>
                </span>
              ) : (
                <span>Log out</span>
              )}
            </button>
          </form>
          {isLoggingOut && (
            <span role="status" className="sr-only">
              Signing out, please wait...
            </span>
          )}
        </div>
      </Menu>
      <span aria-hidden="true" className="kn-account-avatar">
        {Array.from(subject.trim()).slice(0, 2).join("").toUpperCase() || "?"}
      </span>
      <Dialog
        open={appearanceOpen}
        title="Appearance"
        onClose={() => setAppearanceOpen(false)}
      >
        <ThemeControl
          initialPreference={appearancePreference}
          onPreferenceChange={setAppearancePreference}
        />
        <div className="mt-6 flex justify-end">
          <Button variant="secondary" onClick={() => setAppearanceOpen(false)}>
            Done
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
