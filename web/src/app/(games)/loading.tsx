import { PageShell } from "@/components/PageShell";
import { Card } from "@/components/ui/Card";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { PHONE_PAGE_RHYTHM } from "@/lib/page-width";

/**
 * Route-level loading skeleton shown during ISR refreshes and initial render. Phones mirror the
 * compact top (status row under the app bar, summary line, record line, pinned week and search bar,
 * day header) at the same heights as the loaded page; from 640px it is heading, record, controls
 * and the card grid.
 */
export default function Loading() {
  return (
    <PageShell
      width="slate"
      footer={false}
      aria-busy="true"
      aria-label="Loading page"
      mainClassName={`${PHONE_PAGE_RHYTHM} sm:py-6`}
    >
      <p role="status" className="sr-only">Loading page…</p>
      <div aria-hidden="true" className="-mx-4 -mt-2 h-8.75 border-b border-line bg-surface-card/80 sm:hidden" />
      <Skeleton className="h-4 w-48 sm:hidden" />
      <Skeleton className="h-11.5 rounded-xl sm:hidden" />
      <MobileStickyBar className="space-y-1.5 sm:hidden">
        <div className="flex items-center gap-2">
          <Skeleton className="h-11 flex-1 rounded-lg" />
          <Skeleton className="size-11 rounded-lg" />
        </div>
        <Skeleton className="h-11 rounded-lg" />
      </MobileStickyBar>
      <Skeleton className="-mx-4 h-7.25 rounded-none sm:hidden" />
      <Skeleton className="h-7 w-36 max-sm:hidden" />
      <Card className="max-sm:hidden">
        <Skeleton className="mb-2 h-4 w-40" />
        <div className="grid grid-cols-2 gap-2">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      </Card>
      <Skeleton className="h-11 rounded-xl max-sm:hidden" />
      <Skeleton className="h-13 rounded-xl max-sm:hidden" />
      <div className="grid gap-3 md:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} lines={4} />
        ))}
      </div>
    </PageShell>
  );
}
