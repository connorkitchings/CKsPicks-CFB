import { PageShell } from "@/components/PageShell";
import { Card } from "@/components/ui/Card";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";
import { Skeleton } from "@/components/ui/Skeleton";
import { PHONE_PAGE_RHYTHM } from "@/lib/page-width";

/**
 * Ratings loading skeleton. Phones: the pinned search and Filters row, the summary line and rating
 * cards at their loaded heights. From 640px: heading, filter row and table rows.
 */
export default function Loading() {
  return (
    <PageShell
      width="wide"
      footer={false}
      aria-busy="true"
      aria-label="Loading ratings"
      mainClassName={`${PHONE_PAGE_RHYTHM} sm:space-y-4 sm:py-6`}
    >
      <p role="status" className="sr-only">Loading ratings…</p>
      <MobileStickyBar className="flex items-center gap-2 sm:hidden">
        <Skeleton className="h-11 flex-1 rounded-lg" />
        <Skeleton className="size-11 rounded-lg" />
      </MobileStickyBar>
      <Skeleton className="h-4 w-56 sm:hidden" />
      <div className="space-y-2 sm:hidden">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-30.75 rounded-xl" />
        ))}
      </div>
      <div className="space-y-2 max-sm:hidden">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-3 w-64" />
      </div>
      <div className="flex flex-wrap gap-2 max-sm:hidden">
        <Skeleton className="h-11 w-full rounded-md sm:max-w-md" />
        <Skeleton className="h-11 w-32 rounded-md" />
        <Skeleton className="h-11 w-32 rounded-md" />
      </div>
      <Card padding="none" className="divide-y divide-line max-sm:hidden">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3">
            <Skeleton className="h-4 w-6" />
            <Skeleton className="h-4 w-40" />
            <Skeleton className="ml-auto h-4 w-12" />
          </div>
        ))}
      </Card>
    </PageShell>
  );
}
