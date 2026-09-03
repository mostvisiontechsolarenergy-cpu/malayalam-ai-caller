import type { Metadata } from "next";
import { headers } from "next/headers";

import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "http";
  const metadataBase = host
    ? new URL(`${protocol}://${host}`)
    : new URL(process.env.PUBLIC_APP_URL ?? "http://localhost:3000");

  return {
    metadataBase,
    title: "Dcreation Maya · Admin Workspace",
    description:
      "Securely manage clients, company knowledge, pricing, offers, FAQs, and Dcreation Maya agents.",
    openGraph: {
      title: "Dcreation Maya",
      description: "Connected Admin Workspace",
      images: [{ url: "/og.png", width: 1792, height: 1024, alt: "Dcreation Maya admin workspace" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "Dcreation Maya",
      description: "Connected Admin Workspace",
      images: ["/og.png"],
    },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
