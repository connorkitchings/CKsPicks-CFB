import clsx from "clsx";
import { Fragment } from "react";
import TeamLogo from "@/components/TeamLogo";
import {
  edgeSummary,
  getRankBadgeClass,
  groupUnitRows,
  rankLabel,
  rankTitle,
  type RowEdge,
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
        "inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-[11px] tabular-nums",
        getRankBadgeClass(rank, cohort),
      )}
      title={rankTitle(rank, tied, cohort)}
    >
      {rankLabel(rank, tied)}
    </span>
  );
}

/** One accent bar on the side with the edge; position says who, darkness says how much. */
function edgeBar(
  edge: RowEdge | null,
  side: "offense" | "defense",
  edgeSide: "border-l-[3px]" | "border-r-[3px]",
): string {
  const has = edge !== null && edge.side === side && edge.strength !== null;
  return clsx(
    edgeSide,
    !has && "border-transparent",
    has && edge.strength === "strong" && "border-accent",
    has && edge.strength === "slight" && "border-accent/45",
  );
}

function edgeText(edge: RowEdge | null, offenseTeam: string, defenseTeam: string): string | null {
  if (edge === null) return null;
  if (edge.side === "even") return "Even matchup";
  const team = edge.side === "offense" ? `${offenseTeam} offense` : `${defenseTeam} defense`;
  return `Edge: ${team}${edge.strength === "strong" ? " (large)" : ""}`;
}

/**
 * One team's offense against the other team's defense. National ranks use the
 * tier colors; the accent bar on a row's outer edge marks which side holds the
 * advantage (offense rank against the opposing defense's rank).
 */
export function UnitMatchupTable({
  offenseTeam,
  defenseTeam,
  rows,
}: {
  offenseTeam: string;
  defenseTeam: string;
  rows: UnitMatchupRow[];
}) {
  const summary = edgeSummary(rows);
  const compared = summary.offense + summary.defense + summary.even;
  return (
    <div className="min-w-0 rounded-2xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="flex min-h-[3.25rem] items-center justify-between gap-3 border-b border-line/60 pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <TeamLogo name={offenseTeam} px={36} decorative={false} />
          <div className="min-w-0">
            <h3 className="break-words text-sm font-bold leading-tight tracking-tight text-ink">{offenseTeam}</h3>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-accent-ink">Offense</span>
          </div>
        </div>
        <span className="shrink-0 rounded-full border border-line/60 bg-surface-inset px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-faint">
          vs
        </span>
        <div className="flex min-w-0 flex-row-reverse items-center gap-2 text-right">
          <TeamLogo name={defenseTeam} px={36} decorative={false} />
          <div className="min-w-0">
            <h3 className="break-words text-sm font-bold leading-tight tracking-tight text-ink">{defenseTeam}</h3>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Defense</span>
          </div>
        </div>
      </div>

      <p
        data-testid="edge-summary"
        className="min-h-[2.25rem] pt-2 text-[11px] leading-snug text-ink-muted"
      >
        {compared === 0 ? (
          "Not enough games to compare yet."
        ) : (
          <>
            Edge:{" "}
            <span className="font-semibold text-ink">
              {offenseTeam} offense {summary.offense}
            </span>
            {" · "}
            <span className="font-semibold text-ink">
              {defenseTeam} defense {summary.defense}
            </span>
            {" · even "}
            {summary.even}
          </>
        )}
      </p>

      <table
        className="mt-1 w-full table-fixed text-xs"
        aria-label={`${offenseTeam} Offense vs ${defenseTeam} Defense`}
      >
        <colgroup>
          <col className="w-[24%]" />
          <col className="w-[12%]" />
          <col className="w-[28%]" />
          <col className="w-[12%]" />
          <col className="w-[24%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-line text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
            <th scope="col" className="py-2 pl-2 text-left font-medium">
              Offense<span className="sr-only"> ({offenseTeam})</span>
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
              Defense<span className="sr-only"> ({defenseTeam})</span>
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
            {group.rows.map((row) => {
              const note = edgeText(row.edge, offenseTeam, defenseTeam);
              return (
                <tr
                  key={row.key}
                  className={clsx(ROW_H, "transition-colors hover:bg-surface-inset/50")}
                  data-edge={row.edge?.side ?? "none"}
                  data-strength={row.edge?.strength ?? "none"}
                >
                  <td
                    className={clsx(
                      "whitespace-nowrap pl-2 font-mono text-[13px] font-medium tabular-nums text-ink sm:text-sm",
                      edgeBar(row.edge, "offense", "border-l-[3px]"),
                    )}
                  >
                    {row.offenseValue}
                  </td>
                  <td className="text-center">
                    <RankBadge rank={row.offenseRank} cohort={row.offenseCohort} tied={row.offenseTied} />
                  </td>
                  <td className="break-words px-1 text-center text-[11px] font-semibold uppercase leading-tight tracking-wide text-ink">
                    <Label text={row.name} />
                    {note && <span className="sr-only">. {note}</span>}
                  </td>
                  <td className="text-center">
                    <RankBadge rank={row.defenseRank} cohort={row.defenseCohort} tied={row.defenseTied} />
                  </td>
                  <td
                    className={clsx(
                      "whitespace-nowrap pr-2 text-right font-mono text-[13px] font-medium tabular-nums text-ink sm:text-sm",
                      edgeBar(row.edge, "defense", "border-r-[3px]"),
                    )}
                  >
                    {row.defenseValue}
                  </td>
                </tr>
              );
            })}
          </tbody>
        ))}
      </table>
    </div>
  );
}
