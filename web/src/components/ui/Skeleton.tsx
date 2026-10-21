import clsx from "clsx";
import { Card } from "./Card";

/** Pulsing placeholder block; size it with className (e.g. "h-4 w-32"). */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={clsx("animate-pulse rounded bg-surface-inset motion-reduce:animate-none", className)}
    />
  );
}

/** Card holding a few placeholder lines. */
export function SkeletonCard({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <Card className={className}>
      <Skeleton className="mb-3 h-3 w-32" />
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={clsx("h-4", i % 2 ? "w-28" : "w-44")} />
        ))}
      </div>
    </Card>
  );
}
