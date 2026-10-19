import type { ReactNode } from "react";

export function PageHeading({
  title,
  children,
  actions,
  as: Heading = "h1",
}: {
  as?: "h1" | "h2";
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0">
        <Heading className="text-lg font-bold tracking-tight text-ink sm:text-xl">{title}</Heading>
        {children && <div className="mt-1 text-sm text-ink-muted">{children}</div>}
      </div>
      {actions}
    </div>
  );
}
