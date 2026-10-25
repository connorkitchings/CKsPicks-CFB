import type { ReactNode } from "react";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";

/** A titled card of the team page's body; `actions` sits at the right of the title row. */
export function TeamSection({
  id,
  title,
  actions,
  className,
  children,
}: {
  /** Id of the heading, which labels the section. */
  id: string;
  title: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Card as="section" aria-labelledby={id} className={clsx("min-w-0 max-sm:p-3.5", className)}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} className="text-xs font-semibold uppercase tracking-wider text-ink-muted">{title}</h2>
        {actions}
      </div>
      {children}
    </Card>
  );
}
