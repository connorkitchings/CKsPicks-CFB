import { ResponsiveDisclosure } from "@/components/ui/ResponsiveDisclosure";
import { PhoneSwap } from "@/components/ui/PhoneSwap";
import TeamLogo from "@/components/TeamLogo";
import { signedSpread } from "@/lib/betting-format";
import type { Game } from "@/lib/queries";
import { underdogPicks, type Tally } from "@/lib/slate";
import { phoneTeamName } from "@/lib/team-logos";

/**
 * Games where the model picks the consensus-line underdog to win outright, largest gap between the
 * model and the market first. About who wins, not odds: no prices or payouts. Renders nothing when
 * no unfinished game qualifies.
 */
export function UnderdogPicks({
  games,
  record,
  season,
}: {
  games: Game[];
  /** Season straight-up record over each scored week's top picks. */
  record?: Tally | null;
  season: number;
}) {
  const picks = underdogPicks(games, 5);
  if (picks.length === 0) return null;

  const decided = record ? record.win + record.loss : 0;
  const recordText = record && decided > 0 ? `${season}: ${record.win}–${record.loss} straight up` : null;

  return (
    <section aria-label="Underdog picks">
      <ResponsiveDisclosure
        title="Underdogs"
        heading={
          <span>
            Underdog picks
            {recordText && <span className="ml-2 text-xs font-normal text-ink-muted">{recordText}</span>}
          </span>
        }
      >
        <p className="mb-1 text-xs">The model picks the underdog to win</p>
        <ol className="divide-y divide-line/40">
          {picks.map((p) => (
            <li key={p.game.gameId}>
              <a
                href={`#game-${p.game.gameId}`}
                aria-label={`${p.game.awayTeam} at ${p.game.homeTeam}: model picks ${p.team} to win`}
                className="flex min-h-11 min-w-0 items-center justify-between gap-2 rounded-md px-2.5 transition-colors hover:bg-surface-card focus-visible:outline-2 focus-visible:outline-accent"
              >
                <span className="flex min-w-0 items-center gap-1.5 text-sm font-semibold text-ink">
                  <TeamLogo name={p.team} px={16} />
                  <span className="truncate"><PhoneSwap full={p.team} phone={phoneTeamName(p.team)} /></span>
                  <span className="shrink-0 tabular-nums">{signedSpread(p.line)}</span>
                </span>
                <span className="flex shrink-0 items-center gap-2 text-xs tabular-nums text-ink-muted">
                  <span className="hidden sm:inline">over {p.opponent}</span>
                  <span>gap {p.gap.toFixed(1)}</span>
                </span>
              </a>
            </li>
          ))}
        </ol>
        {recordText && (
          <p className="mt-1 px-2.5 text-xs">
            Straight-up record: picks won outright<span className="sm:hidden">, {recordText}</span>
          </p>
        )}
      </ResponsiveDisclosure>
    </section>
  );
}
