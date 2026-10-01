import clsx from "clsx";
import { getRankBadgeClass } from "@/lib/matchup-math";
import type { TeamProfileStats } from "@/lib/matchup";

function MetricRow({
  label,
  value,
  rank,
  subMetrics,
}: {
  label: string;
  value: string;
  rank: number;
  subMetrics?: { label: string; value: string; rank: number }[];
}) {
  return (
    <div className="border-b border-line/60 pb-2.5 pt-2 last:border-0 last:pb-0">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-ink">
          {label}
        </span>
        <div className="flex items-center gap-1.5 font-mono text-xs tabular-nums">
          <span className="font-semibold text-ink">{value}</span>
          <span
            className={clsx(
              "inline-flex h-4 min-w-4 items-center justify-center rounded px-1 text-[10px]",
              getRankBadgeClass(rank),
            )}
            title={`National Rank: #${rank}`}
          >
            #{rank}
          </span>
        </div>
      </div>

      {subMetrics && subMetrics.length > 0 && (
        <div className="mt-1.5 space-y-1 pl-2 text-[11px] text-ink-muted">
          {subMetrics.map((sub) => (
            <div key={sub.label} className="flex items-center justify-between">
              <span>{sub.label}</span>
              <div className="flex items-center gap-1 font-mono tabular-nums">
                <span>{sub.value}</span>
                <span
                  className={clsx(
                    "inline-flex h-3.5 min-w-3.5 items-center justify-center rounded px-0.5 text-[9px]",
                    getRankBadgeClass(sub.rank),
                  )}
                >
                  #{sub.rank}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function TeamProfilePillars({
  awayProfile,
  homeProfile,
}: {
  awayProfile: TeamProfileStats;
  homeProfile: TeamProfileStats;
}) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Away Team Profile */}
      <div className="rounded-2xl border border-line bg-surface-card p-4 shadow-sm sm:p-5">
        <div className="mb-3 flex items-center justify-between border-b border-line pb-2">
          <h3 className="text-sm font-bold text-ink">
            {awayProfile.rank && awayProfile.rank <= 25 && (
              <span className="text-accent-ink mr-1">#{awayProfile.rank}</span>
            )}
            {awayProfile.team} Statistical Profile
          </h3>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
            Away
          </span>
        </div>

        <div className="space-y-1">
          <MetricRow
            label="EPA Margin"
            value={awayProfile.epaMargin.formatted}
            rank={awayProfile.epaMargin.rank}
            subMetrics={[
              {
                label: "Offense EPA/Play",
                value: awayProfile.offEpa.formatted,
                rank: awayProfile.offEpa.rank,
              },
              {
                label: "Defense EPA/Play",
                value: awayProfile.defEpa.formatted,
                rank: awayProfile.defEpa.rank,
              },
            ]}
          />

          <MetricRow
            label="Offense Success Rate"
            value={awayProfile.offSuccessRate.formatted}
            rank={awayProfile.offSuccessRate.rank}
            subMetrics={[
              {
                label: "Dropback Success",
                value: awayProfile.offDropbackSr.formatted,
                rank: awayProfile.offDropbackSr.rank,
              },
              {
                label: "Rush Success",
                value: awayProfile.offRushSr.formatted,
                rank: awayProfile.offRushSr.rank,
              },
            ]}
          />

          <MetricRow
            label="Defense Success Rate"
            value={awayProfile.defSuccessRate.formatted}
            rank={awayProfile.defSuccessRate.rank}
            subMetrics={[
              {
                label: "Dropback Allowed",
                value: awayProfile.defDropbackSr.formatted,
                rank: awayProfile.defDropbackSr.rank,
              },
              {
                label: "Rush Allowed",
                value: awayProfile.defRushSr.formatted,
                rank: awayProfile.defRushSr.rank,
              },
            ]}
          />

          <MetricRow
            label="Net Points / Drive"
            value={awayProfile.netPtsPerDrive.formatted}
            rank={awayProfile.netPtsPerDrive.rank}
            subMetrics={[
              {
                label: "Offense Pts/Drive",
                value: awayProfile.offPtsPerDrive.formatted,
                rank: awayProfile.offPtsPerDrive.rank,
              },
              {
                label: "Defense Pts/Drive",
                value: awayProfile.defPtsPerDrive.formatted,
                rank: awayProfile.defPtsPerDrive.rank,
              },
            ]}
          />

          <MetricRow
            label="Net Field Position"
            value={awayProfile.netFieldPosition.formatted}
            rank={awayProfile.netFieldPosition.rank}
          />

          <MetricRow
            label="Eckel Ratio"
            value={awayProfile.eckelRatio.formatted}
            rank={awayProfile.eckelRatio.rank}
          />
        </div>
      </div>

      {/* Home Team Profile */}
      <div className="rounded-2xl border border-line bg-surface-card p-4 shadow-sm sm:p-5">
        <div className="mb-3 flex items-center justify-between border-b border-line pb-2">
          <h3 className="text-sm font-bold text-ink">
            {homeProfile.rank && homeProfile.rank <= 25 && (
              <span className="text-accent-ink mr-1">#{homeProfile.rank}</span>
            )}
            {homeProfile.team} Statistical Profile
          </h3>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
            Home
          </span>
        </div>

        <div className="space-y-1">
          <MetricRow
            label="EPA Margin"
            value={homeProfile.epaMargin.formatted}
            rank={homeProfile.epaMargin.rank}
            subMetrics={[
              {
                label: "Offense EPA/Play",
                value: homeProfile.offEpa.formatted,
                rank: homeProfile.offEpa.rank,
              },
              {
                label: "Defense EPA/Play",
                value: homeProfile.defEpa.formatted,
                rank: homeProfile.defEpa.rank,
              },
            ]}
          />

          <MetricRow
            label="Offense Success Rate"
            value={homeProfile.offSuccessRate.formatted}
            rank={homeProfile.offSuccessRate.rank}
            subMetrics={[
              {
                label: "Dropback Success",
                value: homeProfile.offDropbackSr.formatted,
                rank: homeProfile.offDropbackSr.rank,
              },
              {
                label: "Rush Success",
                value: homeProfile.offRushSr.formatted,
                rank: homeProfile.offRushSr.rank,
              },
            ]}
          />

          <MetricRow
            label="Defense Success Rate"
            value={homeProfile.defSuccessRate.formatted}
            rank={homeProfile.defSuccessRate.rank}
            subMetrics={[
              {
                label: "Dropback Allowed",
                value: homeProfile.defDropbackSr.formatted,
                rank: homeProfile.defDropbackSr.rank,
              },
              {
                label: "Rush Allowed",
                value: homeProfile.defRushSr.formatted,
                rank: homeProfile.defRushSr.rank,
              },
            ]}
          />

          <MetricRow
            label="Net Points / Drive"
            value={homeProfile.netPtsPerDrive.formatted}
            rank={homeProfile.netPtsPerDrive.rank}
            subMetrics={[
              {
                label: "Offense Pts/Drive",
                value: homeProfile.offPtsPerDrive.formatted,
                rank: homeProfile.offPtsPerDrive.rank,
              },
              {
                label: "Defense Pts/Drive",
                value: homeProfile.defPtsPerDrive.formatted,
                rank: homeProfile.defPtsPerDrive.rank,
              },
            ]}
          />

          <MetricRow
            label="Net Field Position"
            value={homeProfile.netFieldPosition.formatted}
            rank={homeProfile.netFieldPosition.rank}
          />

          <MetricRow
            label="Eckel Ratio"
            value={homeProfile.eckelRatio.formatted}
            rank={homeProfile.eckelRatio.rank}
          />
        </div>
      </div>
    </div>
  );
}
