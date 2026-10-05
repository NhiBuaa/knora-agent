"use client";

import React, { useState } from "react";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { Menu } from "@/components/ui/Menu";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { readThemePreference, type ThemePreference } from "@/lib/theme";

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
  return (
    <div className="account-menu-root">
      <Menu label={`Account: ${subject}`}>
        <div className="account-menu">
          <span className="account-menu__identity">{subject}</span>
          <button
            type="button"
            role="menuitem"
            onClick={() => setAppearanceOpen(true)}
          >
            Appearance
          </button>
          <form action="/api/auth/logout" method="post">
            <button type="submit" role="menuitem">
              Log out
            </button>
          </form>
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
        <div
          className="kn-appearance-controls"
          onChange={(event) => {
            if (event.target instanceof HTMLSelectElement)
              setAppearancePreference(readThemePreference(event.target.value));
          }}
        >
          <ThemeControl initialPreference={appearancePreference} />
        </div>
        <div className="mt-6 flex justify-end">
          <Button variant="secondary" onClick={() => setAppearanceOpen(false)}>
            Done
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
