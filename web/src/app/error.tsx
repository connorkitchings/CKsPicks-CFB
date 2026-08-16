"use client";

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
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">
      <div className="rounded-xl border border-loss-line bg-loss-soft p-5 text-sm text-loss">
        <h2 className="mb-1 text-base font-semibold">Couldn&rsquo;t load this week.</h2>
        <p className="mb-3">
          The database query failed. This is usually transient (Neon cold start
          or a blip). Try again in a moment.
        </p>
        <button
          type="button"
          onClick={reset}
          className="rounded-md bg-loss px-3 py-1.5 text-xs font-semibold text-white transition-opacity hover:opacity-90"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
