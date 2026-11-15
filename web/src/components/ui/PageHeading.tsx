import type { ReactNode } from "react";
import { Eyebrow } from "./SectionHeading";

export function PageHeading({
  title,
  eyebrow,
  children,
  actions,
  as: Heading = "h1",
}: {
  as?: "h1" | "h2";
  title: string;
  eyebrow?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0">
        {eyebrow && <Eyebrow className="mb-0.5">{eyebrow}</Eyebrow>}
        <Heading className={Heading === "h1" ? "text-[clamp(1.75rem,3vw,2.5rem)] font-bold leading-[1.15] tracking-[-0.035em] text-ink" : "text-xl font-bold tracking-tight text-ink sm:text-2xl"}>{title}</Heading>
        {children && <div className="mt-1 text-sm text-ink-muted">{children}</div>}
      </div>
      {actions}
    </div>
  );
}
