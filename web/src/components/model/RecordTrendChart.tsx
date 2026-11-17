"use client";

import { useState } from "react";
import { useIsPhone } from "@/lib/use-is-phone";
import { useMeasuredWidth } from "@/lib/use-measured-width";
import { ChartTable, type TableColumn } from "@/components/charts/ChartTable";
import { niceTicks } from "@/lib/charts";
import { BREAK_EVEN_PCT } from "@/lib/betting-format";
import type { TrendRecord, TrendWeek } from "@/lib/performance-trend";

const DESKTOP_W = 320;
const MAX_W = 460;
const H = 180;
const PAD = { left: 34, right: 48, top: 12, bottom: 24 };

const recordText = (record: TrendRecord) => `${record.win}–${record.loss}–${record.push}`;
const rateText = (record: TrendRecord) => (record.winRate === null ? "—" : `${record.winRate.toFixed(1)}%`);

const COLUMNS: readonly TableColumn<TrendWeek>[] = [
  { key: "week", label: "Week", value: (row) => row.week, format: (row) => `Week ${row.week}` },
  { key: "spreadRecord", label: "Spread to date", value: (row) => row.cumulative.spread.win - row.cumulative.spread.loss, format: (row) => recordText(row.cumulative.spread) },
  { key: "spreadRate", label: "Spread win rate", numeric: true, value: (row) => row.cumulative.spread.winRate, format: (row) => rateText(row.cumulative.spread) },
  { key: "totalRecord", label: "Totals to date", value: (row) => row.cumulative.total.win - row.cumulative.total.loss, format: (row) => recordText(row.cumulative.total) },
  { key: "totalRate", label: "Totals win rate", numeric: true, value: (row) => row.cumulative.total.winRate, format: (row) => rateText(row.cumulative.total) },
  { key: "spreadWeek", label: "Spread that week", numeric: true, value: (row) => row.weekly.spread.winRate, format: (row) => rateText(row.weekly.spread) },
  { key: "totalWeek", label: "Totals that week", numeric: true, value: (row) => row.weekly.total.winRate, format: (row) => rateText(row.weekly.total) },
];

const TARGETS = [
  { key: "spread", label: "Spread" },
  { key: "total", label: "Totals" },
] as const;

/** One target: a dot per week, a line for the season to date, the break-even rate dashed. */
function Panel({ rows, target, label, lo, hi }: { rows: readonly TrendWeek[]; target: "spread" | "total"; label: string; lo: number; hi: number }) {
  // Phones: the viewBox is the panel's CSS width (1:1 scale), so 12px text stays 12px.
  const phone = useIsPhone();
  const { ref, width: measured } = useMeasuredWidth(phone, 360);
  const W = phone ? Math.min(measured, MAX_W) : DESKTOP_W;
  const ticks = niceTicks(lo, hi, 4);
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const first = rows[0].week;
  const span = rows[rows.length - 1].week - first;
  const x = (week: number) => PAD.left + (span === 0 ? plotW / 2 : ((week - first) / span) * plotW);
  const y = (value: number) => PAD.top + ((hi - value) / (hi - lo)) * plotH;
  const last = rows[rows.length - 1];
  const lastRate = last.cumulative[target].winRate;
  const name = `${label} win rate through Week ${last.week}: ${rateText(last.cumulative[target])} season to date. Dots show each week's win rate and the line the season to date.`;
  const line = rows.flatMap((row) => {
    const rate = row.cumulative[target].winRate;
    return rate === null ? [] : [[x(row.week), y(rate)] as const];
  });
  const dots = rows.flatMap((row) => {
    const rate = row.weekly[target].winRate;
    return rate === null ? [] : [[x(row.week), y(rate)] as const];
  });
  // Label by week value, at most five ticks, so the axis stays legible at 320px.
  const lastWeek = last.week;
  const step = Math.max(1, Math.ceil((lastWeek - first) / 4));
  const weekTicks: number[] = [];
  for (let week = first; week <= lastWeek; week += step) weekTicks.push(week);
  return (
    <figure ref={ref} className="m-0 min-w-0">
      <figcaption className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-ink">{label}</span>
        <span className="font-mono text-xs text-ink-muted">{rateText(last.cumulative[target])} to date</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={name} className={`mx-auto block h-auto w-full max-w-[460px] ${phone ? "text-xs" : "text-[10px]"}`} data-testid={`record-trend-${target}`}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} stroke="var(--line)" strokeWidth={0.5} opacity={0.7} />
            <text x={PAD.left - 6} y={y(tick) + 3.5} textAnchor="end" className="fill-ink-muted font-mono">{tick}%</text>
          </g>
        ))}
        <line x1={PAD.left} x2={W - PAD.right} y1={y(BREAK_EVEN_PCT)} y2={y(BREAK_EVEN_PCT)} stroke="var(--ink-muted)" strokeWidth={1} strokeDasharray="4 3" data-break-even />
        <text x={PAD.left + 2} y={y(BREAK_EVEN_PCT) - 4} textAnchor="start" className="fill-ink-muted font-mono">{BREAK_EVEN_PCT}%</text>
        {line.length > 1 && <polyline points={line.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(" ")} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
        {dots.map(([px, py]) => <circle key={px} cx={px} cy={py} r={2.75} fill="var(--accent)" fillOpacity={0.35} stroke="var(--accent)" strokeWidth={1} />)}
        {lastRate !== null && (
          <g>
            <circle cx={x(last.week)} cy={y(lastRate)} r={3.5} fill="var(--accent)" stroke="var(--surface-card)" strokeWidth={1.5} />
            <text x={x(last.week) + 8} y={y(lastRate) + 3.5} className="fill-ink font-mono font-semibold">{lastRate.toFixed(1)}%</text>
          </g>
        )}
        {weekTicks.map((week) => (
          <text key={week} x={x(week)} y={H - 6} textAnchor={week === first && span > 0 ? "start" : week === lastWeek ? "end" : "middle"} className="fill-ink-muted font-mono">Wk {week}</text>
        ))}
      </svg>
    </figure>
  );
}

/** Season-to-date win rate by week for each target against the break-even rate, with a table view. */
export function RecordTrendChart({ rows }: { rows: readonly TrendWeek[] }) {
  const [asTable, setAsTable] = useState(false);
  const values = rows.flatMap((row) => TARGETS.flatMap(({ key }) => [row.weekly[key].winRate, row.cumulative[key].winRate])).filter((v): v is number => v !== null);
  values.push(BREAK_EVEN_PCT);
  const lo = Math.max(0, Math.floor((Math.min(...values) - 5) / 10) * 10);
  const hi = Math.min(100, Math.ceil((Math.max(...values) + 5) / 10) * 10);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted" aria-label="Chart key">
          <li className="flex items-center gap-1.5">
            <svg width="10" height="10" aria-hidden><circle cx="5" cy="5" r="4" fill="var(--accent)" fillOpacity="0.35" stroke="var(--accent)" /></svg>
            Each week
          </li>
          <li className="flex items-center gap-1.5">
            <svg width="18" height="10" aria-hidden><line x1="0" x2="18" y1="5" y2="5" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" /></svg>
            Season to date
          </li>
        </ul>
        <button
          type="button"
          aria-pressed={asTable}
          onClick={() => setAsTable((current) => !current)}
          className="min-h-11 rounded-lg border border-line bg-surface-card px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent aria-pressed:border-accent aria-pressed:text-accent-ink pointer-fine:min-h-9"
          data-testid="table-toggle"
        >
          {asTable ? "Show chart" : "Show as table"}
        </button>
      </div>
      {asTable
        ? <ChartTable rows={rows} columns={COLUMNS} rowKey={(row) => String(row.week)} caption="Season-to-date record and win rate by week" initialSort={{ key: "week" }} />
        : (
          <div className="grid gap-4 sm:grid-cols-2 sm:gap-6" data-testid="record-trend-chart">
            {TARGETS.map((target) => <Panel key={target.key} rows={rows} target={target.key} label={target.label} lo={lo} hi={hi} />)}
          </div>
        )}
    </div>
  );
}
