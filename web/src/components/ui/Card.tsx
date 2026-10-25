import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import clsx from "clsx";

/*
 * Card: the one surface for boxed content.
 *   <Card>…</Card>                      default padding (md)
 *   <Card as="section" padding="sm" aria-labelledby="h">…</Card>
 *   <Card as="li" padding="none">…</Card>   when children own their padding
 * Always renders `data-card` (the dark-mode glow in globals.css keys off it).
 * Do not restyle radius, border or background through className.
 */
const PADDING = { none: "", sm: "p-3", md: "p-4" } as const;

export type CardProps = {
  as?: "div" | "section" | "article" | "li";
  padding?: keyof typeof PADDING;
  className?: string;
  children?: ReactNode;
} & Omit<ComponentPropsWithoutRef<"div">, "className" | "children">;

export function Card({ as, padding = "md", className, children, ...rest }: CardProps) {
  const Tag = (as ?? "div") as ElementType;
  return (
    <Tag
      {...rest}
      data-card=""
      className={clsx("rounded-xl border border-line bg-surface-card shadow-2xs", PADDING[padding], className)}
    >
      {children}
    </Tag>
  );
}
