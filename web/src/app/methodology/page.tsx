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
