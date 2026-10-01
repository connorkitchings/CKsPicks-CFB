import clsx from "clsx";
import TeamLogo from "@/components/TeamLogo";
import { getRankBadgeClass } from "@/lib/matchup-math";
import type { UnitMatchupRow } from "@/lib/matchup";

export function UnitMatchupTable({
  offenseTeam,
  defenseTeam,
  subtitle,
  rows,
}: {
  offenseTeam: string;
  defenseTeam: string;
  subtitle?: string;
  rows: UnitMatchupRow[];
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface-card p-4 shadow-sm sm:p-5">
      {/* Header with Logos above Team & Unit */}
      <div className="mb-4 flex items-center justify-between border-b border-line/60 pb-3">
        {/* Left: Offense */}
        <div className="flex flex-col items-start min-w-0">
          <TeamLogo name={offenseTeam} px={36} decorative={false} className="mb-1.5" />
          <h3 className="truncate text-sm font-bold tracking-tight text-ink">
            {offenseTeam}
          </h3>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-accent-ink">
            Offense
          </span>
        </div>

        {/* Center: VS & Subtitle */}
        <div className="text-center px-2">
          <span className="rounded-full bg-surface-inset px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-ink-faint border border-line/60">
            VS
          </span>
          {subtitle && (
            <p className="mt-1.5 hidden text-[10px] text-ink-faint sm:block max-w-[150px] leading-tight">
              {subtitle}
            </p>
          )}
        </div>

        {/* Right: Defense */}
        <div className="flex flex-col items-end min-w-0 text-right">
          <TeamLogo name={defenseTeam} px={36} decorative={false} className="mb-1.5" />
          <h3 className="truncate text-sm font-bold tracking-tight text-ink">
            {defenseTeam}
          </h3>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
            Defense
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs" aria-label={`${offenseTeam} Offense vs ${defenseTeam} Defense`}>
          <thead>
            <tr className="border-b border-line text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
              <th scope="col" className="py-2 pl-2 text-left font-medium">
                {offenseTeam}
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
                {defenseTeam}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/60">
            {rows.map((row) => (
              <tr key={row.name} className="hover:bg-surface-inset/50 transition-colors">
                {/* Offense Value */}
                <td className="py-2.5 pl-2 font-mono text-sm font-medium tabular-nums text-ink text-left">
                  {row.offenseValue}
                </td>

                {/* Offense Rank Badge */}
                <td className="py-2.5 text-center">
                  <span
                    className={clsx(
                      "inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-[11px] tabular-nums",
                      getRankBadgeClass(row.offenseRank),
                    )}
                    title={`National Rank: #${row.offenseRank}`}
                  >
                    #{row.offenseRank}
                  </span>
                </td>

                {/* Metric Name */}
                <td className="py-2.5 text-center font-semibold tracking-wide text-ink uppercase text-[11px] sm:text-xs">
                  {row.name}
                </td>

                {/* Defense Rank Badge */}
                <td className="py-2.5 text-center">
                  <span
                    className={clsx(
                      "inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-[11px] tabular-nums",
                      getRankBadgeClass(row.defenseRank),
                    )}
                    title={`National Rank: #${row.defenseRank}`}
                  >
                    #{row.defenseRank}
                  </span>
                </td>

                {/* Defense Value */}
                <td className="py-2.5 pr-2 font-mono text-sm font-medium tabular-nums text-ink text-right">
                  {row.defenseValue}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
