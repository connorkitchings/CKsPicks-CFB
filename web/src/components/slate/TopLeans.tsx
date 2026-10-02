import type { Game } from "@/lib/queries";
import { topLeans, winRatePct, type LeanKind, type Tally } from "@/lib/slate";
import { LeanMarker } from "./LeanMarker";
import TeamLogo from "@/components/TeamLogo";

function Column({ games, kind, title }: { games: Game[]; kind: LeanKind; title: string }) {
  const rows = topLeans(games, kind, 5);
  return (
    <div className="min-w-0 rounded-lg border border-line/60 bg-surface-inset/50 p-3">
      <h3 className="mb-2 text-center text-xs font-semibold uppercase tracking-wider text-ink-muted">
        {title}
      </h3>
      {rows.length === 0 ? (
        <p className="py-2 text-center text-xs text-ink-faint">No leans yet.</p>
      ) : (
        <ol className="divide-y divide-line/40">
          {rows.map((l) => (
            <li key={l.game.gameId}>
              <a
                href={`#game-${l.game.gameId}`}
                className="flex h-10 min-w-0 items-center justify-center gap-2 rounded-md px-2.5 transition-colors hover:bg-surface-card focus-visible:outline-2 focus-visible:outline-accent"
              >
                {kind === "total" ? (
                  <>
                    <span className="flex min-w-0 items-center gap-1.5 text-xs text-ink-muted">
                      <TeamLogo name={l.game.awayTeam} px={16} />
                      <span className="truncate">{l.game.awayTeam}</span>
                      <span className="shrink-0 text-ink-faint">@</span>
                      <TeamLogo name={l.game.homeTeam} px={16} />
                      <span className="truncate">{l.game.homeTeam}</span>
                    </span>
                    <span aria-hidden className="shrink-0 text-xs text-ink-faint">·</span>
                    <span className="flex shrink-0 items-center gap-1 text-xs font-semibold whitespace-nowrap text-ink sm:text-sm">
                      <LeanMarker lean={l} />
                      <span>{l.pick}</span>
                    </span>
                  </>
                ) : (
                  <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <LeanMarker lean={l} />
                    <span>{l.pick}</span>
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
export function TopLeans({ games, record }: { games: Game[]; record?: Tally | null }) {
  const decided = (record?.win ?? 0) + (record?.loss ?? 0);
  const rate = decided > 0 && record ? winRatePct(record.win, record.loss) : null;
  return (
    <section aria-label="Best bets" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Best Bets</h2>
        {record && (decided + (record.push ?? 0)) > 0 && (
          <span className="text-xs tabular-nums text-ink-muted">
            Best bets: {record.win}–{record.loss}–{record.push} this season{rate !== null ? ` (${rate.toFixed(1)}%)` : ""}
          </span>
        )}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Column games={games} kind="spread" title="Spread" />
        <Column games={games} kind="total" title="Total" />
      </div>
    </section>
  );
}
