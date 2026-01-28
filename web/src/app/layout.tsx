import type { Metadata } from "next";
import "./globals.css";
import { ClientErrorBoundary } from "./client-error-boundary";

export const metadata: Metadata = {
  title: "CoPoly — Construction Document Intelligence",
  description:
    "Visual document retrieval for construction projects. Search across drawings, RFIs, submittals, and specs with AI-powered understanding.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <ClientErrorBoundary>
          {children}
        </ClientErrorBoundary>
      </body>
    </html>
  );
}
