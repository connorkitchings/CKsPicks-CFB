/**
 * Route-level loading skeleton shown during ISR refreshes and initial render.
 * Mirrors the shape of Header + RecordBanner + GameRow list so the layout
 * doesn't shift when real data arrives.
 */
export default function Loading() {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-100">
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex max-w-4xl flex-col gap-2 px-4 py-4">
          <div className="flex items-baseline justify-between gap-3">
            <div className="h-6 w-36 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
            <div className="h-4 w-20 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
          </div>
          <div className="h-3 w-48 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 space-y-4 px-4 py-6">
        <div className="grid grid-cols-2 gap-4 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="h-14 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
          <div className="h-14 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
        </div>

        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <div className="mb-3 h-3 w-32 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
              <div className="space-y-2">
                <div className="h-4 w-44 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
                <div className="h-4 w-44 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
