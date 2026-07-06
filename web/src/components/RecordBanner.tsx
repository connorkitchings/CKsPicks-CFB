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
      <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
        No season record yet for {season}.
      </div>
    );
  }

  const card = (label: string, w: number, l: number, p: number) => (
    <div className="flex flex-col gap-1">
      <div className="text-[11px] uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
        {label}
      </div>
      <div className="font-mono text-lg font-semibold text-zinc-900 dark:text-zinc-50">
        {w}–{l}
        {p > 0 && <span className="text-zinc-400">–{p}</span>}
      </div>
      <div className="flex gap-3 text-xs text-zinc-500 dark:text-zinc-400">
        <span>{pct(w, l)}</span>
        <span
          className={clsx(
            "font-medium",
            roi(w, l).startsWith("+")
              ? "text-emerald-600 dark:text-emerald-400"
              : roi(w, l).startsWith("—")
                ? ""
                : "text-rose-600 dark:text-rose-400",
          )}
        >
          {roi(w, l)} ROI
        </span>
      </div>
    </div>
  );

  return (
    <section
      aria-label="Season record"
      className="grid grid-cols-2 gap-4 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
    >
      {card("Spreads", stats.spreadWins, stats.spreadLosses, stats.spreadPushes)}
      {card("Totals", stats.totalWins, stats.totalLosses, stats.totalPushes)}
      <div className="col-span-2 text-[11px] text-zinc-400 dark:text-zinc-500">
        {season} record through week {stats.asOfWeek ?? "—"} · assumes -110 vig
      </div>
    </section>
  );
}
