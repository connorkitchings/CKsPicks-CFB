import accuracy from "@/data/model-accuracy.json";

type TargetAccuracy = {
  champion: string;
  selection: { mae: number; n: number; seasons: Record<string, number> } | null;
  locked_2025: { mae: number; n: number } | null;
};

type AccuracyData = {
  methodology: string;
  routes: Record<string, { label: string; spread: TargetAccuracy; total: TargetAccuracy }>;
};

const data = accuracy as AccuracyData;

/** Mirrors the pipeline contract: stored rows may carry legacy regime labels. */
const LEGACY_TO_CANONICAL_REGIME: Record<string, string> = {
  preseason: "game_1",
  one_game: "game_2",
  two_games: "game_3",
  three_games: "game_4",
  established: "established",
};

function statLines(block: TargetAccuracy, unit: string): string[] {
  const lines: string[] = [];
  if (block.locked_2025) {
    lines.push(
      `${block.locked_2025.mae.toFixed(1)} pts off final ${unit} (2025, n=${block.locked_2025.n})`,
    );
  }
  if (block.selection) {
    lines.push(
      `${block.selection.mae.toFixed(1)} pts avg 2022–24 (n=${block.selection.n})`,
    );
  }
  return lines.length > 0 ? lines : ["No backtest yet"];
}

/**
 * Backtest context for the routes in play this week: how close the model's
 * predictions were to final results historically. Outcome-based only (no
 * historical market lines exist under the canonical market policy).
 */
export function ModelAccuracyPanel({ regimes }: { regimes: string[] }) {
  const inPlay = Array.from(
    new Set(
      regimes.map(
        (r) => LEGACY_TO_CANONICAL_REGIME[r] ?? (r in data.routes ? r : null),
      ),
    ),
  ).filter((r): r is string => r !== null && r in data.routes);
  if (inPlay.length === 0) return null;

  return (
    <section
      aria-label="Model backtest accuracy"
      className="space-y-4 rounded-xl border border-line bg-surface-card p-4 shadow-sm"
    >
      <div className="text-[11px] uppercase tracking-wide text-ink-faint">
        Model accuracy{inPlay.length === 1 ? ` — ${data.routes[inPlay[0]].label.toLowerCase()}` : ""}
      </div>
      {inPlay.map((regime) => {
        const route = data.routes[regime];
        return (
          <div key={regime} className="grid grid-cols-2 gap-4">
            {inPlay.length > 1 && (
              <div className="col-span-2 text-xs font-medium text-ink-muted">
                {route.label}
              </div>
            )}
            <div className="flex flex-col gap-1">
              <div className="text-xs text-ink-muted">Spreads</div>
              {statLines(route.spread, "margin").map((line) => (
                <div
                  key={line}
                  className="font-mono text-sm font-semibold tabular-nums text-ink"
                >
                  {line}
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-1">
              <div className="text-xs text-ink-muted">Totals</div>
              {statLines(route.total, "total").map((line) => (
                <div
                  key={line}
                  className="font-mono text-sm font-semibold tabular-nums text-ink"
                >
                  {line}
                </div>
              ))}
            </div>
          </div>
        );
      })}
      <div className="text-[11px] text-ink-faint">{data.methodology}</div>
    </section>
  );
}
