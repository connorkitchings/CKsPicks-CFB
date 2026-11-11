import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { ThemeScript } from "@/components/ThemeScript";
import { SiteNav } from "@/components/SiteNav";
import { MatchupLinksProvider } from "@/components/MatchupLinks";
import { isMatchupEnabled } from "@/lib/matchup-gate";
import { BRAND_FULL, SITE_URL } from "@/lib/brand";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: `${BRAND_FULL} · V5 College Football Forecasts`,
  description:
    "V5 college football forecasts, team ratings, and season performance.",
  applicationName: BRAND_FULL,
  openGraph: {
    title: `${BRAND_FULL} · V5 College Football Forecasts`,
    description:
      "V5 college football forecasts, team ratings, and season performance.",
    url: SITE_URL,
    siteName: BRAND_FULL,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: `${BRAND_FULL} · V5 College Football Forecasts`,
    description:
      "V5 college football forecasts, team ratings, and season performance.",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      data-scroll-behavior="smooth"
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased scroll-smooth`}
    >
      <head>
        <meta name="color-scheme" content="light dark" />
        <ThemeScript />
      </head>
      <body className="min-h-full flex flex-col pb-[calc(3.5rem+env(safe-area-inset-bottom)+0.5rem)] sm:pb-0">
        <MatchupLinksProvider enabled={isMatchupEnabled()}>
          <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface-card focus:px-3 focus:py-3 focus:text-sm focus:font-medium focus:text-ink focus:shadow-lg">Skip to main content</a>
          <SiteNav />
          {children}
        </MatchupLinksProvider>
      </body>
    </html>
  );
}
