import clsx from "clsx";
import TeamLogo from "@/components/TeamLogo";
import { AwaitingTag } from "@/components/slate/AwaitingTag";
import { dayShort } from "@/components/slate/format";
import {
  atsResult, gameResultText, isFinal, lineForTeam, lineText, overUnderResult,
  type TeamGameFields, type TeamGameLines,
} from "@/lib/team-games";
import { phoneTeamName } from "@/lib/team-logos";

export interface TeamGame extends TeamGameFields, TeamGameLines {
  gameId: number;
  week: number;
  startDate: Date;
}

/** The second line of a row: line, ATS and over/under once final; line and total before. */
function detailParts(game: TeamGame, team: string): [label: string, value: string][] {
  const line = lineForTeam(game, team);
  const total = game.totalLine === null ? null : game.totalLine.toFixed(1);
  const parts: [string, string | null][] = isFinal(game)
    ? [["Line", line === null ? null : lineText(line)], ["ATS", atsResult(game, team)], [overUnderResult(game) ?? "Total", total]]
    : [["Line", line === null ? null : lineText(line)], ["Total", total]];
  return parts.filter((part): part is [string, string] => part[1] !== null);
}

/**
 * One schedule line from `team`'s side: opponent, week and date, the score once final, and a
 * second line with the market line and bet results (or the line and total before kickoff).
 * A kicked-off game with no score yet is tagged "Awaiting result". Upcoming games are dimmed unless they are the team's `next` game.
 */
export function TeamGameRow({ game, team, now, next = false }: { game: TeamGame; team: string; now: Date; next?: boolean }) {
  const home = game.homeTeam === team;
  const opponent = home ? game.awayTeam : game.homeTeam;
  const final = isFinal(game);
  const result = final ? gameResultText(game, team) : null;
  const details = detailParts(game, team);
  return (
    <div>
      <div className="flex items-center gap-2">
        <TeamLogo name={opponent} px={24} />
        <div className="min-w-0 flex-1">
          <p className={clsx("truncate text-sm font-semibold", final || next ? "text-ink" : "text-ink-muted")}><span className="font-normal text-ink-muted">{home ? "vs" : "at"}</span> {phoneTeamName(opponent)}</p>
          <p className="text-xs text-ink-muted">Wk {game.week} · {dayShort(game.startDate)}</p>
        </div>
        {result ? <p className="shrink-0 font-mono text-sm font-semibold tabular-nums text-ink">{result}</p> : <AwaitingTag game={game} now={now} className="shrink-0" />}
      </div>
      {details.length > 0 && (
        <p className="mt-1 pl-8 text-xs text-ink-muted">
          {next && "Next · "}
          {details.map(([label, value], i) => (
            <span key={label}>{i > 0 && " · "}{label} <b className="font-mono font-medium tabular-nums text-ink">{value}</b></span>
          ))}
        </p>
      )}
    </div>
  );
}
