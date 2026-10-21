import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { PageShell } from "@/components/PageShell";
import { ModelTabs } from "@/components/model/ModelTabs";
import { Card } from "@/components/ui/Card";
import { PageHeading } from "@/components/ui/PageHeading";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { BREAK_EVEN_PCT } from "@/lib/betting-format";
import { publicationScope } from "@/lib/publication";

export const metadata: Metadata = { title: "How the model works" };

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <Card as="section" id={id} aria-labelledby={`${id}-heading`}>
      <SectionHeading id={`${id}-heading`}>{title}</SectionHeading>
      <div className="mt-2 max-w-prose space-y-2 text-sm leading-relaxed text-ink-muted">{children}</div>
    </Card>
  );
}

const code = "rounded bg-surface-inset px-1 py-0.5 font-mono text-xs break-words";

export default function ModelMethodPage() {
  return (
    <PageShell
      width="wide"
      header={{
        season: publicationScope.season,
        systemName: null,
        updatedAt: null,
        allowedSeasons: publicationScope.allowedSeasons,
      }}
      mainClassName="space-y-4 py-3 sm:py-6"
    >
      <ModelTabs active="method" />
      <PageHeading title="How the model works" eyebrow="V5 model">
        <span className="block max-w-prose">
          What the forecasts measure, how they are turned into a spread and a total, and how the record is graded.
        </span>
      </PageHeading>

      <Section id="team-strength" title="Team strength: points per possession">
        <p>
          V5 rates every team on offense and on defense by how many points it scores or allows per possession.
        </p>
        <p>
          The ratings adjust for the opponents played and carry on as one continuous rating for each team across the
          season. Opponent strength is handled in the football measurement itself so schedule strength is not counted
          twice. Each rating comes with an uncertainty that generally shrinks as evidence grows.
        </p>
      </Section>

      <Section id="prior" title="The learned prior">
        <p>
          Before a team has played, its rating starts from a prior rather than from a blank slate. The accepted prior
          uses a 0.60 carryover (written ρ = 0.60): a fixed share of what the model already knew about a team
          carries forward instead of resetting every team to average. Preseason evidence matters most before games are
          played; completed games gradually take more weight.
        </p>
      </Section>

      <Section id="updates" title="Exposure-weighted updates">
        <p>
          After each game, the ratings update in proportion to how much the game actually showed. A game with more
          possessions is stronger evidence than one with fewer, so it moves the ratings more. The accepted
          candidate combines the points-per-possession measure, the 0.60 carryover and these exposure-weighted updates
          (<code className={code}>ppp__rho_0_60__exposure</code>).
        </p>
      </Section>

      <Section id="uncertainty" title="Uncertainty and intervals">
        <p>
          Forecasts are not single numbers. Each margin and total comes with an interval that reflects how well the
          two ratings are known, and rating uncertainty generally shrinks as evidence grows. In the 2025 review, the 80% intervals
          covered 80.1% of margins and 82.0% of totals, so the stated range matched how often games landed inside it.
        </p>
      </Section>

      <Section id="forecasts" title="Game forecasts: the Ridge bridge">
        <p>
          A fixed Ridge regression, called the bridge, turns the two teams’ pregame ratings and earlier-known
          non-offense scoring context into a home-margin forecast and a game-total forecast. It was fit through the 2025
          season on 2015–2019 and 2021–2025 (2020 is excluded throughout). Neither 2026 outcomes nor sportsbook lines
          refit it: bookmaker lines never enter the model’s features.
        </p>
        <p>
          The 2025 historical review reported a margin error of 14.160 points and a total error of 13.356 points
          (mean absolute error) across 934 games per target. A separate postseason market comparison had lower
          market error on both targets. There is no like-for-like point-in-time V4 backtest, so the evidence does
          not establish that V5 beats V4.
        </p>
      </Section>

      <Section id="grading" title="Grading the record">
        <p>
          The public record is one cumulative V5 record from Week 0, with spreads and totals counted separately. A pick
          is the model’s side measured against its chosen eligible quote, then settled as a win, loss or push against the
          certified final score. Every forecast with an eligible line is graded, with no edge threshold. A game without
          an eligible line is left ungraded rather than counted as a win or loss.
        </p>
        <p>
          Quotes captured strictly before kickoff come first. For each game and target the grader shops the captured
          quotes for the model’s side and takes the best one, so this is a best-available-line comparison, not a claim
          that a particular price was open when a pick was published. Pushes are counted as pushes, and win rate
          excludes them. The reference to beat is a {BREAK_EVEN_PCT}% win rate, the break-even at standard pricing.
        </p>
        <p>
          Limits: capture times are when a line was fetched, not when a sportsbook posted it. Some design decisions were
          made with early 2026 outcomes known, though those outcomes do not fit any parameter, so reconstructed
          weeks are not blind forward tests.{" "}
          <Link href="/model" className="font-semibold text-accent-ink underline">
            See the 2026 record
          </Link>
          .
        </p>
      </Section>

      <Section id="sos-sor" title="Schedule strength and record">
        <p>
          Schedule strength (SOS) and strength of record (SOR) use the same ratings as the forecasts, computed once per
          season release. Every game, played or not, is scored with the current period’s ratings, so the SOS of a
          played game changes each week as the ratings learn. SOS is the average chance that the reference team loses
          the schedule’s games, times 100; higher is harder. The ratings table shows each team’s SOS as a rank among FBS
          teams against an average FBS team, where 1 is the hardest schedule; the underlying number appears on hover.
          The elite-reference SOS is stored with the release but not shown.
        </p>
        <p>
          SOR is 100 minus the chance that an elite team, playing the same completed FBS schedule, finishes with at
          least this team’s record, so higher is a stronger résumé. The ratings table shows SOR as a rank, where 1 is the
          strongest résumé; the underlying number appears on hover. WAA (wins above an average FBS team on the same
          schedule) is stored with the release but not shown in the ratings table. SOR shows {"—"} until a team has 3
          completed FBS games. W-L is “vs FBS”, and FCS games are excluded. Neutral sites are not adjusted because the
          model has no neutral-site term; home field is included.
        </p>
      </Section>

      <Section id="elite-reference" title="Elite reference">
        <p>
          The elite reference is the average rating of the period’s top 25 teams by overall rating. It is a descriptive
          yardstick for reading SOR, not an input to the model. SOR is the only elite-reference measure the ratings
          table shows; the elite-reference SOS is stored but not displayed.
        </p>
        <p>
          A team ranked in the top 25 is never measured against itself. Its elite reference is the other 24 top-25 teams
          plus the 26th-ranked team. Every other team, including the 26th-ranked team, is measured against the plain
          top-25 average.
        </p>
      </Section>

      <Section id="reading-the-record" title="Reading the record">
        <p>
          The V5 model was fit through the 2025 season. Its 2026 forecasts use only information available before each
          game; 2026 outcomes do not retrain the model. Market comparison uses timestamped lines after the model
          forecast; missing eligible lines yield no grade. The historical V5 study established an accepted model
          design. It did not establish that V5 beats V4 in a like-for-like live comparison.
        </p>
      </Section>
    </PageShell>
  );
}
