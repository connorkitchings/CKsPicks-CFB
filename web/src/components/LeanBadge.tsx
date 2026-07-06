import { clsx } from "clsx";

/**
 * Visual spread-lean badge. Color encodes direction (home = blue, away = red);
 * intensity encodes strength of lean via the edge magnitude.
 *
 * Heuristics (mirror v2_champion.yaml thresholds):
 *   edge >= 8.0  -> "High" confidence (solid fill)
 *   edge >= 2.0  -> "Medium" (soft fill)
 *   else         -> "Low" (outline only)
 */
function edgeTier(edge: number | null): "high" | "medium" | "low" {
  if (edge === null) return "low";
  if (edge >= 8.0) return "high";
  if (edge >= 2.0) return "medium";
  return "low";
}

export function LeanBadge({
  lean,
  edge,
  homeTeam,
  awayTeam,
}: {
  lean: "home" | "away" | null;
  edge: number | null;
  homeTeam: string;
  awayTeam: string;
}) {
  if (lean === null) {
    return (
      <span className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium text-zinc-400 ring-1 ring-zinc-300 dark:ring-zinc-700">
        No lean
      </span>
    );
  }

  const isHome = lean === "home";
  const team = isHome ? homeTeam : awayTeam;
  const tier = edgeTier(edge);

  const styles = {
    home: {
      high: "bg-blue-600 text-white ring-1 ring-blue-700",
      medium: "bg-blue-100 text-blue-800 ring-1 ring-blue-200 dark:bg-blue-950 dark:text-blue-200 dark:ring-blue-900",
      low: "bg-transparent text-blue-600 ring-1 ring-blue-300 dark:text-blue-300 dark:ring-blue-800",
    },
    away: {
      high: "bg-rose-600 text-white ring-1 ring-rose-700",
      medium: "bg-rose-100 text-rose-800 ring-1 ring-rose-200 dark:bg-rose-950 dark:text-rose-200 dark:ring-rose-900",
      low: "bg-transparent text-rose-600 ring-1 ring-rose-300 dark:text-rose-300 dark:ring-rose-800",
    },
  } as const;

  const cls = styles[lean][tier];
  const label = `${isHome ? "🏠" : "✈️"} ${team}`;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold whitespace-nowrap",
        cls,
      )}
      title={`Edge: ${edge !== null ? edge.toFixed(1) : "—"} pts`}
    >
      {label}
      {edge !== null && (
        <span className="opacity-75 font-mono">+{edge.toFixed(1)}</span>
      )}
    </span>
  );
}

/** Smaller chip for over/under lean. */
export function TotalLeanChip({
  lean,
  edge,
  totalLine,
}: {
  lean: "over" | "under" | null;
  edge: number | null;
  totalLine: number | null;
}) {
  if (lean === null || totalLine === null) {
    return (
      <span className="inline-flex items-center rounded-md px-2 py-0.5 text-[11px] text-zinc-400 ring-1 ring-zinc-300 dark:ring-zinc-700">
        O/U —
      </span>
    );
  }
  const isOver = lean === "over";
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium ring-1",
        isOver
          ? "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-900"
          : "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-900",
      )}
      title={`Edge: ${edge !== null ? edge.toFixed(1) : "—"} pts`}
    >
      {isOver ? "Over" : "Under"} {totalLine.toFixed(1)}
    </span>
  );
}
