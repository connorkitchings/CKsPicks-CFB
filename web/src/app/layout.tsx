import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeToggle } from "@/components/ThemeToggle";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const siteUrl = "https://ckspicks-cfb.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "CK's Picks · CFB Model Leans",
  description:
    "Weekly model leans for every FBS game — spread and total edges from the CK's Picks college football model.",
  applicationName: "CK's Picks · CFB",
  openGraph: {
    title: "CK's Picks · CFB Model Leans",
    description:
      "Weekly model leans for every FBS game — spread and total edges from the CK's Picks college football model.",
    url: siteUrl,
    siteName: "CK's Picks · CFB",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "CK's Picks · CFB Model Leans",
    description:
      "Weekly model leans for every FBS game — spread and total edges from the CK's Picks college football model.",
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col">
        {children}
        <div className="pointer-events-none fixed bottom-4 right-4 z-50">
          <div className="pointer-events-auto">
            <ThemeToggle />
          </div>
        </div>
      </body>
    </html>
  );
}
