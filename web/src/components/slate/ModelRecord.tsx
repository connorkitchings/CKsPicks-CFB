import clsx from "clsx";
import Link from "next/link";
import type { Performance } from "@/lib/v5";
import { winRatePct } from "@/lib/slate";
import { Card } from "@/components/ui/Card";

type Rec = { win: number; loss: number; push: number };
const ZERO: Rec = { win: 0, loss: 0, push: 0 };

/**
 * Compact record cell:
 * Top row: category label on left, decided count on right.
 * Main row: monospace W-L-P record on left, win rate % with benchmark context on right.
 */
function RecordCell({ label, rec }: { label: string; rec: Rec }) {
  const rate = winRatePct(rec.win, rec.loss);
  const isAboveBreakEven = rate !== null && rate >= 52.4;

  return (
    <div className="flex flex-col items-stretch justify-center gap-1 rounded-lg border border-line bg-surface-inset p-2 text-center">
      <span className="text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {label}
      </span>
      <div className="flex items-center justify-between gap-1 max-[360px]:flex-col max-[360px]:items-start">
        <div className="font-mono text-base font-bold tracking-tight tabular-nums text-ink sm:text-lg">
          {rec.win}–{rec.loss}–{rec.push}
        </div>
        {rate !== null && (
          <div>
            <span
              className={clsx(
                "inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums leading-none",
                isAboveBreakEven
                  ? "border border-win-line/60 bg-win-soft text-win"
                  : "text-ink-muted",
              )}
            >
              {rate.toFixed(1)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/** A titled pair of spread/total records. Always renders both cells, even when empty. */
function RecordBlock({
  title,
  note,
  spread,
  total,
  showHeader = true,
}: {
  title: string;
  note: string;
  spread: Rec | null;
  total: Rec | null;
  showHeader?: boolean;
}) {
  return (
    <div className="min-w-0">
      {showHeader && (
        <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-2">
          <h3 className="text-xs font-semibold text-ink">{title}</h3>
          <span className="text-xs text-ink-muted">{note}</span>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <RecordCell label="Spread" rec={spread ?? ZERO} />
        <RecordCell label="Total" rec={total ?? ZERO} />
      </div>
    </div>
  );
}

const sumRecords = (a: Rec, b: Rec): Rec => ({ win: a.win + b.win, loss: a.loss + b.loss, push: a.push + b.push });
const tally = (rec: Rec) => `${rec.win}–${rec.loss}${rec.push ? `–${rec.push}` : ""}`;
const pct = (value: number | null) => (value === null ? "n/a" : `${(value * 100).toFixed(0)}%`);
const points = (value: number | null) => (value === null ? "n/a" : value.toFixed(1));

/**
 * The model's record: the season so far before this week, plus the week's own
 * record and accuracy once any of its games is graded. Links to /model.
 */
export function ModelRecord({
  performance,
  weekNumber,
  week,
  weekPerformance = [],
}: {
  /** Season-to-date before the week. */
  performance: Performance[];
  weekNumber: number;
  /** The week's own tally; omitted until a game in the week is graded. */
  week?: { spread: Rec; total: Rec };
  weekPerformance?: Performance[];
}) {
  const overall = performance.find((p) => p.classification === "all");
  const combined = overall ? sumRecords(overall.spread ?? ZERO, overall.total ?? ZERO) : null;
  const combinedRate = combined ? winRatePct(combined.win, combined.loss) : null;
  const weekOverall = weekPerformance.find((p) => p.classification === "all");

  return (
    <Card as="section" aria-label="Record" padding="none">
      {/* One content tree: collapsed behind the summary line on phones, open and inline from `sm:` up. */}
      <details className="responsive-disclosure group">
        <summary
          data-testid="record-summary"
          className="flex min-h-11 cursor-pointer items-center justify-between gap-2 rounded-xl px-2.5 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden"
        >
          <span className="min-w-0 truncate tabular-nums">
            {combined ? `Season ${tally(combined)}${combinedRate === null ? "" : ` · ${combinedRate.toFixed(1)}%`}` : "Season record"}
          </span>
          <span aria-hidden className="shrink-0 text-ink-muted transition-transform group-open:rotate-90">›</span>
        </summary>
        <div className="p-2.5 max-sm:pt-0">
          <div className="mb-1 flex items-center justify-between gap-x-3">
            <h2 className="text-sm font-semibold text-ink">Season record before Week {weekNumber}</h2>
            <Link
              href="/model"
              className="inline-flex min-h-11 shrink-0 items-center text-xs font-semibold text-accent-ink underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Season record
            </Link>
          </div>
          <RecordBlock
            title="Season"
            note={overall ? `${overall.games} games` : "no games yet"}
            spread={overall?.spread ?? null}
            total={overall?.total ?? null}
            showHeader={false}
          />
          {week && (
            <div className="mt-2">
              <h3 className="mb-1 flex flex-wrap items-baseline gap-x-2 text-sm font-semibold text-ink">
                Week {weekNumber} record
                <span className="text-xs font-normal text-ink-muted">this slate · small sample</span>
              </h3>
              <RecordBlock title={`Week ${weekNumber}`} note="" spread={week.spread} total={week.total} showHeader={false} />
              {weekOverall && weekOverall.evaluated > 0 && (
                <p data-testid="week-accuracy" className="mt-1.5 hidden text-xs text-ink-muted sm:block">
                  Average miss: spread {points(weekOverall.marginMae)} pts · total {points(weekOverall.totalMae)} pts
                  {" · "}95% interval coverage: spread {pct(weekOverall.marginCoverage95)} · total {pct(weekOverall.totalCoverage95)}
                </p>
              )}
            </div>
          )}
        </div>
      </details>
    </Card>
  );
}
