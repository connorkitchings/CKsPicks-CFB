import clsx from "clsx";
import TeamLogo from "@/components/TeamLogo";
import { type TeamGame } from "@/components/teams/TeamGameRow";
import { TeamSection } from "@/components/teams/TeamSection";
import {
  isFinal, modelPickedWinner, modelRecords, modelSpreadPick, modelTotalPick, modelWinnerName, recordText, winPercent,
  type BetResult, type ModelPick,
} from "@/lib/team-games";
import { phoneTeamName } from "@/lib/team-logos";

const TH = "px-1.5 pb-2 text-left text-[10px] font-semibold uppercase tracking-wider text-ink-muted whitespace-nowrap";
const TD = "whitespace-nowrap border-t border-line px-1.5 py-2";
const NONE = <span className="text-ink-faint">—</span>;

const MARKS: Record<BetResult, { text: string; label: string; tone: string }> = {
  W: { text: "✓", label: "Hit", tone: "text-win" },
  L: { text: "✗", label: "Miss", tone: "text-loss" },
  P: { text: "P", label: "Push", tone: "text-ink-muted" },
};

/** The hit, miss or push mark of a graded pick; nothing before the game is final. */
function Mark({ result }: { result: BetResult | null | undefined }) {
  if (!result) return null;
  const { text, label, tone } = MARKS[result];
  return <span role="img" aria-label={label} className={clsx("ml-1 font-semibold", tone)}>{text}</span>;
}

/** A pick with its mark; "No line" when only the market is missing, "No pick" without a forecast. */
function PickCell({ pick, game }: { pick: ModelPick | null; game: TeamGame }) {
  if (pick) return <><span className="font-mono">{pick.label}</span><Mark result={pick.result} /></>;
  return <span className="text-ink-faint">{game.predictedMargin === null && game.predictedTotal === null ? "No pick" : "No line"}</span>;
}

function WinnerCell({ game, team }: { game: TeamGame; team: string }) {
  const name = modelWinnerName(game);
  if (name === null) return <span className="text-ink-faint">No pick</span>;
  const right = modelPickedWinner(game, team);
  return <>{name}{right !== null && <Mark result={right ? "W" : "L"} />}</>;
}

function OpponentCell({ game, team, px }: { game: TeamGame; team: string; px: number }) {
  const home = game.homeTeam === team;
  const opponent = home ? game.awayTeam : game.homeTeam;
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span className="w-4 shrink-0 text-xs text-ink-faint">{home ? "vs" : "at"}</span>
      <TeamLogo name={opponent} px={px} />
      <span className="truncate font-medium">{phoneTeamName(opponent)}</span>
    </span>
  );
}

function Summary({ games, team }: { games: readonly TeamGame[]; team: string }) {
  const { ats, overUnder, winner } = modelRecords(games, team);
  const items = [
    ats.wins + ats.losses + ats.pushes > 0 && { label: "ATS (W–L)", value: recordText(ats.wins, ats.losses, ats.pushes), rate: winPercent(ats.wins, ats.losses) },
    overUnder.wins + overUnder.losses + overUnder.pushes > 0 && { label: "O/U", value: recordText(overUnder.wins, overUnder.losses, overUnder.pushes), rate: winPercent(overUnder.wins, overUnder.losses) },
    winner.right + winner.wrong > 0 && { label: "Model picked the winner", value: recordText(winner.right, winner.wrong), rate: winPercent(winner.right, winner.wrong) },
  ].filter((item) => item !== false);
  if (items.length === 0) return null;
  return (
    <p data-testid="model-record" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-[13px] text-ink-muted">
      {items.map((item) => (
        <span key={item.label}>{item.label} <b className="font-mono font-medium tabular-nums text-ink">{item.value}</b>{item.rate && <> · {item.rate}</>}</span>
      ))}
    </p>
  );
}

/**
 * How the model's pregame picks did on this team's games: its spread and total side against the
 * market, with a hit/miss/push mark, and the winner it had. Picks follow the app's lean rule
 * (no minimum edge). Upcoming games with a forecast show the current lean (or "No line"), dimmed.
 */
export function ModelOnTeam({ games, team }: { games: readonly TeamGame[]; team: string }) {
  const rows = games.filter((game) => isFinal(game) || game.predictedMargin !== null || game.predictedTotal !== null);
  if (rows.length === 0) return null;
  return (
    <TeamSection id="team-model" title="Model on this team">
      <div className="overflow-x-auto max-sm:hidden">
        <table aria-label="Model picks" className="w-full text-sm tabular-nums">
          <thead>
            <tr>
              <th scope="col" className={TH}>Wk</th><th scope="col" className={TH}>Opponent</th>
              <th scope="col" className={TH}>ATS pick</th><th scope="col" className={TH}>O/U pick</th><th scope="col" className={TH}>Winner</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((game) => (
              <tr key={game.gameId} className={clsx(!isFinal(game) && "text-ink-muted opacity-70")}>
                <td className={clsx(TD, "font-mono")}>{game.week}</td>
                <td className={TD}><OpponentCell game={game} team={team} px={22} /></td>
                <td className={TD}><PickCell pick={modelSpreadPick(game)} game={game} /></td>
                <td className={TD}><PickCell pick={modelTotalPick(game)} game={game} /></td>
                <td className={TD}>{isFinal(game) ? <WinnerCell game={game} team={team} /> : NONE}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul aria-label="Model picks" className="-mx-3.5 divide-y divide-line sm:hidden">
        {rows.map((game) => (
          <li key={game.gameId} className={clsx("px-3 py-2.5", !isFinal(game) && "text-ink-muted opacity-70")}>
            <div className="flex items-center gap-2 text-sm"><div className="min-w-0 flex-1"><OpponentCell game={game} team={team} px={24} /></div><span className="shrink-0 text-xs text-ink-muted">Wk {game.week}</span></div>
            <p className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 pl-8 text-xs text-ink-muted">
              <span>ATS <b className="font-medium text-ink"><PickCell pick={modelSpreadPick(game)} game={game} /></b></span>
              <span>O/U <b className="font-medium text-ink"><PickCell pick={modelTotalPick(game)} game={game} /></b></span>
            </p>
          </li>
        ))}
      </ul>
      <Summary games={games} team={team} />
      <p className="mt-2 text-xs text-ink-muted">Model picks use the pregame forecast for each game. Display only — not betting advice.</p>
    </TeamSection>
  );
}
