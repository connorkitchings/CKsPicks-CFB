import type { ElementType, ReactNode } from "react";
import clsx from "clsx";

/** The single small uppercase label style. */
export function Eyebrow({
  as: Tag = "p",
  className,
  children,
}: {
  as?: ElementType;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Tag className={clsx("text-xs font-semibold uppercase tracking-wider text-ink-muted", className)}>
      {children}
    </Tag>
  );
}

/** Section title (h2 by default) with an optional trailing actions slot. */
export function SectionHeading({
  as: Heading = "h2",
  id,
  actions,
  className,
  children,
}: {
  as?: "h2" | "h3";
  id?: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={clsx("flex flex-wrap items-center justify-between gap-2", className)}>
      <Heading id={id} className="text-base font-semibold tracking-tight text-ink">
        {children}
      </Heading>
      {actions}
    </div>
  );
}
