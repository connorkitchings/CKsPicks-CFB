import accuracy from "@/data/model-accuracy.json";

type TargetAccuracy = {
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

function routeContext(regime: string): string {
  if (regime === "game_1") {
    return "At least one team is playing its first game, so the model has limited current-season evidence.";
  }
  const completedGames = { game_2: 1, game_3: 2, game_4: 3 }[regime];
  if (completedGames !== undefined) {
    return `At least one team has only ${completedGames} completed ${completedGames === 1 ? "game" : "games"}, so current-season evidence is still limited.`;
  }
  return "Both teams have enough current-season results for the established model.";
}

function QualityCheck({
  label,
  description,
  spread,
  total,
}: {
  label: string;
  description: string;
  spread: { mae: number; n: number } | null;
  total: { mae: number; n: number } | null;
}) {
  const sampleSize = spread?.n ?? total?.n;
  if (!spread && !total) return null;

  return (
    <div className="rounded-lg bg-surface-inset p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
        <div className="text-xs font-medium text-ink-muted">{label}</div>
        {sampleSize && (
          <div className="text-[11px] text-ink-faint">
            {sampleSize} comparable games
          </div>
        )}
      </div>
      <p className="mt-1 text-[11px] text-ink-faint">{description}</p>
      <dl className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <dt className="text-[11px] text-ink-faint">Spread</dt>
          <dd className="font-mono text-base font-semibold tabular-nums text-ink">
            {spread ? `${spread.mae.toFixed(1)} pts` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] text-ink-faint">Total</dt>
          <dd className="font-mono text-base font-semibold tabular-nums text-ink">
            {total ? `${total.mae.toFixed(1)} pts` : "—"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

/** Fan-facing context for the models in play this week. */
export function ModelAccuracyPanel({ regimes }: { regimes: string[] }) {
  const inPlay = Array.from(
    new Set(
      regimes.map(
        (regime) =>
          LEGACY_TO_CANONICAL_REGIME[regime] ??
          (regime in data.routes ? regime : null),
      ),
    ),
  ).filter((regime): regime is string => regime !== null && regime in data.routes);
  if (inPlay.length === 0) return null;

  return (
    <section
      aria-label="Model quality context"
      className="rounded-xl border border-line bg-surface-card p-4 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-ink">Early-Season Model Context</h2>
      <p className="mt-1 text-xs text-ink-muted">
        Typical miss is the average distance between a prediction and the final result. Smaller is better.
      </p>

      <div className="mt-4 space-y-4">
        {inPlay.map((regime) => {
          const route = data.routes[regime];
          return (
            <div key={regime}>
              {inPlay.length > 1 && (
                <h3 className="text-xs font-semibold text-ink-muted">
                  {regime === "game_1" ? "First-Game Model" : `${route.label} Model`}
                </h3>
              )}
              <p className="text-sm text-ink-muted">{routeContext(regime)}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <QualityCheck
                  label="2025 Season Check"
                  description="How the model performed in the most recent season."
                  spread={route.spread.locked_2025}
                  total={route.total.locked_2025}
                />
                <QualityCheck
                  label="2022–24 Track Record"
                  description="A broader check across earlier seasons."
                  spread={route.spread.selection}
                  total={route.total.selection}
                />
              </div>
            </div>
          );
        })}
      </div>

      <details className="mt-4 border-t border-line pt-3 text-xs text-ink-faint">
        <summary className="cursor-pointer font-medium text-ink-muted">
          How These Numbers Are Measured
        </summary>
        <p className="mt-2 leading-relaxed">
          These are forecast checks, not betting results. The 2025 season was
          held aside for a final check; 2022–24 results were used to compare
          early-season model designs. {data.methodology}
        </p>
      </details>
    </section>
  );
}
