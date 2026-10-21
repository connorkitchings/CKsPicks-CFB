import { PageShell } from "@/components/PageShell";
import { Card } from "@/components/ui/Card";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";

/** Team page loading skeleton: heading, rating history table and forecast cards. */
export default function Loading() {
  return (
    <PageShell
      width="narrow"
      footer={false}
      aria-busy="true"
      aria-label="Loading team"
      mainClassName="space-y-7 py-8"
    >
      <p role="status" className="sr-only">Loading team…</p>
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-3 w-64" />
      </div>
      <Card padding="none" className="divide-y divide-line">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="ml-auto h-4 w-12" />
            <Skeleton className="h-4 w-12" />
          </div>
        ))}
      </Card>
      <div className="space-y-2">
        <SkeletonCard lines={2} />
        <SkeletonCard lines={2} />
      </div>
    </PageShell>
  );
}
