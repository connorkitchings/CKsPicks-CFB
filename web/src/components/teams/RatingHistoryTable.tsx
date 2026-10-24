import { Card } from "@/components/ui/Card";
import type { Rating } from "@/lib/v5";

/** Weeks shown before the rest fold into "Earlier weeks". */
const RECENT_WEEKS = 4;

function Table({ rows, head }: { rows: readonly Rating[]; head: boolean }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <thead className={head ? "border-b border-line bg-surface-inset text-xs uppercase tracking-wide text-ink-faint" : "sr-only"}>
        <tr><th scope="col" className="px-3 py-3 text-left sm:px-4">Week</th><th scope="col" className="px-3 py-3 text-right">Overall</th><th scope="col" className="px-3 py-3 text-right">OFF</th><th scope="col" className="px-3 py-3 text-right">DEF</th><th scope="col" className="px-4 py-3 text-right max-sm:hidden">Uncertainty</th></tr>
      </thead>
      <tbody>
        {rows.map((rating, index) => (
          <tr key={`${rating.cutoffUtc.toISOString()}-${index}`} className="border-b border-line last:border-0">
            <td className="px-3 py-3 text-ink sm:px-4">Week {rating.week}</td>
            <td className="px-3 py-3 text-right text-ink">{rating.overallRating.toFixed(2)}</td>
            <td className="px-3 py-3 text-right text-ink-muted">{rating.offenseRating.toFixed(2)}</td>
            <td className="px-3 py-3 text-right text-ink-muted">{rating.defenseRating.toFixed(2)}</td>
            <td className="px-4 py-3 text-right text-ink-muted max-sm:hidden">±{Math.sqrt(Math.max(0, rating.overallVariance)).toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Pregame ratings, newest week first; weeks before the most recent few sit behind a native disclosure. */
export function RatingHistoryTable({ history }: { history: readonly Rating[] }) {
  const newestFirst = [...history].reverse();
  const recent = newestFirst.slice(0, RECENT_WEEKS);
  const earlier = newestFirst.slice(RECENT_WEEKS);
  return (
    <Card padding="none">
      <Table rows={recent} head />
      {earlier.length > 0 && (
        <details className="border-t border-line">
          <summary className="flex min-h-11 cursor-pointer items-center px-3 text-sm font-medium text-accent-ink sm:px-4">Show earlier weeks ({earlier.length})</summary>
          <Table rows={earlier} head={false} />
        </details>
      )}
    </Card>
  );
}
