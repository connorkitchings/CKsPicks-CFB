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
const ROW_H = "h-11";
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
        "inline-flex h-5 min-w-5 items-center justify-center whitespace-nowrap rounded px-1 text-[10.5px] tabular-nums sm:text-[11px]",
        getRankBadgeClass(rank, cohort),
      )}
      title={rankTitle(rank, tied, cohort)}
    >
      {rankLabel(rank, tied)}
    </span>
  );
}

/** "Model Offense Rank" over "#122": always two lines, so side-by-side headers stay level. */
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
    <div data-testid={testId} className="mt-0.5 text-center text-[11px] leading-tight text-ink-muted">
      <div>{label}</div>
      <div className="font-mono">#{rank ?? "—"}</div>
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
    <div className="min-w-0 rounded-2xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-3 border-b border-line/60 pb-3">
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <TeamLogo name={offenseTeam} px={44} decorative={false} />
          <h3 className="break-words text-sm font-bold leading-tight tracking-tight text-ink">{offenseTeam}</h3>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-accent-ink">Offense</span>
          <RankLine label="Model Offense Rank" rank={offenseRank} testId="unit-offense-rank" />
        </div>
        <span className="mt-4 shrink-0 rounded-full border border-line/60 bg-surface-inset px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-faint">
          vs
        </span>
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <TeamLogo name={defenseTeam} px={44} decorative={false} />
          <h3 className="break-words text-sm font-bold leading-tight tracking-tight text-ink">{defenseTeam}</h3>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Defense</span>
          <RankLine label="Model Defense Rank" rank={defenseRank} testId="unit-defense-rank" />
        </div>
      </div>

      <table
        className="mt-2 w-full table-fixed text-xs"
        aria-label={`${offenseTeam} Offense vs ${defenseTeam} Defense`}
      >
        <colgroup>
          <col className="w-[23%]" />
          <col className="w-[14%]" />
          <col className="w-[26%]" />
          <col className="w-[14%]" />
          <col className="w-[23%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-line text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
            <th scope="col" className="py-2 pl-2 text-left font-medium">
              <span className="sr-only">Offense ({offenseTeam})</span>
            </th>
            <th scope="col" className="py-2 text-center font-medium">
              Rank
            </th>
            <th scope="col" className="py-2 text-center font-semibold text-ink-muted">
              Metric
            </th>
            <th scope="col" className="py-2 text-center font-medium">
              Rank
            </th>
            <th scope="col" className="py-2 pr-2 text-right font-medium">
              <span className="sr-only">Defense ({defenseTeam})</span>
            </th>
          </tr>
        </thead>
        {groupUnitRows(rows).map((group) => (
          <tbody key={group.section} className="divide-y divide-line/60">
            <tr className={SECTION_H}>
              <th
                scope="rowgroup"
                colSpan={5}
                className="pl-2 pt-3 text-left align-bottom text-[10px] font-semibold uppercase tracking-wider text-ink-faint"
              >
                {group.label}
              </th>
            </tr>
            {group.rows.map((row) => (
              <tr key={row.key} className={clsx(ROW_H, "transition-colors hover:bg-surface-inset/50")}>
                <td className="whitespace-nowrap pl-2 font-mono text-[13px] font-medium tabular-nums text-ink sm:text-sm">
                  {row.offenseValue}
                </td>
                <td className="text-center">
                  <RankBadge rank={row.offenseRank} cohort={row.offenseCohort} tied={row.offenseTied} />
                </td>
                <td className="break-words px-1 text-center text-[11px] font-semibold uppercase leading-tight tracking-wide text-ink">
                  <Label text={row.name} />
                </td>
                <td className="text-center">
                  <RankBadge rank={row.defenseRank} cohort={row.defenseCohort} tied={row.defenseTied} />
                </td>
                <td className="whitespace-nowrap pr-2 text-right font-mono text-[13px] font-medium tabular-nums text-ink sm:text-sm">
                  {row.defenseValue}
                </td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
