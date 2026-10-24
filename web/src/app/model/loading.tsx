import { PageShell } from "@/components/PageShell";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { PHONE_PAGE_RHYTHM } from "@/lib/page-width";

/** Model loading skeleton. Phones: the pinned tab row, summary line and the two KPI cards at their loaded heights. */
export default function ModelLoading() {
  return (
    <PageShell
      width="wide"
      footer={false}
      mainClassName={`${PHONE_PAGE_RHYTHM} sm:space-y-4 sm:py-6`}
      aria-busy="true"
      aria-label="Loading model record"
    >
      <MobileStickyBar className="flex gap-1 border-b border-line max-sm:pb-0 sm:hidden">
        <Skeleton className="-mb-px h-11 w-18" />
        <Skeleton className="-mb-px h-11 w-27.5" />
      </MobileStickyBar>
      <Skeleton className="h-4 w-48 sm:hidden" />
      <div className="grid grid-cols-2 gap-2.5 sm:hidden">
        <Skeleton className="h-42.5 rounded-xl" />
        <Skeleton className="h-42.5 rounded-xl" />
      </div>
      <Skeleton className="h-11.5 rounded-xl sm:hidden" />
      <Skeleton className="h-11 w-56 max-sm:hidden" />
      <Skeleton className="h-6 w-64 max-sm:hidden" />
      <SkeletonCard lines={4} className="max-sm:hidden" />
      <SkeletonCard lines={6} />
    </PageShell>
  );
}
