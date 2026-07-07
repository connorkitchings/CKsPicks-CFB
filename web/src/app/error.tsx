"use client";

/**
 * Route-level error boundary. Catches throws from the server component
 * (typically Neon connection failures) and offers a retry without a full
 * reload. `reset` is provided by Next.js and re-runs the segment.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">
      <div className="rounded-xl border border-rose-300 bg-rose-50 p-5 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200">
        <h2 className="mb-1 text-base font-semibold">Couldn&rsquo;t load this week.</h2>
        <p className="mb-3">
          The database query failed. This is usually transient (Neon cold start
          or a blip). Try again in a moment.
        </p>
        <pre className="mb-3 overflow-x-auto whitespace-pre-wrap rounded-md bg-white/60 p-2 text-[11px] dark:bg-black/40">
          {error.message || "Unknown error"}
          {error.digest ? `\ndigest: ${error.digest}` : ""}
        </pre>
        <button
          type="button"
          onClick={reset}
          className="rounded-md bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-rose-700"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
