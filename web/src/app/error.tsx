"use client";

import { Notice } from "@/components/ui/Notice";

/**
 * Route-level error boundary. Catches throws from the server component
 * (typically Neon connection failures) and offers a retry without a full
 * reload. `reset` is provided by Next.js and re-runs the segment.
 */
export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">
      <Notice
        tone="error"
        action={
          <button
            type="button"
            onClick={reset}
            className="min-h-11 rounded-md border border-loss bg-surface-card px-4 py-2 text-sm font-semibold text-loss transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-accent"
          >
            Try again
          </button>
        }
      >
        <h1 className="mb-1 text-lg font-semibold">Couldn&rsquo;t load this page.</h1>
        <p>This page is temporarily unavailable. Try again in a moment.</p>
      </Notice>
    </main>
  );
}
