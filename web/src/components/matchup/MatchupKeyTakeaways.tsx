import Link from "next/link";

export function MatchupKeyTakeaways({
  awayTeam,
  homeTeam,
  takeaways,
}: {
  awayTeam: string;
  homeTeam: string;
  takeaways: string[];
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-bold uppercase tracking-wider text-ink">
          Key Matchup Takeaways & Model Notes
        </h3>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
          Analysis
        </span>
      </div>

      <ul className="space-y-2 text-xs leading-relaxed text-ink-muted">
        {takeaways.map((note, index) => (
          <li key={index} className="flex items-start gap-2">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            <span>{note}</span>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line/60 pt-3 text-xs text-ink-faint">
        <span>Deep dive team ratings:</span>
        <Link
          href={`/teams/${encodeURIComponent(awayTeam)}`}
          className="font-medium text-accent-ink hover:underline"
        >
          {awayTeam} Ratings History →
        </Link>
        <span>·</span>
        <Link
          href={`/teams/${encodeURIComponent(homeTeam)}`}
          className="font-medium text-accent-ink hover:underline"
        >
          {homeTeam} Ratings History →
        </Link>
      </div>
    </div>
  );
}
