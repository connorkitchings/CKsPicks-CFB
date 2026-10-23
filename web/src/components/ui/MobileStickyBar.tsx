import type { HTMLAttributes } from "react";
import clsx from "clsx";

/**
 * The phone pinned bar: sticks to the top (below the safe area), bleeds to the page edges, opaque
 * with no backdrop blur. Inert from 640px up. Extra classes and attributes pass through.
 */
export function MobileStickyBar({ as: Tag = "div", className, ...props }: { as?: "div" | "nav" } & HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      className={clsx("max-sm:sticky max-sm:top-0 max-sm:z-30 max-sm:-mx-4 max-sm:border-b max-sm:border-line max-sm:bg-surface-page max-sm:px-4 max-sm:pb-2 max-sm:pt-[calc(env(safe-area-inset-top)+0.5rem)]", className)}
      {...props}
    />
  );
}
