import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Disclosure } from "@/components/ui/Disclosure";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ratingText } from "@/components/ratings/StatGrid";
import {
  contributionText,
  pppText,
  priorPercent,
  type RatingBreakdown as Breakdown,
  type UnitRatingBreakdown,
} from "@/lib/rating-breakdown";

type ReadyUnit = Extract<UnitRatingBreakdown, { status: "ready" }>;

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;
const cell = "px-1 py-1.5 text-right font-mono tabular-nums";
const head = "px-1 py-1.5 text-right font-medium";

function UnitCard({ team, unit }: { team: string; unit: UnitRatingBreakdown }) {
  const defense = unit.role === "defense";
  const title = `${team} ${unit.role}`;
  return (
    <Card as="article" aria-label={`${title} rating breakdown`} className="min-w-0 space-y-2">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {unit.status === "ready" ? <ReadyBody unit={unit} defense={defense} /> : (
        <p role="status" className="text-sm text-ink-muted">
          Breakdown unavailable for this rating. The stored components could not be matched to the rating shown above.
        </p>
      )}
    </Card>
  );
}

function ReadyBody({ unit, defense }: { unit: ReadyUnit; defense: boolean }) {
  const unused = unit.excluded.length;
  if (unit.completedGames === 0) {
    return (
      <>
        <p className="text-sm text-ink">
          No completed games yet · rating is the preseason prior ({priorPercent(unit.priorWeight)})
          {unused > 0 && ` · ${unused} not used`}
        </p>
        <p className="font-mono text-sm tabular-nums text-ink">
          Rating {ratingText(unit.rating)}{unit.rank !== null && ` (#${unit.rank})`}
        </p>
      </>
    );
  }
  const missingContext = unit.games.some((game) => game.missingContext);
  return (
    <>
      <p className="font-mono text-sm tabular-nums text-ink">
        Raw PPP{defense && " allowed"} {pppText(unit.rawPpp!)} → adjusted {pppText(unit.adjustedPpp!)} → rating{" "}
        {ratingText(unit.rating)}{unit.rank !== null && ` (#${unit.rank})`}
      </p>
      <p className="text-xs text-ink-muted">
        Prior {priorPercent(unit.priorWeight)} · {plural(unit.completedGames, "game")}, {Math.round(unit.possessions)} possessions
        {unused > 0 && ` · ${unused} not used`}
      </p>
      <Disclosure title="Game-by-game">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs" aria-label={`${unit.role} game-by-game contributions`}>
            <thead>
              <tr className="border-b border-line text-ink-muted">
                <th scope="col" className="px-2 py-1.5 text-left font-medium">Opponent</th>
                <th scope="col" className={head}>Raw</th>
                <th scope="col" className={head}>Adj.</th>
                <th scope="col" className={head}>Contrib.</th>
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
                <th scope="row" className="px-2 py-1.5 text-left font-normal text-ink">Preseason prior</th>
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
      </Disclosure>
    </>
  );
}

/** Two cards per column, paired like the unit comparisons above: an offense and the defense it faces. */
export function RatingBreakdown({ awayTeam, homeTeam, breakdown }: { awayTeam: string; homeTeam: string; breakdown: Breakdown }) {
  return (
    <section aria-labelledby="rating-breakdown-heading" className="space-y-3">
      <SectionHeading id="rating-breakdown-heading">How the ratings are built</SectionHeading>
      <div className="space-y-1.5 text-xs leading-relaxed text-ink-muted">
        <p>
          Ratings use opponent-adjusted scoring per possession plus a shrinking preseason prior. The Team stats tables
          above show raw statistics and are not combined to form the rating.
        </p>
        <p>
          The prior plus the per-game contributions add up to the rating. The prior&apos;s share shrinks as possessions
          accumulate (see the <Link href="/model/method#prior" className="underline hover:text-accent-ink">prior</Link> and{" "}
          <Link href="/model/method#updates" className="underline hover:text-accent-ink">updates</Link> methods). Defense rows
          measure the opposing offense, and a higher defense rating means allowing less. Ratings are on a standardized scale,
          not points, and small rank gaps are near ties. Games with incomplete data are left out or used without opponent context.
        </p>
      </div>
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
