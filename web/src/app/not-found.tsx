import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "@/components/PageShell";
import { ThemeReapply } from "@/components/ThemeReapply";
import { PageHeading } from "@/components/ui/PageHeading";

export const metadata: Metadata = { title: "Page not found", robots: { index: false } };

const LINK_CLASS =
  "inline-flex min-h-11 items-center justify-center rounded-lg border border-line bg-surface-card px-4 text-sm font-semibold text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent";

/** Site-wide 404, rendered inside the root layout so the app bar, theme and base styles apply. */
export default function NotFound() {
  return (
    <PageShell width="narrow" mainClassName="space-y-5 py-6 sm:py-10">
      <ThemeReapply />
      <PageHeading title="Page not found">
        <p>This page could not be found. It may have moved, or the address may be mistyped.</p>
      </PageHeading>
      <nav aria-label="Where to go next" className="flex flex-wrap gap-3">
        <Link href="/" className={LINK_CLASS}>Games</Link>
        <Link href="/teams" className={LINK_CLASS}>Ratings</Link>
      </nav>
    </PageShell>
  );
}
