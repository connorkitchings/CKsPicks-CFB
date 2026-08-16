import { clsx } from "clsx";

type Stats = {
  spreadWins: number;
  spreadLosses: number;
  spreadPushes: number;
  totalWins: number;
  totalLosses: number;
  totalPushes: number;
  asOfWeek: number | null;
};

function pct(w: number, l: number): string {
  const n = w + l;
  if (n === 0) return "—";
  return `${((100 * w) / n).toFixed(1)}%`;
}

/**
 * Assumes standard -110 vigorish: profit per win = +1 unit,
 * loss per loss = -1.1 units, push = 0.
 */
function roi(w: number, l: number): string {
  const n = w + l;
  if (n === 0) return "—";
  const units = w - 1.1 * l;
  const r = (100 * units) / n;
  const sign = r >= 0 ? "+" : "";
  return `${sign}${r.toFixed(1)}%`;
}

export function RecordBanner({
  season,
  stats,
}: {
  season: number;
  stats: Stats | null;
}) {
  if (!stats) {
    return (
      <div className="rounded-xl border border-line bg-surface-inset p-4 text-sm text-ink-faint">
        No season record yet for {season}.
      </div>
    );
  }

  const card = (label: string, w: number, l: number, p: number) => {
    const roiValue = roi(w, l);
    return (
      <div className="flex flex-col gap-1">
        <div className="text-[11px] uppercase tracking-wide text-ink-faint">
          {label}
        </div>
        <div className="font-mono text-lg font-semibold tabular-nums text-ink">
          {w}–{l}
          {p > 0 && <span className="text-ink-faint">–{p}</span>}
        </div>
        <div className="flex gap-3 text-xs tabular-nums text-ink-muted">
          <span>{pct(w, l)}</span>
          <span
            className={clsx(
              "font-medium",
              roiValue.startsWith("+")
                ? "text-win"
                : roiValue.startsWith("—")
                  ? ""
                  : "text-loss",
            )}
          >
            {roiValue} ROI
          </span>
        </div>
      </div>
    );
  };

  return (
    <section
      aria-label="Season record"
      className="grid grid-cols-2 gap-4 rounded-xl border border-line bg-surface-card p-4 shadow-sm"
    >
      {card("Spreads", stats.spreadWins, stats.spreadLosses, stats.spreadPushes)}
      {card("Totals", stats.totalWins, stats.totalLosses, stats.totalPushes)}
      <div className="col-span-2 text-[11px] text-ink-faint">
        {season} record through week {stats.asOfWeek ?? "—"} · assumes -110 vig
      </div>
    </section>
  );
}
