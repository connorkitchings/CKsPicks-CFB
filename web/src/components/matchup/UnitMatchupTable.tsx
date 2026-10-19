import clsx from "clsx";
import { Fragment } from "react";
import TeamLogo from "@/components/TeamLogo";
import {
  getRankBadgeClass,
  groupUnitRows,
  rankLabel,
  rankTitle,
  type UnitMatchupRow,
} from "@/lib/team-stats";

/** Fixed heights keep the two side-by-side tables' rows aligned. */
const ROW_H = "h-14 sm:h-11";
const SECTION_H = "h-8";

/** Label with a break opportunity after each slash, so "Points/possession" wraps instead of clipping. */
function Label({ text }: { text: string }) {
  return (
    <>
      {text.split("/").map((part, i) => (
        <Fragment key={i}>
          {i > 0 && (
            <>
              /<wbr />
            </>
          )}
          {part}
        </Fragment>
      ))}
    </>
  );
}

function RankBadge({
  rank,
  cohort,
  tied,
}: {
  rank: number | null;
  cohort: number | null;
  tied: boolean;
}) {
  return (
    <span
      className={clsx(
        "inline-flex h-5 min-w-5 items-center justify-center whitespace-nowrap rounded px-1 text-xs tabular-nums",
        getRankBadgeClass(rank, cohort),
        rank === null && "!text-ink-muted",
      )}
      title={rankTitle(rank, tied, cohort)}
    >
      {rankLabel(rank, tied)}
    </span>
  );
}

/** Model ranks wrap in narrow team headers without clipping. */
function RankLine({
  label,
  rank,
  testId,
}: {
  label: string;
  rank: number | null | undefined;
  testId: string;
}) {
  if (rank === undefined) return null;
  return (
    <div
      data-testid={testId}
      className="mt-0.5 text-center text-xs leading-snug text-ink-muted"
    >
      {label} <span className="font-mono">#{rank ?? "—"}</span>
    </div>
  );
}

/**
 * One team's offense against the other team's defense, with national ranks in
 * tier colors. (Per-row edge calculation lives in team-stats.ts but is not
 * drawn for now.)
 */
export function UnitMatchupTable({
  offenseTeam,
  defenseTeam,
  rows,
  offenseRank,
  defenseRank,
}: {
  offenseTeam: string;
  defenseTeam: string;
  rows: UnitMatchupRow[];
  /** The offense team's model offense rank (null when unranked; omit to hide the line). */
  offenseRank?: number | null;
  /** The defense team's model defense rank. */
  defenseRank?: number | null;
}) {
  return (
    <div className="min-w-0 rounded-2xl border border-line bg-surface-card p-3 shadow-sm sm:p-4">
      <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-3 border-b border-line/60 pb-3">
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <div className="hidden lg:block"><TeamLogo name={offenseTeam} px={44} decorative={false} /></div>
          <h3 className="break-words text-sm font-bold leading-tight tracking-tight text-ink">{offenseTeam}</h3>
          <span className="text-xs font-semibold uppercase tracking-wider text-accent-ink">Offense</span>
          <RankLine label="Model Offense Rank" rank={offenseRank} testId="unit-offense-rank" />
        </div>
        <span className="mt-4 shrink-0 rounded-full border border-line/60 bg-surface-inset px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-ink-muted">
          vs
        </span>
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <div className="hidden lg:block"><TeamLogo name={defenseTeam} px={44} decorative={false} /></div>
          <h3 className="break-words text-sm font-bold leading-tight tracking-tight text-ink">{defenseTeam}</h3>
          <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Defense</span>
          <RankLine label="Model Defense Rank" rank={defenseRank} testId="unit-defense-rank" />
        </div>
      </div>

      <table
        className="mt-2 w-full table-fixed text-xs"
        aria-label={`${offenseTeam} Offense vs ${defenseTeam} Defense`}
      >
        <colgroup>
          <col className="w-[33%] sm:w-[37%]" />
          <col className="w-[34%] sm:w-[26%]" />
          <col className="w-[33%] sm:w-[37%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-line text-xs font-semibold text-ink-muted">
            <th scope="col" className="py-2 text-left font-medium sm:pl-2">
              <span className="flex items-center justify-between gap-1">
                <span>Offense<span className="sr-only"> ({offenseTeam}), value and rank</span></span>
                <span aria-hidden className="hidden sm:inline">Rank</span>
              </span>
            </th>
            <th scope="col" className="py-2 text-center font-semibold">Metric</th>
            <th scope="col" className="py-2 text-right font-medium sm:pr-2">
              <span className="flex items-center justify-between gap-1">
                <span aria-hidden className="hidden sm:inline">Rank</span>
                <span>Defense<span className="sr-only"> ({defenseTeam}), value and rank</span></span>
              </span>
            </th>
          </tr>
        </thead>
        {groupUnitRows(rows).map((group) => (
          <tbody key={group.section} className="divide-y divide-line/60">
            <tr className={SECTION_H}>
              <th
                scope="rowgroup"
                colSpan={3}
                className="pt-3 text-center align-bottom text-xs font-semibold uppercase tracking-wider text-ink-muted"
              >
                {group.label}
              </th>
            </tr>
            {group.rows.map((row) => (
              <tr key={row.key} className={clsx(ROW_H, "transition-colors hover:bg-surface-inset/50")}>
                <td className="sm:pl-2">
                  <div className="flex flex-col items-start justify-between gap-1 sm:flex-row sm:items-center">
                    <span data-value="offense" className="font-mono text-sm font-medium tabular-nums text-ink">{row.offenseValue}</span>
                    <RankBadge rank={row.offenseRank} cohort={row.offenseCohort} tied={row.offenseTied} />
                  </div>
                </td>
                <td className="break-words px-1 text-center text-sm font-medium leading-tight text-ink">
                  <Label text={row.name} />
                </td>
                <td className="sm:pr-2">
                  <div className="flex flex-col items-end justify-between gap-1 sm:flex-row-reverse sm:items-center">
                    <span data-value="defense" className="font-mono text-sm font-medium tabular-nums text-ink">{row.defenseValue}</span>
                    <RankBadge rank={row.defenseRank} cohort={row.defenseCohort} tied={row.defenseTied} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
