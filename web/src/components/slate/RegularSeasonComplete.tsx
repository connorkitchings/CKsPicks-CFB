import { Notice } from "@/components/ui/Notice";
import { seasonRecordThrough, winRatePct, type Tally } from "@/lib/slate";
import type { Game } from "@/lib/queries";
import type { Performance } from "@/lib/v5";

const tally = (t: Tally) => `${t.win}–${t.loss}${t.push ? `–${t.push}` : ""}`;

function rateText(t: Tally): string {
  const rate = winRatePct(t.win, t.loss);
  return rate === null ? "" : ` (${rate.toFixed(1)}%)`;
}

/**
 * Shown once the final regular-season close is live: the official record ends with the final regular week,
 * so the page says so and states the final cumulative record. Postseason games are not predicted or graded.
 */
export function RegularSeasonComplete({ performance, games }: { performance: Performance[]; games: Game[] }) {
  const record = seasonRecordThrough(performance, games);
  return (
    <Notice tone="info" title="Regular season complete">
      <p data-testid="regular-season-record">
        Final record: spread {tally(record.spread)}
        {rateText(record.spread)} · total {tally(record.total)}
        {rateText(record.total)}
      </p>
      <p className="mt-1 text-ink-muted" data-testid="regular-season-scope">
        The record covers the regular season only. Postseason games are not predicted, graded or part of it.
      </p>
    </Notice>
  );
}
