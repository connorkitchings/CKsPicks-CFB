import { PageShell } from "@/components/PageShell";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";

export default function ModelLoading() {
  return (
    <PageShell
      width="wide"
      footer={false}
      mainClassName="space-y-4 py-3 sm:py-6"
      aria-busy="true"
      aria-label="Loading model record"
    >
      <Skeleton className="h-11 w-56" />
      <Skeleton className="h-6 w-64" />
      <SkeletonCard lines={4} />
      <SkeletonCard lines={6} />
    </PageShell>
  );
}
