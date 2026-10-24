import type { ReactNode } from "react";
import { RankChip } from "@/components/ui/RankChip";
import { TeamSection } from "@/components/teams/TeamSection";
import { rankLabel, rankTitle, type StatRole, type UnitMatchupRow } from "@/lib/team-stats";

/** The headline rows of each unit; every other metric sits behind "Full stats". */
const CORE_KEYS = ["ppp", "epa_per_possession", "success_rate", "explosive_rate", "conv_rate_3rd_4th"];
/** The metric a collapsed phone section summarizes with. */
const HEADLINE_KEY = "epa_per_possession";
const HEADLINE_LABEL = "PPA/poss";

const UNITS: { role: StatRole; label: string; swatch: string }[] = [
  { role: "offense", label: "Offense", swatch: "bg-accent" },
  { role: "defense", label: "Defense", swatch: "bg-warn" },
];

/** A row's value and rank for one side of the ball. */
const sideOf = (row: UnitMatchupRow, role: StatRole) => (role === "offense"
  ? { value: row.offenseValue, rank: row.offenseRank, cohort: row.offenseCohort, tied: row.offenseTied }
  : { value: row.defenseValue, rank: row.defenseRank, cohort: row.defenseCohort, tied: row.defenseTied });

function Chip({ row, role }: { row: UnitMatchupRow; role: StatRole }) {
  const { rank, cohort, tied } = sideOf(row, role);
  return <RankChip rank={rank} total={cohort ?? undefined} label={rankLabel(rank, tied)} title={rankTitle(rank, tied, cohort)} className="min-w-11" />;
}

function Rows({ rows, role }: { rows: readonly UnitMatchupRow[]; role: StatRole }) {
  return (
    <dl className="grid grid-cols-[1fr_auto_auto] text-sm">
      {rows.map((row) => (
        <div key={row.key} className="col-span-3 grid grid-cols-subgrid items-center border-t border-line py-1.5 first:border-t-0">
          <dt className="text-ink-muted">{row.name}</dt>
          <dd className="pl-3 text-right font-mono tabular-nums text-ink">{sideOf(row, role).value}</dd>
          <dd className="pl-3"><Chip row={row} role={role} /></dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * One unit's section: a native `<details>` that starts collapsed on phones, where the summary also
 * carries one headline stat, and is always open (heading only) from `sm:` up.
 */
function UnitSection({ label, swatch, role, rows, headline, testId }: {
  label: string;
  swatch: string;
  role: StatRole;
  rows: readonly UnitMatchupRow[];
  headline?: UnitMatchupRow;
  testId: string;
}): ReactNode {
  const summary = headline && sideOf(headline, role);
  return (
    <details data-testid={testId} className="unit-section group">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:min-h-0 sm:cursor-default sm:pb-1 [&::-webkit-details-marker]:hidden">
        <span className="flex items-center gap-1.5"><i className={`inline-block h-2 w-2 rounded-sm ${swatch}`} />{label}</span>
        <span className="flex items-center gap-2 sm:hidden">
          {headline && summary && <span className="flex items-center gap-1.5 text-xs font-normal text-ink-muted">{HEADLINE_LABEL} <span className="font-mono tabular-nums text-ink">{summary.value}</span><Chip row={headline} role={role} /></span>}
          <span aria-hidden className="text-ink-faint transition-transform group-open:rotate-180">▾</span>
        </span>
      </summary>
      <Rows rows={rows} role={role} />
    </details>
  );
}

/**
 * Offense and defense core metrics with national ranks, plus a "Full stats" disclosure for the rest.
 * `rows` are the team's own offense and defense sides from `buildUnitRows(rows, team, team)`.
 */
export function UnitProfile({ rows }: { rows: readonly UnitMatchupRow[] }) {
  const core = rows.filter((row) => CORE_KEYS.includes(row.key));
  const more = rows.filter((row) => !CORE_KEYS.includes(row.key));
  const headline = rows.find((row) => row.key === HEADLINE_KEY);
  return (
    <TeamSection id="team-unit-profile" title="Unit profile">
      <div className="space-y-3">
        {UNITS.map((unit) => <UnitSection key={unit.role} {...unit} rows={core} headline={headline} testId={`unit-${unit.role}`} />)}
      </div>
      {more.length > 0 && (
        <details className="mt-3 border-t border-line pt-1" data-testid="unit-full-stats">
          <summary className="flex min-h-11 cursor-pointer items-center text-[13px] font-semibold text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:min-h-9">Full stats ({rows.length})</summary>
          <div className="space-y-3 pt-1">
            {UNITS.map((unit) => (
              <div key={unit.role}>
                <p className="flex items-center gap-1.5 pb-1 text-sm font-semibold text-ink"><i className={`inline-block h-2 w-2 rounded-sm ${unit.swatch}`} />{unit.label}</p>
                <Rows rows={more} role={unit.role} />
              </div>
            ))}
          </div>
        </details>
      )}
    </TeamSection>
  );
}
