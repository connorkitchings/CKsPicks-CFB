import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Disclosure } from "@/components/ui/Disclosure";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ratingText } from "@/components/ratings/StatGrid";
import {
  adjustmentSentence,
  cumulativeByWeek,
  contributionText,
  pppText,
  priorPercent,
  ratingStanding,
  type RatingBreakdown as Breakdown,
  type UnitRatingBreakdown,
} from "@/lib/rating-breakdown";

type ReadyUnit = Extract<UnitRatingBreakdown, { status: "ready" }>;

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;
const rankText = (rank: number | null) => (rank === null ? "" : ` (#${rank})`);
const cell = "px-1 py-1.5 text-right font-mono tabular-nums";
const head = "px-1 py-1.5 text-right font-medium";

function UnitCard({ team, unit }: { team: string; unit: UnitRatingBreakdown }) {
  const title = `${team} ${unit.role}`;
  return (
    <Card as="article" aria-label={`${title} rating breakdown`} className="min-w-0 space-y-2">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {unit.status === "ready" ? <ReadyBody unit={unit} /> : (
        <p role="status" className="text-sm text-ink-muted">
          Breakdown unavailable for this rating. The stored components could not be matched to the rating shown above.
        </p>
      )}
    </Card>
  );
}

function ReadyBody({ unit }: { unit: ReadyUnit }) {
  const unused = unit.excluded.length;
  if (unit.completedGames === 0) {
    return (
      <>
        <p className="text-sm font-semibold tabular-nums text-ink">
          Rating {ratingText(unit.rating)}{rankText(unit.rank)}, {ratingStanding(unit.rating)}
        </p>
        <p className="text-xs text-ink-muted">
          No completed games yet · rating is the preseason estimate ({priorPercent(unit.priorWeight)})
          {unused > 0 && ` · ${unused} not used`}
        </p>
      </>
    );
  }
  const weeks = cumulativeByWeek(unit.games);
  const missingContext = unit.games.some((game) => game.missingContext);
  return (
    <>
      <p className="text-sm text-ink">{adjustmentSentence(unit.role, unit.rawPpp!, unit.adjustedPpp!)}</p>
      <p className="text-sm font-semibold tabular-nums text-ink">
        Rating {ratingText(unit.rating)}{rankText(unit.rank)}, {ratingStanding(unit.rating)}
      </p>
      <p className="text-xs text-ink-muted">
        {priorPercent(unit.priorWeight)} of this rating is the preseason estimate; the rest is this season&apos;s{" "}
        {plural(unit.completedGames, "game")} ({plural(Math.round(unit.possessions), "possession")})
        {unused > 0 && ` · ${unused} ${unused === 1 ? "game" : "games"} not used`}
      </p>
      <Disclosure title="Show the math">
        <p className="text-xs">
          Season to date after each week. Adjusted values re-score every past game with today&apos;s opponent ratings, so they
          can differ from earlier weeks.
        </p>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-collapse text-xs" aria-label={`${unit.role} season-to-date raw and adjusted points per possession`}>
            <thead>
              <tr className="border-b border-line text-ink-muted">
                <th scope="col" className="px-2 py-1.5 text-left font-medium">Through week</th>
                <th scope="col" className={head}>Raw</th>
                <th scope="col" className={head}>Adj.</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((row, index) => (
                <tr key={row.week} className={index === weeks.length - 1 ? "border-b border-line/60 font-semibold text-ink" : "border-b border-line/60"}>
                  <th scope="row" className="px-2 py-1.5 text-left font-normal text-ink">
                    <span className={index === weeks.length - 1 ? "font-semibold" : undefined}>Wk {row.week}</span>
                    <span className="block font-normal text-ink-muted">+ {row.added.join(", ")}</span>
                  </th>
                  <td className={cell}>{row.rawPpp === null ? "" : pppText(row.rawPpp)}</td>
                  <td className={cell}>
                    {row.adjustedPpp === null ? "" : pppText(row.adjustedPpp)}
                    {row.hasMissingContext && <sup title="No opponent context">†</sup>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs">
          The rating blends the season-to-date adjusted number (on the standardized scale) with the preseason estimate, which
          is {priorPercent(unit.priorWeight)} of this rating.
        </p>
        {missingContext && (
          <p className="mt-2 text-xs">† No opponent context was available, so the raw value was used as the adjusted value.</p>
        )}
        {unused > 0 && (
          <div className="mt-2 text-xs">
            <p className="font-medium">Not used by the rating</p>
            <ul className="list-disc pl-4">
              {unit.excluded.map((game) => (
                <li key={game.gameId}>
                  {game.opponent ?? "Opponent unknown"} (Wk {game.week}): {game.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
        <Disclosure title="Audit detail: each game's effect on the rating" className="mt-3">
          {/* Nested padding leaves the four-column table 2px short at 320px; reclaim it. */}
          <div className="-mx-2 overflow-x-auto">
            <table className="w-full border-collapse text-xs" aria-label={`${unit.role} game-by-game effect on rating`}>
              <thead>
                <tr className="border-b border-line text-ink-muted">
                  <th scope="col" className="px-2 py-1.5 text-left font-medium">Opponent</th>
                  <th scope="col" className={head}>Raw</th>
                  <th scope="col" className={head}>Adj.</th>
                  <th scope="col" className={head}>Effect on rating</th>
                </tr>
              </thead>
              <tbody>
                {unit.games.map((game) => (
                  <tr key={game.gameId} className="border-b border-line/60">
                    <th scope="row" className="px-2 py-1.5 text-left font-normal text-ink">
                      {game.opponent ?? "Opponent unknown"}
                      <span className="block text-ink-muted">Wk {game.week} · {Math.round(game.exposure)} poss.</span>
                    </th>
                    <td className={cell}>{pppText(game.rawPpp)}</td>
                    <td className={cell}>{pppText(game.adjustedPpp)}{game.missingContext && <sup title="No opponent context">†</sup>}</td>
                    <td className={cell}>{contributionText(game.contribution)}</td>
                  </tr>
                ))}
                <tr className="border-b border-line/60">
                  <th scope="row" className="px-2 py-1.5 text-left font-normal text-ink">Preseason estimate</th>
                  <td className={cell} />
                  <td className={cell} />
                  <td className={cell}>{contributionText(unit.priorContribution)}</td>
                </tr>
              </tbody>
              <tfoot>
                <tr className="font-semibold text-ink">
                  <th scope="row" className="px-2 py-1.5 text-left">Rating</th>
                  <td className={cell} colSpan={2} />
                  <td className={cell}>{ratingText(unit.rating)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Disclosure>
      </Disclosure>
    </>
  );
}

/** Two cards per column, paired like the unit comparisons above: an offense and the defense it faces. */
export function RatingBreakdown({ awayTeam, homeTeam, breakdown }: { awayTeam: string; homeTeam: string; breakdown: Breakdown }) {
  return (
    <section aria-labelledby="rating-breakdown-heading" className="space-y-3">
      <SectionHeading id="rating-breakdown-heading">How the ratings are built</SectionHeading>
      <p className="text-xs leading-relaxed text-ink-muted">
        Each rating measures one thing: points scored (or allowed) per possession, adjusted for the strength of opponents.
        The Team stats tables above are shown for context and do not feed the rating. 0 is an average team and higher is
        better, including defense (allowing fewer points gives a higher rating); the preseason estimate counts for less as
        games are played (see the <Link href="/model/method#prior" className="underline hover:text-accent-ink">prior</Link> and{" "}
        <Link href="/model/method#updates" className="underline hover:text-accent-ink">updates</Link> methods).
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 space-y-4">
          <UnitCard team={awayTeam} unit={breakdown.awayOffense} />
          <UnitCard team={homeTeam} unit={breakdown.homeDefense} />
        </div>
        <div className="min-w-0 space-y-4">
          <UnitCard team={homeTeam} unit={breakdown.homeOffense} />
          <UnitCard team={awayTeam} unit={breakdown.awayDefense} />
        </div>
      </div>
    </section>
  );
}
