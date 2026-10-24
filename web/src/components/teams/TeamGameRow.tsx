import TeamLogo from "@/components/TeamLogo";
import { dayShort } from "@/components/slate/format";
import { gameResultText, isFinal, type TeamGameFields } from "@/lib/team-games";
import { phoneTeamName } from "@/lib/team-logos";

export interface TeamGame extends TeamGameFields {
  gameId: number;
  week: number;
  startDate: Date;
}

/** One schedule line from `team`'s side: opponent, week and date, and the score or forecast. */
export function TeamGameRow({ game, team }: { game: TeamGame; team: string }) {
  const home = game.homeTeam === team;
  const opponent = home ? game.awayTeam : game.homeTeam;
  const result = gameResultText(game, team);
  const final = isFinal(game);
  return (
    <div>
      <div className="flex items-center gap-2">
        <TeamLogo name={opponent} px={24} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink"><span className="font-normal text-ink-muted">{home ? "vs" : "at"}</span> {phoneTeamName(opponent)}</p>
          <p className="text-xs text-ink-muted">Wk {game.week} · {dayShort(game.startDate)}</p>
        </div>
        {final && result && <p className="shrink-0 font-mono text-sm font-semibold tabular-nums text-ink">{result}</p>}
      </div>
      {!final && result && <p className="mt-1 pl-8 text-xs tabular-nums text-ink-muted">{result}</p>}
    </div>
  );
}
