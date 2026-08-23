/**
 * Route-level loading skeleton shown during ISR refreshes and initial render.
 * Mirrors the shape of Header + RecordBanner + the matchup-centric GameRow
 * list so the layout doesn't shift when real data arrives.
 */
export default function Loading() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-start justify-between gap-3 px-4 py-4">
          <div className="flex flex-col gap-2">
            <div className="h-6 w-36 animate-pulse rounded bg-surface-inset" />
            <div className="h-3 w-48 animate-pulse rounded bg-surface-inset" />
          </div>
          <div className="h-8 w-8 animate-pulse rounded-md bg-surface-inset" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 space-y-4 px-4 py-6">
        <div className="grid grid-cols-2 gap-4 rounded-xl border border-line bg-surface-card p-4">
          <div className="h-14 animate-pulse rounded bg-surface-inset" />
          <div className="h-14 animate-pulse rounded bg-surface-inset" />
        </div>

        <div className="h-13 animate-pulse rounded-xl border border-line bg-surface-card p-2" />

        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-line bg-surface-card p-4"
            >
              <div className="mb-3 h-3 w-32 animate-pulse rounded bg-surface-inset" />
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-44 animate-pulse rounded bg-surface-inset" />
                  <div className="h-4 w-44 animate-pulse rounded bg-surface-inset" />
                </div>
                <div className="space-y-2">
                  <div className="h-4 w-24 animate-pulse rounded bg-surface-inset" />
                  <div className="h-4 w-20 animate-pulse rounded bg-surface-inset" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
