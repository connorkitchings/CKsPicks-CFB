/**
 * Shared stat box: rounded inset container → faint uppercase label → big mono
 * stat → muted subline. Used by RecordBanner, V5PerformanceBanner,
 * HistoricalModelContext, and the /performance page so the record displays
 * stay visually identical without four copies of the same markup.
 */

/** Win rate over decisive games (pushes excluded); "—" when undecided. */
export function winRatePercent(wins: number, losses: number): string {
  const decisions = wins + losses;
  return decisions === 0
    ? "—"
    : `${((100 * wins) / decisions).toFixed(1)}%`;
}

export function StatCard({
  label,
  stat,
  subline,
  statLarge = false,
  labelAs = "div",
}: {
  label: string;
  stat: string;
  subline: string;
  /** Larger mono stat for page-level heroes (e.g. /performance). */
  statLarge?: boolean;
  /** Render the label as an h2 to preserve heading hierarchy on pages. */
  labelAs?: "div" | "h2";
}) {
  const LabelTag = labelAs === "h2" ? "h2" : "div";
  return (
    <div className="rounded-lg bg-surface-inset p-3">
      <LabelTag className="text-[11px] font-medium uppercase tracking-wide text-ink-faint">
        {label}
      </LabelTag>
      <div
        className={
          statLarge
            ? "font-mono text-3xl tabular-nums text-ink"
            : "font-mono text-2xl font-semibold tabular-nums text-ink"
        }
      >
        {stat}
      </div>
      <div className="text-xs tabular-nums text-ink-muted">{subline}</div>
    </div>
  );
}
