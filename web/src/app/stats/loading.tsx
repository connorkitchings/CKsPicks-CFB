import { PageShell } from "@/components/PageShell";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { PHONE_PAGE_RHYTHM } from "@/lib/page-width";

/** Graphs loading skeleton. Phones: the pinned chart picker row (select plus settings button), the controls block and the chart at their loaded heights. */
export default function StatsLoading() {
  return (
    <PageShell
      width="slate"
      footer={false}
      mainClassName={`${PHONE_PAGE_RHYTHM} sm:space-y-4 sm:py-6`}
      aria-busy="true"
      aria-label="Loading graphs"
    >
      <MobileStickyBar className="flex items-center gap-2 sm:hidden">
        <Skeleton className="h-11 flex-1 rounded-lg" />
        <Skeleton className="size-11 rounded-lg" />
      </MobileStickyBar>
      <Skeleton className="h-24 rounded-xl sm:hidden" />
      <Skeleton className="h-96 rounded-xl sm:hidden" />
      <Skeleton className="h-11 w-56 max-sm:hidden" />
      <Skeleton className="h-11 w-full max-sm:hidden" />
      <SkeletonCard lines={8} className="max-sm:hidden" />
    </PageShell>
  );
}
