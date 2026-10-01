import type { Game } from "@/lib/queries";
import { topLeans, type LeanKind } from "@/lib/picks-proto";
import { kickoffTime } from "./format";
import { LeanMarker } from "./LeanMarker";

function Column({ games, kind, title }: { games: Game[]; kind: LeanKind; title: string }) {
  const rows = topLeans(games, kind, 5);
  return (
    <div>
      <h3 className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-xs text-ink-faint">No leans yet.</p>
      ) : (
        <ol className="space-y-1">
          {rows.map((l) => (
            <li key={l.game.gameId}>
              <a
                href={`#game-${l.game.gameId}`}
                className="block rounded-md px-2 py-1.5 hover:bg-surface-inset focus-visible:outline-2 focus-visible:outline-accent"
              >
                <span className="flex items-center gap-2 text-sm">
                  <LeanMarker lean={l} />
                  <span className="min-w-0 truncate font-semibold text-accent-ink">{l.pick}</span>
                  <span className="shrink-0 text-xs tabular-nums text-ink-muted">({l.edge.toFixed(1)})</span>
                  <span className="hidden min-w-0 truncate text-xs text-ink-faint sm:inline">
                    {l.game.awayTeam} @ {l.game.homeTeam}
                  </span>
                  <span className="ml-auto hidden shrink-0 text-xs tabular-nums text-ink-faint sm:inline">
                    {kickoffTime(l.game.startDate)}
                  </span>
                </span>
                {l.model && (
                  <span className="mt-0.5 block truncate pl-6 text-[11px] text-ink-muted">
                    model: {l.model}
                  </span>
                )}
              </a>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** Highest-edge leans first; every game is still listed below. */
export function TopLeans({ games }: { games: Game[] }) {
  return (
    <section aria-label="Top leans" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <h2 className="mb-2 text-sm font-semibold text-ink">Top leans</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <Column games={games} kind="spread" title="Spread" />
        <Column games={games} kind="total" title="Total" />
      </div>
    </section>
  );
}
