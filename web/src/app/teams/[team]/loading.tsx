import { PageShell } from "@/components/PageShell";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

/** Team page loading skeleton: header block, trend line, history table and schedule rows. */
export default function Loading() {
  return (
    <PageShell
      width="narrow"
      footer={false}
      aria-busy="true"
      aria-label="Loading team"
      mainClassName="space-y-5 py-4 sm:space-y-7 sm:py-8"
    >
      <p role="status" className="sr-only">Loading team…</p>
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-5 w-44" />
            <Skeleton className="h-3 w-12" />
          </div>
        </div>
        <Card padding="sm" className="space-y-3">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-9 w-full" />
        </Card>
      </div>
      <div className="space-y-3">
        <Skeleton className="h-14 w-full" />
        <Card padding="none" className="divide-y divide-line">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-3">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="ml-auto h-4 w-12" />
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-4 w-12" />
            </div>
          ))}
        </Card>
      </div>
      <Card padding="none" className="divide-y divide-line">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2 px-3 py-2.5">
            <Skeleton className="h-6 w-6 rounded-full" />
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        ))}
      </Card>
    </PageShell>
  );
}
