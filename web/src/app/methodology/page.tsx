import Link from "next/link";
import { PageHeading } from "@/components/ui/PageHeading";

export default function MethodologyPage() {
  return (
    <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8 text-sm leading-relaxed text-ink-muted">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">
          V5 model
        </p>
        <div className="mt-1">
          <PageHeading title="How the forecasts work" />
        </div>
      </div>

      <section className="rounded-xl border border-line bg-surface-card p-5">
        <h2 className="text-lg font-semibold text-ink">Team strength</h2>
        <p className="mt-2">
          V5 measures offensive and defensive points per eligible possession,
          adjusts for the opponents played, and maintains one continuous rating
          for each team. Preseason evidence matters most before games are played.
          Completed games gradually take more weight. The ratings include
          uncertainty, which generally shrinks as evidence grows.
        </p>
      </section>

      <section className="rounded-xl border border-line bg-surface-card p-5">
        <h2 className="text-lg font-semibold text-ink">Game forecasts</h2>
        <p className="mt-2">
          A fixed Ridge bridge turns the two teams’ pregame ratings and
          earlier-known non-offense scoring context into a home-margin and
          game-total forecast. It was fit through the 2025 season. Neither 2026
          outcomes nor sportsbook lines fit this V5 model.
        </p>
      </section>

      <section className="rounded-xl border border-line bg-surface-card p-5">
        <h2 className="text-lg font-semibold text-ink">Schedule strength and record</h2>
        <p className="mt-2">
          Schedule strength (SOS) and strength of record (SOR) use the same
          ratings as the forecasts, computed once per season release. Every game,
          played or not, is scored with the current period’s ratings, so the SOS
          of a played game changes each week as the ratings learn. SOS is the
          average chance that the reference team loses the schedule’s games, times
          100; higher is harder. Compare SOS values only within one reference, since
          an elite team wins more often and its values run lower than the average
          reference’s.
        </p>
        <p className="mt-2">
          SOR is 100 minus the chance that an elite team, playing the same completed
          FBS schedule, finishes with at least this team’s record, so higher is a
          stronger résumé. WAA is the team’s wins minus the wins an average FBS team
          would be expected to earn on that schedule. SOR and WAA show {"—"} until a
          team has 3 completed FBS games. W-L is “vs FBS”, and FCS games are
          excluded. Neutral sites are not adjusted because the model has no
          neutral-site term; home field is included.
        </p>
      </section>

      <section id="elite-reference" className="rounded-xl border border-line bg-surface-card p-5">
        <h2 className="text-lg font-semibold text-ink">Elite reference</h2>
        <p className="mt-2">
          The elite reference is the average rating of the period’s top 25 teams by
          overall rating. It is a descriptive yardstick for reading SOR and SOS, not
          an input to the model. Elite is the primary SOS reference, with the average
          reference shown alongside it.
        </p>
        <p className="mt-2">
          A team ranked in the top 25 is never measured against itself. Its elite
          reference is the other 24 top-25 teams plus the 26th-ranked team. Every
          other team, including the 26th-ranked team, is measured against the plain
          top-25 average.
        </p>
      </section>

      <section className="rounded-xl border border-line bg-surface-card p-5">
        <h2 className="text-lg font-semibold text-ink">Reading the record</h2>
        <p className="mt-2">
          The V5 model was fit through the 2025 season. Its 2026 forecasts use
          only information available before each game; 2026 outcomes do not
          retrain the model. Market comparison uses timestamped lines after the
          model forecast; missing eligible lines yield no grade.
        </p>
      </section>

      <p>
        The historical V5 study established an accepted model design. It did not
        establish that V5 beats V4 in a like-for-like live comparison.{" "}
        <Link href="/performance" className="text-accent-ink underline">
          View the 2026 results
        </Link>
        .
      </p>
    </main>
  );
}
