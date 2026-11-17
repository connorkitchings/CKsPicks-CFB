"use client";

import { useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import clsx from "clsx";
import { useSearchParams } from "next/navigation";
import {
  closerSide,
  lineAbsError,
  modelAbsError,
  parseTarget,
  scatterDomain,
  sortPairedErrors,
  type CloserSide,
  type PairedError,
  type PairedSortKey,
  type SortDirection,
} from "@/lib/performance-errors";
import type { MarketTarget } from "@/lib/performance-market";
import { niceTicks } from "@/lib/charts";
import { nearestScatterTeams } from "@/lib/scatter-selection";
import { replaceSearchParams } from "@/lib/url-state";
import { Card } from "@/components/ui/Card";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { MatchupButton } from "@/components/MatchupLinks";

const TARGET_OPTIONS = [
  { value: "spread", label: "Spread", testId: "error-target-spread" },
  { value: "total", label: "Totals", testId: "error-target-total" },
] as const;

const CLOSER_LABEL: Record<CloserSide, string> = { model: "Model", market: "Betting line", even: "Even" };

const pts = (value: number) => `${value.toFixed(1)} pts`;
const signed = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(1)}`;

/** Spread values are home margins; totals are combined points. */
function valueText(target: MarketTarget, pair: PairedError, value: number): string {
  if (target === "total") return pts(value);
  if (value === 0) return "Pick’em";
  return `${value > 0 ? pair.homeTeam : pair.awayTeam} by ${Math.abs(value).toFixed(1)}`;
}

/** Signed error in words: positive leans toward the home team (spread) or high (total). */
function errorText(target: MarketTarget, pair: PairedError, error: number): string {
  if (error === 0) return "0.0 pts (exact)";
  const size = pts(Math.abs(error));
  if (target === "total") return `${size} ${error > 0 ? "high" : "low"}`;
  return `${size} toward ${error > 0 ? pair.homeTeam : pair.awayTeam}`;
}

const gameName = (pair: PairedError) => `${pair.awayTeam} at ${pair.homeTeam}`;

const W = 320;
const PAD = { left: 38, right: 12, top: 12, bottom: 36 };
const PLOT = { w: W - PAD.left - PAD.right, h: W - PAD.top - PAD.bottom };

function Scatter({
  target,
  pairs,
  selectedId,
  onSelect,
}: {
  target: MarketTarget;
  pairs: PairedError[];
  selectedId: number | null;
  onSelect: (gameId: number | null) => void;
}) {
  const domain = scatterDomain(pairs);
  const x = (value: number) => PAD.left + (value / domain) * PLOT.w;
  const y = (value: number) => PAD.top + PLOT.h - (value / domain) * PLOT.h;
  const ordered = useMemo(() => [...pairs].sort((a, b) => lineAbsError(a) - lineAbsError(b) || a.gameId - b.gameId), [pairs]);
  const [focusId, setFocusId] = useState<number | null>(null);
  const nodes = useRef(new Map<number, SVGGElement>());
  const svgRef = useRef<SVGSVGElement>(null);
  const selectedPair = ordered.find((p) => p.gameId === selectedId);
  const tabbable = ordered.find((p) => p.gameId === (focusId ?? selectedId))?.gameId ?? ordered[0]?.gameId;

  function move(index: number) {
    const next = ordered[Math.min(ordered.length - 1, Math.max(0, index))];
    setFocusId(next.gameId);
    nodes.current.get(next.gameId)?.focus();
  }

  function onKeyDown(event: KeyboardEvent<SVGGElement>, index: number, pair: PairedError) {
    const keys: Record<string, () => void> = {
      ArrowRight: () => move(index + 1),
      ArrowUp: () => move(index + 1),
      ArrowLeft: () => move(index - 1),
      ArrowDown: () => move(index - 1),
      Home: () => move(0),
      End: () => move(ordered.length - 1),
      Enter: () => onSelect(pair.gameId),
      " ": () => onSelect(pair.gameId),
      Escape: () => onSelect(null),
    };
    const action = keys[event.key];
    if (!action) return;
    event.preventDefault();
    action();
  }

  // Overlapping points are resolved by the nearest one to the pointer, not by whichever is on top.
  function onPlotClick(event: MouseEvent<SVGSVGElement>) {
    const matrix = svgRef.current?.getScreenCTM();
    if (!matrix) return;
    const [nearest] = nearestScatterTeams(ordered.map((pair) => {
      const screen = new DOMPoint(x(lineAbsError(pair)), y(modelAbsError(pair))).matrixTransform(matrix);
      return { team: String(pair.gameId), x: screen.x, y: screen.y };
    }), event.clientX, event.clientY);
    if (nearest === undefined) return;
    setFocusId(Number(nearest));
    nodes.current.get(Number(nearest))?.focus();
    onSelect(Number(nearest));
  }

  const ticks = niceTicks(0, domain, 5);
  const unit = target === "spread" ? "margin" : "total";
  return (
    <svg
      ref={svgRef}
      onClick={onPlotClick}
      viewBox={`0 0 ${W} ${W}`}
      className="mx-auto block h-auto w-full max-w-[560px] text-[10px]"
      role="group"
      aria-label={`${target === "spread" ? "Spread" : "Totals"} absolute error: betting line on the horizontal axis, model on the vertical axis. Points below the diagonal are games where the model was closer.`}
      data-testid="error-scatter"
    >
      {ticks.map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} className="stroke-line" strokeWidth={0.5} />
          <line y1={PAD.top} y2={PAD.top + PLOT.h} x1={x(tick)} x2={x(tick)} className="stroke-line" strokeWidth={0.5} />
          <text x={PAD.left - 5} y={y(tick) + 3} textAnchor="end" className="fill-ink-muted font-mono">{Number.isInteger(tick) ? tick : tick.toFixed(1)}</text>
          <text x={x(tick)} y={PAD.top + PLOT.h + 13} textAnchor="middle" className="fill-ink-muted font-mono">{Number.isInteger(tick) ? tick : tick.toFixed(1)}</text>
        </g>
      ))}
      <line x1={x(0)} y1={y(0)} x2={x(domain)} y2={y(domain)} className="stroke-ink-muted" strokeWidth={1} strokeDasharray="4 3" data-testid="equal-error-diagonal" />
      <text x={W - PAD.right - 4} y={PAD.top + PLOT.h - 6} textAnchor="end" className="fill-ink-muted font-semibold">Model closer</text>
      <text x={PAD.left + 4} y={PAD.top + 12} className="fill-ink-muted font-semibold">Betting line closer</text>
      <text x={PAD.left + PLOT.w / 2} y={W - 6} textAnchor="middle" className="fill-ink-muted">Betting line absolute error ({unit}, pts)</text>
      <text transform={`translate(10 ${PAD.top + PLOT.h / 2}) rotate(-90)`} textAnchor="middle" className="fill-ink-muted">Model absolute error (pts)</text>
      {ordered.map((pair, index) => {
        const selected = pair.gameId === selectedId;
        const cx = x(lineAbsError(pair));
        const cy = y(modelAbsError(pair));
        return (
          <g
            key={pair.gameId}
            ref={(node) => { if (node) nodes.current.set(pair.gameId, node); else nodes.current.delete(pair.gameId); }}
            role="button"
            tabIndex={pair.gameId === tabbable ? 0 : -1}
            aria-pressed={selected}
            aria-label={`${gameName(pair)}, Week ${pair.week}: model error ${modelAbsError(pair).toFixed(1)}, betting line error ${lineAbsError(pair).toFixed(1)}, ${CLOSER_LABEL[closerSide(pair)]} closer`}
            data-testid="error-point"
            className="group cursor-pointer outline-none"
            onKeyDown={(event) => onKeyDown(event, index, pair)}
            onFocus={() => setFocusId(pair.gameId)}
          >
            <circle cx={cx} cy={cy} r={11} className="fill-transparent" />
            <circle cx={cx} cy={cy} r={selected ? 5 : 3.5} className={selected ? "fill-accent stroke-ink" : "fill-ink-muted/60"} strokeWidth={selected ? 1.5 : 0} />
            <circle cx={cx} cy={cy} r={8} className="fill-none stroke-transparent group-focus-visible:stroke-accent" strokeWidth={2} />
          </g>
        );
      })}
      {/* The selected game is drawn last so no neighbouring point hides it. */}
      {selectedPair && <circle cx={x(lineAbsError(selectedPair))} cy={y(modelAbsError(selectedPair))} r={5} className="fill-accent stroke-ink" strokeWidth={1.5} pointerEvents="none" aria-hidden />}
    </svg>
  );
}

function Detail({ target, pair }: { target: MarketTarget; pair: PairedError | null }) {
  return (
    <div data-testid="error-detail" className="min-w-0 rounded-lg bg-surface-inset p-3 text-sm">
      {/* Only this one line is announced; the full detail list below is read on demand. */}
      <p aria-live="polite" className="sr-only">
        {pair === null ? "No game selected." : `${gameName(pair)}, Week ${pair.week}: ${CLOSER_LABEL[closerSide(pair)]} was closer.`}
      </p>
      {pair === null ? (
        <p className="text-ink-muted">Select a point or a table row to see that game’s forecast, line and errors.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold text-ink">{gameName(pair)} <span className="font-normal text-ink-muted">· Week {pair.week}</span></p>
            <MatchupButton gameId={pair.gameId} />
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <dt className="text-ink-muted">Model forecast</dt><dd className="break-words text-ink">{valueText(target, pair, pair.model)}</dd>
            <dt className="text-ink-muted">Retained line</dt><dd className="break-words text-ink">{valueText(target, pair, pair.line)}</dd>
            <dt className="text-ink-muted">Actual</dt><dd className="break-words text-ink">{valueText(target, pair, pair.actual)}</dd>
            <dt className="text-ink-muted">Model error</dt><dd className="break-words text-ink">{errorText(target, pair, pair.modelError)}</dd>
            <dt className="text-ink-muted">Line error</dt><dd className="break-words text-ink">{errorText(target, pair, pair.lineError)}</dd>
            <dt className="text-ink-muted">Closer</dt><dd className="text-ink">{CLOSER_LABEL[closerSide(pair)]}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}

const COLUMNS: { key: PairedSortKey; label: string; numeric: boolean }[] = [
  { key: "game", label: "Game", numeric: false },
  { key: "week", label: "Week", numeric: true },
  { key: "forecast", label: "Model forecast", numeric: true },
  { key: "line", label: "Retained line", numeric: true },
  { key: "actual", label: "Actual", numeric: true },
  { key: "modelError", label: "Model error", numeric: true },
  { key: "lineError", label: "Line error", numeric: true },
  { key: "closer", label: "Closer", numeric: false },
];

function ErrorTable({
  target,
  pairs,
  selectedId,
  onSelect,
}: {
  target: MarketTarget;
  pairs: PairedError[];
  selectedId: number | null;
  onSelect: (gameId: number) => void;
}) {
  const [sort, setSort] = useState<{ key: PairedSortKey; direction: SortDirection }>({ key: "week", direction: "asc" });
  const rows = useMemo(() => sortPairedErrors(pairs, sort.key, sort.direction), [pairs, sort]);
  const toggle = (key: PairedSortKey) =>
    setSort((current) => ({ key, direction: current.key === key && current.direction === "asc" ? "desc" : "asc" }));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm tabular-nums" data-testid="error-table">
        <caption className="sr-only">
          {target === "spread" ? "Spread" : "Totals"} paired errors, the same games as the scatter. Errors are absolute points; forecast, line and actual are {target === "spread" ? "home margins" : "combined points"}.
        </caption>
        <thead className="border-b border-line bg-surface-inset text-xs text-ink-muted">
          <tr>
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                scope="col"
                aria-sort={sort.key === column.key ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
                className={clsx("whitespace-nowrap px-2 py-1 font-medium", column.numeric && "text-right")}
              >
                <button type="button" onClick={() => toggle(column.key)} className="min-h-11 min-w-11 rounded px-1 font-medium hover:text-ink focus-visible:outline-2 focus-visible:outline-accent pointer-fine:min-h-8">
                  {column.label}{sort.key === column.key && <span aria-hidden> {sort.direction === "asc" ? "▲" : "▼"}</span>}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((pair) => (
            <tr key={pair.gameId} className={clsx(pair.gameId === selectedId && "bg-surface-inset")}>
              <th scope="row" className="px-2 py-1 text-left font-normal">
                <button type="button" aria-pressed={pair.gameId === selectedId} onClick={() => onSelect(pair.gameId)} className="min-h-11 whitespace-nowrap rounded px-1 text-left font-medium text-ink hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent pointer-fine:min-h-8">
                  {gameName(pair)}
                </button>
              </th>
              <td className="px-2 py-1 text-right">{pair.week}</td>
              <td className="px-2 py-1 text-right">{target === "spread" ? signed(pair.model) : pair.model.toFixed(1)}</td>
              <td className="px-2 py-1 text-right">{target === "spread" ? signed(pair.line) : pair.line.toFixed(1)}</td>
              <td className="px-2 py-1 text-right">{target === "spread" ? signed(pair.actual) : pair.actual.toFixed(1)}</td>
              <td className="px-2 py-1 text-right">{modelAbsError(pair).toFixed(1)}</td>
              <td className="px-2 py-1 text-right">{lineAbsError(pair).toFixed(1)}</td>
              <td className="whitespace-nowrap px-2 py-1">{CLOSER_LABEL[closerSide(pair)]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Model-versus-line absolute error for one target, with a table of the same games. */
export function ErrorExplorer({
  pairs,
}: {
  pairs: Record<MarketTarget, PairedError[]>;
}) {
  const target = parseTarget(useSearchParams().get("target"));
  // Keyed to its target so Back/Forward changing `?target=` drops the selection too.
  const [selection, setSelection] = useState<{ target: MarketTarget; id: number | null } | null>(null);
  const selectedId = selection?.target === target ? selection.id : null;
  const setSelectedId = (id: number | null) => setSelection({ target, id });
  const rows = pairs[target];
  const selected = rows.find((pair) => pair.gameId === selectedId) ?? null;

  function changeTarget(next: MarketTarget) {
    replaceSearchParams("/model", (params) => params.set("target", next));
  }

  return (
    <section aria-labelledby="errors-heading" className="space-y-2" data-testid="error-explorer">
      <h2 id="errors-heading" className="text-sm font-semibold text-ink">Where the model and the line disagreed</h2>
      <p className="text-xs leading-relaxed text-ink-muted">
        Each point is one game with a retained pre-kickoff line. The horizontal axis is how far the betting line was from the final score and the vertical axis is how far the model was, both in points. Below the dashed diagonal the model was closer; above it the betting line was closer.
      </p>
      <SegmentedControl label="Error target" value={target} onChange={changeTarget} options={TARGET_OPTIONS} fill />
      <Card padding="sm" className="space-y-3 sm:p-4">
        {rows.length === 0 ? (
          <p className="text-sm text-ink-muted">No paired games for this target yet.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-[minmax(0,560px)_minmax(0,1fr)] md:items-start">
            <div className="min-w-0">
              <Scatter key={target} target={target} pairs={rows} selectedId={selected?.gameId ?? null} onSelect={setSelectedId} />
              <p className="mt-1 text-center text-xs text-ink-muted max-sm:hidden">Arrow keys move between points, Enter selects, Escape clears the selection.</p>
            </div>
            <Detail target={target} pair={selected} />
          </div>
        )}
        <p className="text-xs text-ink-muted" data-testid="error-count">
          {rows.length} {rows.length === 1 ? "game" : "games"} · pushes included · the table lists the same games and values.
        </p>
        {rows.length > 0 && (
          <details data-testid="error-table-details" className="rounded-lg border border-line">
            <summary className="min-h-11 cursor-pointer px-3 py-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-accent pointer-fine:min-h-9 pointer-fine:py-2">Table view of the same games</summary>
            <div className="max-h-96 overflow-y-auto">
              <ErrorTable key={target} target={target} pairs={rows} selectedId={selected?.gameId ?? null} onSelect={setSelectedId} />
            </div>
          </details>
        )}
      </Card>
    </section>
  );
}
