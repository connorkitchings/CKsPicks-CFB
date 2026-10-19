/**
 * Route-level loading skeleton shown during ISR refreshes and initial render.
 * Mirrors the compact page context, record, collapsed highlights and
 * card grid so the layout doesn't shift when real data arrives.
 */
export default function Loading() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-start justify-between gap-3 px-4 py-4">
          <div className="flex flex-col gap-2">
            <div className="h-6 w-36 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
            <div className="h-3 w-48 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
          </div>
          <div className="h-11 w-11 animate-pulse rounded-md bg-surface-inset motion-reduce:animate-none" />
        </div>
      </header>

      <main id="main-content" tabIndex={-1} aria-busy="true" aria-label="Loading page" className="mx-auto w-full max-w-6xl flex-1 space-y-3 px-4 py-3 sm:py-6">
        <p role="status" className="sr-only">Loading page…</p>
        <div aria-hidden="true" className="h-7 w-36 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
        <div className="rounded-xl border border-line bg-surface-card p-4">
          <div className="mb-2 h-4 w-40 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
          <div className="grid grid-cols-2 gap-2">
            <div className="h-14 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
            <div className="h-14 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
          </div>
        </div>

        <div aria-hidden="true" className="h-11 animate-pulse rounded-xl border border-line bg-surface-card motion-reduce:animate-none" />

        <div className="h-13 animate-pulse rounded-xl border border-line bg-surface-card p-2 motion-reduce:animate-none" />

        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-line bg-surface-card p-4"
            >
              <div className="mb-3 h-3 w-32 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
              <div className="mb-3 space-y-2">
                <div className="h-4 w-44 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
                <div className="h-4 w-44 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
              </div>
              <div className="space-y-2 border-t border-line pt-3">
                <div className="h-4 w-36 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
                <div className="h-4 w-28 animate-pulse rounded bg-surface-inset motion-reduce:animate-none" />
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
