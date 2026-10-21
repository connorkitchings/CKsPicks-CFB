import { PageShell } from "@/components/PageShell";
import { Card } from "@/components/ui/Card";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";

/** Matchup loading skeleton: back link, two team blocks with the forecast, and stat cards. */
export default function Loading() {
  return (
    <PageShell
      width="wide"
      footer={false}
      aria-busy="true"
      aria-label="Loading matchup"
      mainClassName="space-y-6 py-6"
    >
      <p role="status" className="sr-only">Loading matchup…</p>
      <Skeleton className="h-5 w-40" />
      <Card className="sm:p-6">
        <div className="grid grid-cols-2 items-start gap-4 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
          {[0, 1].map((i) => (
            <div key={i} className="flex flex-col items-center gap-2">
              <Skeleton className="h-12 w-12 rounded-full sm:h-16 sm:w-16" />
              <Skeleton className="h-5 w-28" />
              <Skeleton className="h-3 w-20" />
            </div>
          ))}
          <Skeleton className="col-span-2 h-32 w-full rounded-xl lg:col-span-1 lg:col-start-2 lg:row-start-1 lg:w-[475px]" />
        </div>
      </Card>
      <SkeletonCard lines={6} />
      <SkeletonCard lines={6} />
    </PageShell>
  );
}
