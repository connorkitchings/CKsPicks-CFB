import clsx from "clsx";
import { getRankBadgeClass } from "@/lib/matchup-math";
import type { UnitMatchupRow } from "@/lib/matchup";

export function UnitMatchupTable({
  title,
  subtitle,
  awayTeam,
  homeTeam,
  rows,
}: {
  title: string;
  subtitle: string;
  awayTeam: string;
  homeTeam: string;
  rows: UnitMatchupRow[];
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface-card p-4 shadow-sm sm:p-5">
      {/* Header */}
      <div className="mb-4 text-center">
        <h3 className="text-sm font-bold uppercase tracking-wider text-ink">
          {title}
        </h3>
        <p className="text-xs text-ink-faint">{subtitle}</p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs" aria-label={title}>
          <thead>
            <tr className="border-b border-line text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
              <th scope="col" className="py-2 pl-2 text-left font-medium">
                {awayTeam}
              </th>
              <th scope="col" className="py-2 text-center font-medium w-12">
                Rank
              </th>
              <th scope="col" className="py-2 text-center font-semibold text-ink-muted">
                Metric
              </th>
              <th scope="col" className="py-2 text-center font-medium w-12">
                Rank
              </th>
              <th scope="col" className="py-2 pr-2 text-right font-medium">
                {homeTeam}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/60">
            {rows.map((row) => (
              <tr key={row.name} className="hover:bg-surface-inset/50 transition-colors">
                {/* Away Value */}
                <td className="py-2.5 pl-2 font-mono text-sm font-medium tabular-nums text-ink text-left">
                  {row.awayValue}
                </td>

                {/* Away Rank Badge */}
                <td className="py-2.5 text-center">
                  <span
                    className={clsx(
                      "inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-[11px] tabular-nums",
                      getRankBadgeClass(row.awayRank),
                    )}
                    title={`National Rank: #${row.awayRank}`}
                  >
                    #{row.awayRank}
                  </span>
                </td>

                {/* Metric Name */}
                <td className="py-2.5 text-center font-semibold tracking-wide text-ink uppercase text-[11px] sm:text-xs">
                  {row.name}
                </td>

                {/* Home Rank Badge */}
                <td className="py-2.5 text-center">
                  <span
                    className={clsx(
                      "inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-[11px] tabular-nums",
                      getRankBadgeClass(row.homeRank),
                    )}
                    title={`National Rank: #${row.homeRank}`}
                  >
                    #{row.homeRank}
                  </span>
                </td>

                {/* Home Value */}
                <td className="py-2.5 pr-2 font-mono text-sm font-medium tabular-nums text-ink text-right">
                  {row.homeValue}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
