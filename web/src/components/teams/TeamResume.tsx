import { RankChip } from "@/components/ui/RankChip";
import { TeamSection } from "@/components/teams/TeamSection";
import type { TeamSummary } from "@/lib/team-summary";

const value = (n: number | null | undefined, digits = 1) => (typeof n === "number" ? n.toFixed(digits) : "—");
const signed = (n: number | null | undefined) => (typeof n === "number" ? `${n > 0 ? "+" : ""}${n.toFixed(1)}` : "—");

/** Strength of record, the three schedule-strength views and wins above average, each with its national rank. */
export function TeamResume({ summary }: { summary: TeamSummary }) {
  const { rating, sos } = summary;
  const played = rating.completedGames;
  const remaining = typeof played === "number" && typeof rating.scheduledGames === "number" ? rating.scheduledGames - played : null;
  const rows: { label: string; value: string; rank: number | null }[] = [
    { label: "Strength of record", value: value(rating.sor), rank: rating.sorRank ?? null },
    { label: `SOS played${typeof played === "number" ? ` (${played})` : ""}`, value: value(rating.sosPlayedAverage), rank: sos.played },
    { label: `SOS remaining${remaining === null ? "" : ` (${remaining})`}`, value: value(rating.sosRemainingAverage), rank: sos.remaining },
    { label: "SOS full season", value: value(rating.sosFullAverage), rank: sos.full },
    { label: "Wins above average", value: signed(rating.waa), rank: summary.waaRank },
  ];
  return (
    <TeamSection id="team-resume" title="Résumé">
      <dl className="grid grid-cols-[1fr_auto_auto] text-sm">
        {rows.map((row) => (
          <div key={row.label} className="col-span-3 grid grid-cols-subgrid items-center border-t border-line py-2 first:border-t-0 first:pt-0 last:pb-0">
            <dt className="text-ink-muted">{row.label}</dt>
            <dd className="pl-3 text-right font-mono tabular-nums text-ink">{row.value}</dd>
            <dd className="pl-3"><RankChip rank={row.rank} className="min-w-11" title={`${row.label} national rank`} /></dd>
          </div>
        ))}
      </dl>
    </TeamSection>
  );
}
