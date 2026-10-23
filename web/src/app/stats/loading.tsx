import { PageShell } from "@/components/PageShell";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";

export default function StatsLoading() {
  return (
    <PageShell
      width="slate"
      footer={false}
      mainClassName="space-y-4 py-3 sm:py-6"
      aria-busy="true"
      aria-label="Loading graphs"
    >
      <Skeleton className="h-11 w-56" />
      <Skeleton className="h-11 w-full" />
      <SkeletonCard lines={8} />
    </PageShell>
  );
}
