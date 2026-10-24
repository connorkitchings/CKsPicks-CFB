import type { Rating } from "@/lib/v5";

const W = 300;
const H = 56;
const PAD = 6;


/** Overall rating by week as a small inline line, with the first and latest values labelled. */
export function RatingSparkline({ history }: { history: readonly Pick<Rating, "week" | "overallRating">[] }) {
  if (history.length < 2) return null;
  const values = history.map((row) => row.overallRating);
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const points = values.map((value, i): [number, number] => [
    PAD + (i / (values.length - 1)) * (W - 2 * PAD),
    H - PAD - ((value - min) / span) * (H - 2 * PAD),
  ]);
  const first = history[0];
  const last = history[history.length - 1];
  const summary = `Overall rating ${first.overallRating.toFixed(2)} in Week ${first.week}, ${last.overallRating.toFixed(2)} in Week ${last.week}`;
  const [lastX, lastY] = points[points.length - 1];
  return (
    <figure className="mb-3">
      <div className="relative h-14 text-accent-ink">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={summary} className="h-full w-full">
          <title>{summary}</title>
          <polyline points={points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        </svg>
        <span aria-hidden className="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-current" style={{ left: `${(lastX / W) * 100}%`, top: `${(lastY / H) * 100}%` }} />
      </div>
      <figcaption className="flex justify-between text-xs tabular-nums text-ink-muted" aria-hidden>
        <span>Wk {first.week} · {first.overallRating.toFixed(2)}</span>
        <span>Wk {last.week} · {last.overallRating.toFixed(2)}</span>
      </figcaption>
      <p className="sr-only">{summary}</p>
    </figure>
  );
}
