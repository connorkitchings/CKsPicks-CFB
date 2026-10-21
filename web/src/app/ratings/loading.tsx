import { PageShell } from "@/components/PageShell";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

/** Ratings loading skeleton: heading, filter row and table rows. */
export default function Loading() {
  return (
    <PageShell
      width="wide"
      footer={false}
      aria-busy="true"
      aria-label="Loading ratings"
      mainClassName="space-y-4 py-3 sm:py-6"
    >
      <p role="status" className="sr-only">Loading ratings…</p>
      <div className="space-y-2">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-3 w-64" />
      </div>
      <div className="flex flex-wrap gap-2">
        <Skeleton className="h-11 w-full rounded-md sm:max-w-md" />
        <Skeleton className="h-11 w-32 rounded-md" />
        <Skeleton className="h-11 w-32 rounded-md" />
      </div>
      <Card padding="none" className="divide-y divide-line">
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
