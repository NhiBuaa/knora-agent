import type { Metadata } from "next";
import localFont from "next/font/local";
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

export const metadata: Metadata = { title: "Knora", description: "Workspace knowledge assistant" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={`${inter.variable} ${robotoSlab.variable}`}><body>{children}</body></html>;
}
