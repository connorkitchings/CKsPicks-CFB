import clsx from "clsx";
import type { Grade } from "@/lib/slate";

const LABEL: Record<Grade, string> = { win: "Win", loss: "Loss", push: "Push" };

/** Graded outcome chip. Green/red are reserved for graded results only. */
export function ResultBadge({ grade }: { grade: Grade }) {
  return (
    <span
      className={clsx(
        "inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold",
        grade === "win" && "bg-win-soft text-win",
        grade === "loss" && "bg-loss-soft text-loss",
        grade === "push" && "bg-surface-inset text-ink-muted",
      )}
    >
      {LABEL[grade]}
    </span>
  );
}

/** "Covered by 3.5" / "Missed by 2.0" / "Pushed". */
export function coverText(cover: number | null): string | null {
  if (cover === null) return null;
  if (cover === 0) return "Pushed";
  return `${cover > 0 ? "Covered" : "Missed"} by ${Math.abs(cover).toFixed(1)}`;
}
