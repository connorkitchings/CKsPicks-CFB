import Link from "next/link";
import { Header, Footer } from "@/components/Header";
import { PageHeading } from "@/components/ui/PageHeading";
import { Card } from "@/components/ui/Card";
import { publicationScope } from "@/lib/publication";

export default function MethodologyPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={publicationScope.season}
        systemName={null}
        updatedAt={null}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
      />
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-8 text-sm leading-relaxed text-ink-muted">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">
          V5 model
        </p>
        <div className="mt-1">
          <PageHeading title="How the forecasts work" />
        </div>
      </div>

      <Card as="section" padding="none" className="p-5">
        <h2 className="text-lg font-semibold text-ink">Team strength</h2>
        <p className="mt-2">
          V5 measures offensive and defensive points per eligible possession,
          adjusts for the opponents played, and maintains one continuous rating
          for each team. Preseason evidence matters most before games are played.
          Completed games gradually take more weight. The ratings include
          uncertainty, which generally shrinks as evidence grows.
        </p>
      </Card>

      <Card as="section" padding="none" className="p-5">
        <h2 className="text-lg font-semibold text-ink">Game forecasts</h2>
        <p className="mt-2">
          A fixed Ridge bridge turns the two teams’ pregame ratings and
          earlier-known non-offense scoring context into a home-margin and
          game-total forecast. It was fit through the 2025 season. Neither 2026
          outcomes nor sportsbook lines fit this V5 model.
        </p>
      </Card>

      <Card as="section" padding="none" className="p-5">
        <h2 className="text-lg font-semibold text-ink">Schedule strength and record</h2>
        <p className="mt-2">
          Schedule strength (SOS) and strength of record (SOR) use the same
          ratings as the forecasts, computed once per season release. Every game,
          played or not, is scored with the current period’s ratings, so the SOS
          of a played game changes each week as the ratings learn. SOS is the
          average chance that the reference team loses the schedule’s games, times
          100; higher is harder. The ratings table shows each team’s SOS as a rank
          among FBS teams against an average FBS team, where 1 is the hardest
          schedule; the underlying number appears on hover. The elite-reference SOS
          is stored with the release but not shown.
        </p>
        <p className="mt-2">
          SOR is 100 minus the chance that an elite team, playing the same completed
          FBS schedule, finishes with at least this team’s record, so higher is a
          stronger résumé. The ratings table shows SOR as a rank, where 1 is the
          strongest résumé; the underlying number appears on hover. WAA (wins above
          an average FBS team on the same schedule) is stored with the release but
          not shown in the ratings table. SOR shows {"—"} until a
          team has 3 completed FBS games. W-L is “vs FBS”, and FCS games are
          excluded. Neutral sites are not adjusted because the model has no
          neutral-site term; home field is included.
        </p>
      </Card>

      <Card as="section" id="elite-reference" padding="none" className="p-5">
        <h2 className="text-lg font-semibold text-ink">Elite reference</h2>
        <p className="mt-2">
          The elite reference is the average rating of the period’s top 25 teams by
          overall rating. It is a descriptive yardstick for reading SOR, not an
          input to the model. SOR is the only elite-reference measure the ratings
          table shows; the elite-reference SOS is stored but not displayed.
        </p>
        <p className="mt-2">
          A team ranked in the top 25 is never measured against itself. Its elite
          reference is the other 24 top-25 teams plus the 26th-ranked team. Every
          other team, including the 26th-ranked team, is measured against the plain
          top-25 average.
        </p>
      </Card>

      <Card as="section" padding="none" className="p-5">
        <h2 className="text-lg font-semibold text-ink">Reading the record</h2>
        <p className="mt-2">
          The V5 model was fit through the 2025 season. Its 2026 forecasts use
          only information available before each game; 2026 outcomes do not
          retrain the model. Market comparison uses timestamped lines after the
          model forecast; missing eligible lines yield no grade.
        </p>
      </Card>

      <p>
        The historical V5 study established an accepted model design. It did not
        establish that V5 beats V4 in a like-for-like live comparison.{" "}
        <Link href="/performance" className="text-accent-ink underline">
          View the 2026 results
        </Link>
        .
      </p>
      </main>
      <Footer publicationMode={publicationScope.mode} />
    </div>
  );
}
