import { PageShell } from "@/components/PageShell";
import { Card } from "@/components/ui/Card";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";

/**
 * Route-level loading skeleton shown during ISR refreshes and initial render.
 * Mirrors the Games page: heading, record, collapsed highlights, controls and
 * the card grid, so the layout doesn't shift when real data arrives.
 */
export default function Loading() {
  return (
    <PageShell
      width="slate"
      footer={false}
      aria-busy="true"
      aria-label="Loading page"
      mainClassName="space-y-3 py-3 sm:py-6"
    >
      <p role="status" className="sr-only">Loading page…</p>
      <Skeleton className="h-7 w-36" />
      <Card>
        <Skeleton className="mb-2 h-4 w-40" />
        <div className="grid grid-cols-2 gap-2">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      </Card>
      <Skeleton className="h-11 rounded-xl" />
      <Skeleton className="h-13 rounded-xl" />
      <div className="grid gap-3 md:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} lines={4} />
        ))}
      </div>
    </PageShell>
  );
}
