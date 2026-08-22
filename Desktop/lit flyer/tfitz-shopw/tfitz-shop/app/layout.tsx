import type { Metadata } from "next";
import "./globals.css";
import { BRAND } from "@/lib/config";

export const metadata: Metadata = {
  title: `${BRAND.name} — ${BRAND.tagline}`,
  description: `Thrifted pieces from ${BRAND.name}, ${BRAND.city}. Hand-picked, quality checked, priced fair.`,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-paper-100 text-ink-900">
        {children}
      </body>
    </html>
  );
}
