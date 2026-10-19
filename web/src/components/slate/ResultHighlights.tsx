import { Disclosure } from "@/components/ui/Disclosure";
import type { Game } from "@/lib/queries";
import { topResults, type GradedLean } from "@/lib/slate";
import { LeanMarker } from "./LeanMarker";
import { coverText, ResultBadge } from "./ResultBadge";

function Column({ title, rows, empty }: { title: string; rows: GradedLean[]; empty: string }) {
  return (
    <div>
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-xs text-ink-muted">{empty}</p>
      ) : (
        <ol className="space-y-1">
          {rows.map((r) => (
            <li key={`${r.game.gameId}-${r.kind}`}>
              <a
                href={`#game-${r.game.gameId}`}
                className="flex min-h-11 items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surface-inset focus-visible:outline-2 focus-visible:outline-accent"
              >
                <ResultBadge grade={r.grade} />
                <LeanMarker lean={r} />
                <span className="min-w-0 truncate font-semibold text-ink">{r.pick}</span>
                <span className="shrink-0 text-xs tabular-nums text-ink-muted">({r.edge.toFixed(1)})</span>
                <span className="hidden min-w-0 truncate text-xs text-ink-muted sm:inline">
                  {r.game.awayTeam} @ {r.game.homeTeam}
                </span>
                <span className="ml-auto shrink-0 text-xs tabular-nums text-ink-muted">
                  {coverText(r.cover)}
                </span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** Highest-edge leans that won, and highest-edge leans that lost. */
export function ResultHighlights({ games }: { games: Game[] }) {
  return (
    <section aria-label="Highlights">
      <Disclosure title="Highlights">
        <div className="grid gap-4 md:grid-cols-2">
          <Column title="Best calls (largest edge that won)" rows={topResults(games, "win", 3)} empty="No wins graded." />
          <Column title="Biggest misses (largest edge that lost)" rows={topResults(games, "loss", 3)} empty="No losses graded." />
        </div>
      </Disclosure>
    </section>
  );
}
