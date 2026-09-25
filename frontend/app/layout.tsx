import React from "react";
import type { Metadata } from "next";
import localFont from "next/font/local";
import { cookies } from "next/headers";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { readThemePreference, THEME_COOKIE_NAME } from "@/lib/theme";
import "./globals.css";

const inter = localFont({
  src: "../public/fonts/inter-latin-vietnamese.woff2",
  variable: "--font-inter",
  display: "swap",
  weight: "100 900",
});
const robotoSlab = localFont({
  src: "../public/fonts/roboto-slab-latin-vietnamese.woff2",
  variable: "--font-roboto-slab",
  display: "swap",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Knora",
  description: "Workspace knowledge assistant",
};
export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const preference = readThemePreference(
    (await cookies()).get(THEME_COOKIE_NAME)?.value,
  );
  return (
    <html
      lang="en"
      className={`${inter.variable} ${robotoSlab.variable}`}
      data-theme={preference === "system" ? undefined : preference}
    >
      <body>
        <ThemeControl initialPreference={preference} />
        {children}
      </body>
    </html>
  );
}
