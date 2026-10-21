import Link from "next/link";
import type { ComponentProps } from "react";
import clsx from "clsx";

const VARIANTS = {
  primary: "bg-accent-solid text-on-accent-solid hover:opacity-90",
  secondary: "border border-line bg-surface-card text-ink hover:bg-surface-inset",
} as const;

export type ButtonLinkProps = {
  variant?: keyof typeof VARIANTS;
} & ComponentProps<typeof Link>;

/** A link styled as a button; at least 44px tall on phones. */
export function ButtonLink({ variant = "secondary", className, ...rest }: ButtonLinkProps) {
  return (
    <Link
      {...rest}
      className={clsx(
        "inline-flex min-h-11 items-center justify-center rounded-md px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-accent sm:min-h-9",
        VARIANTS[variant],
        className,
      )}
    />
  );
}
