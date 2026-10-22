import type { ReactNode } from "react";
import clsx from "clsx";

/*
 * Notice: status messages in one surface.
 *   <Notice tone="empty" title="No games">Nothing scheduled.</Notice>
 *   <Notice tone="warn" action={<a href="/model">Open the model</a>}>…</Notice>
 * Tones: info and empty announce politely (role="status"); warn and error
 * interrupt (role="alert").
 */
const TONES = {
  info: { box: "border-accent-line bg-accent-soft", text: "text-ink", role: "status" },
  empty: { box: "border-line bg-surface-card", text: "text-ink-muted", role: "status" },
  warn: { box: "border-warn-line bg-warn-soft", text: "text-warn", role: "alert" },
  error: { box: "border-loss-line bg-loss-soft", text: "text-loss", role: "alert" },
} as const;

export type NoticeTone = keyof typeof TONES;

export function Notice({
  tone = "info",
  title,
  action,
  className,
  children,
}: {
  tone?: NoticeTone;
  title?: ReactNode;
  action?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  const t = TONES[tone];
  return (
    <div
      role={t.role}
      data-card=""
      className={clsx(
        "flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 text-sm",
        t.box,
        t.text,
        className,
      )}
    >
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={clsx(title && "mt-1")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}
