import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";

const siteUrl = "https://ckspicks-cfb.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "CK's Picks · V5 College Football Forecasts",
  description:
    "V5 college football forecasts, team ratings, and season performance.",
  applicationName: "CK's Picks · CFB",
  openGraph: {
    title: "CK's Picks · V5 College Football Forecasts",
    description:
      "V5 college football forecasts, team ratings, and season performance.",
    url: siteUrl,
    siteName: "CK's Picks · CFB",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "CK's Picks · V5 College Football Forecasts",
    description:
      "V5 college football forecasts, team ratings, and season performance.",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

/**
 * Pre-paint theme init: must run before React hydration to avoid a flash.
 * Reads localStorage.theme; defaults to system (honors prefers-color-scheme).
 */
const themeScript = `(function(){try{var t=localStorage.getItem('theme');var d=t==='dark'||((!t||t==='system')&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col"><SiteNav />{children}</body>
    </html>
  );
}
