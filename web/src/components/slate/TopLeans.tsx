import clsx from "clsx";
import type { Game } from "@/lib/queries";
import { edgeTone, topLeans, type LeanKind, type Tally } from "@/lib/slate";
import { kickoffTime } from "./format";
import { LeanMarker } from "./LeanMarker";

function Column({ games, kind, title }: { games: Game[]; kind: LeanKind; title: string }) {
  const rows = topLeans(games, kind, 5);
  return (
    <div>
      <h3 className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-xs text-ink-faint">No leans yet.</p>
      ) : (
        <ol className="divide-y divide-line/40">
          {rows.map((l) => (
            <li key={l.game.gameId}>
              <a
                href={`#game-${l.game.gameId}`}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-surface-inset focus-visible:outline-2 focus-visible:outline-accent"
              >
                <LeanMarker lean={l} />
                <span className="min-w-0 truncate font-semibold text-ink">{l.pick}</span>
                <span className={clsx("shrink-0 text-xs font-bold tabular-nums", edgeTone(l.edge, l.kind))}>
                  ({l.edge.toFixed(1)})
                </span>
                <span className="hidden min-w-0 truncate text-xs text-ink-muted sm:inline">
                  {l.game.awayTeam} @ {l.game.homeTeam}
                </span>
                <span className="ml-auto hidden shrink-0 text-xs tabular-nums text-ink-faint sm:inline">
                  {kickoffTime(l.game.startDate)}
                </span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** Highest-edge leans first; every game is still listed below. */
export function TopLeans({ games, record }: { games: Game[]; record?: Tally | null }) {
  const decided = (record?.win ?? 0) + (record?.loss ?? 0) + (record?.push ?? 0);
  return (
    <section aria-label="Top leans" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Top leans</h2>
        {record && decided > 0 && (
          <span className="text-xs tabular-nums text-ink-muted">
            Top leans: {record.win}–{record.loss}–{record.push} this season
          </span>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Column games={games} kind="spread" title="Spread" />
        <Column games={games} kind="total" title="Total" />
      </div>
    </section>
  );
}
