import { PhoneSwap } from "@/components/ui/PhoneSwap";
import TeamLogo from "@/components/TeamLogo";
import { signedSpread } from "@/lib/betting-format";
import type { UnderdogPick, Tally } from "@/lib/slate";
import { phoneTeamName } from "@/lib/team-logos";

/** Season straight-up record text for the Underdog picks view, or null before any scored week. */
export function underdogRecordText(record: Tally | null | undefined, season: number): string | null {
  return record && record.win + record.loss > 0 ? `${season}: ${record.win}–${record.loss} straight up` : null;
}

/**
 * Games where the model picks the consensus-line underdog to win outright, largest gap between the
 * model and the market first. About who wins, not odds: no prices or payouts. Section and disclosure
 * live in FeaturedGames, which only renders this when `picks` is non-empty.
 */
export function UnderdogPicksBody({ picks, recordText }: { picks: UnderdogPick[]; recordText: string | null }) {
  return (
    <>
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
    </>
  );
}
