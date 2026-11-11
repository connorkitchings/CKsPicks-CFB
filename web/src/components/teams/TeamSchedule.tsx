import clsx from "clsx";
import TeamLogo from "@/components/TeamLogo";
import { Notice } from "@/components/ui/Notice";
import { AwaitingTag } from "@/components/slate/AwaitingTag";
import { MatchupCellLink, MatchupRowLink } from "@/components/teams/MatchupRowLink";
import { TeamGameRow, type TeamGame } from "@/components/teams/TeamGameRow";
import { TeamSection } from "@/components/teams/TeamSection";
import {
  atsResult, isFinal, lineForTeam, lineText, nextUpcomingGame, overUnderResult, recordText, teamRecords, winPercent, withByeWeeks,
  type ScheduleEntry,
  type BetResult,
} from "@/lib/team-games";
import { gameState } from "@/lib/slate";
import { phoneTeamName } from "@/lib/team-logos";
import { etDate } from "@/lib/time-et";

const TH = "px-1.5 pb-2 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-muted whitespace-nowrap";
const TD = "whitespace-nowrap border-t border-line px-1.5 py-2";
const NONE = <span className="text-ink-faint"><span aria-hidden>—</span><span className="sr-only">no data</span></span>;

const BET_TONE: Record<BetResult, string> = { W: "text-win", L: "text-loss", P: "text-ink-muted" };

function Outcome({ game, team }: { game: TeamGame; team: string }) {
  const [own, other] = game.homeTeam === team ? [game.homePoints, game.awayPoints] : [game.awayPoints, game.homePoints];
  if (own === null || other === null) return NONE;
  const letter = own === other ? "T" : own > other ? "W" : "L";
  return (
    <>
      <span className={clsx("inline-block min-w-5 rounded px-1.5 py-px text-center font-mono text-[11px] font-semibold", letter === "W" ? "bg-win-soft text-win" : letter === "L" ? "bg-loss-soft text-loss" : "bg-surface-inset text-ink-muted")}>{letter}</span>
      {" "}<span className="font-mono tabular-nums">{own}–{other}</span>
    </>
  );
}

/** A week the team did not play: not a game, so it carries no record, link or result cells. */
function ByeRow({ week }: { week: number }) {
  return (
    <tr data-testid="schedule-bye-row" className="text-ink-muted">
      <td className={clsx(TD, "font-mono")}>{week}</td>
      <td className={clsx(TD, "italic")} colSpan={8}>Bye<span className="sr-only"> week, no game</span></td>
    </tr>
  );
}

function ScheduleTable({ entries, team, now, nextId }: { entries: readonly ScheduleEntry<TeamGame>[]; team: string; now: Date; nextId: number | undefined }) {
  return (
    <div className="overflow-x-auto max-sm:hidden">
      <table aria-label="Lines and results" className="w-full text-sm tabular-nums">
        <thead>
          <tr>
            <th scope="col" className={TH}>Wk</th><th scope="col" className={TH}>Date</th><th scope="col" className={TH}>Opponent</th>
            <th scope="col" className={clsx(TH, "text-right")}>Line</th><th scope="col" className={clsx(TH, "text-right")}>Total</th>
            <th scope="col" className={TH}>Result</th><th scope="col" className={TH}>ATS</th><th scope="col" className={TH}>O/U</th>
            <th scope="col" className="sr-only">Matchup</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            if (entry.kind === "bye") return <ByeRow key={`bye-${entry.week}`} week={entry.week} />;
            const game = entry.game;
            const final = isFinal(game);
            const home = game.homeTeam === team;
            const opponent = home ? game.awayTeam : game.homeTeam;
            const line = lineForTeam(game, team);
            const ats = atsResult(game, team);
            const ou = overUnderResult(game);
            return (
              <tr key={game.gameId} data-testid={game.gameId === nextId ? "schedule-next-row" : undefined} className={clsx(!final && "text-ink-muted", game.gameId === nextId && "bg-accent-soft")}>
                <td className={clsx(TD, "font-mono")}>{game.week}</td>
                <td className={TD}>{etDate(game.startDate)}</td>
                <td className={TD}>
                  <span className="flex items-center gap-2">
                    <span className="w-4 text-xs text-ink-faint">{home ? "vs" : "at"}</span>
                    <TeamLogo name={opponent} px={22} />
                    <span className={clsx(final || game.gameId === nextId ? "font-medium text-ink" : "text-ink-muted")}>{phoneTeamName(opponent)}</span>
                  </span>
                </td>
                <td className={clsx(TD, "text-right font-mono")}>{line === null ? NONE : lineText(line)}</td>
                <td className={clsx(TD, "text-right font-mono")}>{game.totalLine === null ? NONE : game.totalLine.toFixed(1)}</td>
                <td className={TD}>{final ? <Outcome game={game} team={team} /> : gameState(game, now) === "awaiting" ? <AwaitingTag game={game} now={now} /> : NONE}</td>
                <td className={TD}>{ats ? <span className={clsx("font-semibold", BET_TONE[ats])}>{ats}</span> : NONE}</td>
                <td className={TD}>{ou ?? NONE}</td>
                <td className={clsx(TD, "text-right text-xs")}><MatchupCellLink gameId={game.gameId} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** The market records and cover rates over the games that have the data; nothing before any result. */
function RecordLine({ games, team }: { games: readonly TeamGame[]; team: string }) {
  const { ats, overUnder } = teamRecords(games, team);
  const cover = winPercent(ats.wins, ats.losses);
  const over = winPercent(overUnder.overs, overUnder.unders);
  const items = [
    ats.wins + ats.losses + ats.pushes > 0 && { label: "ATS (W–L)", value: recordText(ats.wins, ats.losses, ats.pushes), rate: cover && `${cover} cover` },
    overUnder.overs + overUnder.unders + overUnder.pushes > 0 && { label: "O/U (Over–Under)", value: recordText(overUnder.overs, overUnder.unders, overUnder.pushes), rate: over && `${over} over` },
  ].filter((item) => item !== false);
  if (items.length === 0) return null;
  return (
    <p data-testid="schedule-record" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-[13px] text-ink-muted">
      {items.map((item) => (
        <span key={item.label}>{item.label} <b className="font-mono font-medium tabular-nums text-ink">{item.value}</b>{item.rate && <> · {item.rate}</>}</span>
      ))}
    </p>
  );
}

/**
 * The schedule as a market-only lines-and-results table from `sm:` up and a two-line list on phones,
 * with the ATS and over/under records and cover rates underneath. The first unplayed game is highlighted;
 * a game past kickoff with no score yet is tagged "Awaiting result".
 */
export function TeamSchedule({ games, team, now }: { games: readonly TeamGame[]; team: string; now: Date }) {
  const nextId = nextUpcomingGame(games, now)?.gameId;
  const entries = withByeWeeks(games);
  return (
    <TeamSection id="team-games" title="Schedule · lines and results">
      {games.length === 0 ? <Notice tone="empty">No selected V5 forecasts are available yet.</Notice> : <>
        <ScheduleTable entries={entries} team={team} now={now} nextId={nextId} />
        <ul aria-label="Schedule" className="-mx-3.5 divide-y divide-line sm:hidden">
          {entries.map((entry) => entry.kind === "bye" ? (
            <li key={`bye-${entry.week}`} data-testid="schedule-bye-row" className="px-3.5 py-2 text-xs text-ink-muted">
              Wk {entry.week} · <span className="italic">Bye</span><span className="sr-only"> week, no game</span>
            </li>
          ) : (
            <li key={entry.game.gameId} className={clsx(entry.game.gameId === nextId && "bg-accent-soft")}>
              <MatchupRowLink gameId={entry.game.gameId}><TeamGameRow game={entry.game} team={team} now={now} next={entry.game.gameId === nextId} /></MatchupRowLink>
            </li>
          ))}
        </ul>
        <RecordLine games={games} team={team} />
      </>}
    </TeamSection>
  );
}
