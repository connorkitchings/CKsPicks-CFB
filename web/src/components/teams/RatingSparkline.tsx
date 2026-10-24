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
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary} className="h-14 w-full text-accent-ink">
        <title>{summary}</title>
        <polyline points={points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        <circle cx={lastX} cy={lastY} r="3.5" fill="currentColor" />
      </svg>
      <figcaption className="flex justify-between text-xs tabular-nums text-ink-muted" aria-hidden>
        <span>Wk {first.week} · {first.overallRating.toFixed(2)}</span>
        <span>Wk {last.week} · {last.overallRating.toFixed(2)}</span>
      </figcaption>
      <p className="sr-only">{summary}</p>
    </figure>
  );
}
