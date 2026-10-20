"use client";

import { chartColor, niceTicks, valueLabelY, type Domain, type GameLogGame, type Side, type TeamGameLog } from "@/lib/charts";
import { FALLBACK_TEAM_COLOR, teamAltColor, teamColor } from "@/lib/team-logos";
import { TeamMark } from "./TeamMark";
import { useChartSelection } from "./useChartSelection";

export type GameLogChartProps = {
  log: TeamGameLog;
  /**
   * Each panel's value window. Both panels draw at one pixels-per-unit scale (heights are
   * proportional to the windows' spans), so bar lengths compare across panels.
   */
  domains: Record<Side, Domain>;
  formatTick: (value: number) => string;
  /** A bar's value as printed at its tip ("56.0%"). */
  formatValue: (value: number) => string;
  describe: (game: GameLogGame) => string;
  width: number;
  height: number;
  interactive?: boolean;
  label: string;
};

const MARGIN = { top: 26, right: 14, left: 62 };
/** Panel title row above each plot. */
const TITLE = 22;
const PANEL_GAP = 14;
/** Opponent logo, result and week under the defense panel. */
const FOOTER = 66;

/** Result letter to text color; the letter itself is the non-color cue. */
const RESULT_FILL: Record<string, string> = { W: "var(--win)", L: "var(--loss)" };

const PANELS: readonly { side: Side; title: string }[] = [
  { side: "offense", title: "Offense" },
  { side: "defense", title: "Defense allowed (axis inverted: up is better)" },
];

/**
 * One bar per game in an offense panel and a defense-allowed panel (inverted), with the
 * week's dashed FBS average across each bar's band. A game without a value keeps its slot
 * and reads "n/a". Each game is one focus stop covering both panels.
 */
export function GameLogChart({ log, domains, formatTick, formatValue, describe, width, height, interactive = true, label }: GameLogChartProps) {
  const keys = log.games.map((game) => String(game.gameId));
  const { selected, register, handlers } = useChartSelection(keys);
  const tipGame = interactive && selected ? log.games.find((game) => String(game.gameId) === selected) : undefined;
  const fill = chartColor(teamColor(log.team), teamAltColor(log.team), FALLBACK_TEAM_COLOR);

  const plotLeft = MARGIN.left;
  const plotRight = width - MARGIN.right;
  // Both panels share the height left after titles, gap and footer, split by window span so
  // one unit is the same number of pixels in each (with a floor so a tiny panel stays legible).
  const spans = { offense: domains.offense[1] - domains.offense[0], defense: domains.defense[1] - domains.defense[0] };
  const available = height - MARGIN.top - FOOTER - PANEL_GAP - 2 * TITLE;
  const share = Math.min(0.75, Math.max(0.25, spans.offense / (spans.offense + spans.defense)));
  const panelHeights: Record<Side, number> = { offense: available * share, defense: available * (1 - share) };
  const panelTop = (index: number) => MARGIN.top + TITLE + (index === 0 ? 0 : panelHeights.offense + PANEL_GAP + TITLE);
  // Offense: higher is up. Defense allowed: lower is up (better).
  const yOf = (side: Side, value: number) => {
    const [lo, hi] = domains[side];
    const t = (value - lo) / (hi - lo);
    const top = panelTop(side === "offense" ? 0 : 1);
    return side === "offense" ? top + (1 - t) * panelHeights.offense : top + t * panelHeights.defense;
  };
  const band = (plotRight - plotLeft) / Math.max(1, log.games.length);
  const thick = Math.max(4, Math.min(44, band * 0.56));
  const logo = Math.max(14, Math.min(26, band * 0.6));
  const ticksOf = (side: Side) => {
    const [lo, hi] = domains[side];
    return niceTicks(lo, hi, Math.max(2, Math.round(panelHeights[side] / 55))).filter((tick) => tick >= lo && tick <= hi);
  };
  const footerTop = panelTop(1) + panelHeights.defense;
  const center = (index: number) => plotLeft + band * (index + 0.5);

  function tooltipPosition(index: number) {
    const x = center(index);
    const y = panelTop(0) + panelHeights.offense * 0.4;
    return {
      left: `${(x / width) * 100}%`,
      top: `${(y / height) * 100}%`,
      transform: `translate(${x > width * 0.6 ? "-105%" : "12px"}, 0)`,
    };
  }

  return (
    <div className="relative" data-testid="game-log-chart">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="group" aria-label={label} className="block h-auto w-full select-none">
        <g data-testid="game-log-legend" aria-hidden>
          <line x1={plotRight - 168} x2={plotRight - 146} y1={12} y2={12} stroke="var(--ink-muted)" strokeWidth={1.5} strokeDasharray="5 3" />
          <text x={plotRight - 140} y={12} dominantBaseline="central" fontSize={11} fill="var(--ink-muted)">
            FBS average that week
          </text>
        </g>
        {PANELS.map(({ side, title }, index) => {
          const top = panelTop(index);
          const zero = yOf(side, 0);
          return (
            <g key={side} data-testid={`game-log-panel-${side}`}>
              <text x={plotLeft} y={top - 8} fontSize={12} fontWeight={600} fill="var(--ink)">
                {title}
              </text>
              <rect x={plotLeft} y={top} width={plotRight - plotLeft} height={panelHeights[side]} fill="var(--surface-card)" stroke="var(--line)" />
              {ticksOf(side).map((tick) => (
                <g key={tick}>
                  <line x1={plotLeft} x2={plotRight} y1={yOf(side, tick)} y2={yOf(side, tick)} stroke="var(--line)" strokeWidth={0.6} />
                  <text x={plotLeft - 8} y={yOf(side, tick)} textAnchor="end" dominantBaseline="central" fontSize={11} fill="var(--ink-muted)">
                    {formatTick(tick)}
                  </text>
                </g>
              ))}
              <line x1={plotLeft} x2={plotRight} y1={zero} y2={zero} stroke="var(--ink-muted)" strokeWidth={1} />
            </g>
          );
        })}
        {log.games.map((game, index) => {
          const key = String(game.gameId);
          const c = center(index);
          return (
            <g
              key={key}
              ref={register(key)}
              role="img"
              aria-label={describe(game)}
              tabIndex={interactive ? 0 : undefined}
              data-game={game.gameId}
              className="outline-none [&:focus-visible>rect.focus-ring]:opacity-100"
              {...(interactive ? handlers(key) : {})}
            >
              {interactive && (
                <rect className="focus-ring opacity-0" x={c - band / 2} y={panelTop(0)} width={band} height={footerTop + FOOTER - panelTop(0) - 4} fill="none" stroke="var(--accent)" strokeWidth={2} />
              )}
              {game.result.startsWith("L") && (
                <rect x={c - band / 2 + 2} y={panelTop(0)} width={band - 4} height={footerTop + FOOTER - panelTop(0) - 4} fill="var(--loss-soft)" opacity={0.6} data-loss-band />
              )}
              {/* Transparent hit target over the whole column. */}
              <rect x={c - band / 2} y={panelTop(0)} width={band} height={footerTop + FOOTER - panelTop(0) - 4} fill="transparent" />
              {PANELS.map(({ side }) => {
                const value = game[side];
                const zero = yOf(side, 0);
                const average = game.average[side];
                return (
                  <g key={side} data-side={side}>
                    {value === null ? (
                      <text x={c} y={zero + (side === "offense" ? -10 : 12)} textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600} fill="var(--ink-muted)" data-na>
                        n/a
                      </text>
                    ) : value === 0 ? (
                      <line x1={c - thick / 2} x2={c + thick / 2} y1={zero} y2={zero} stroke={fill} strokeWidth={2} data-bar />
                    ) : (
                      <rect x={c - thick / 2} y={Math.min(zero, yOf(side, value))} width={thick} height={Math.abs(yOf(side, value) - zero)} fill={fill} data-bar />
                    )}
                    {value !== null && value !== 0 && (
                      <text
                        x={c}
                        y={valueLabelY(yOf(side, value), zero, average === null ? null : yOf(side, average))}
                        textAnchor="middle"
                        fontSize={11}
                        fontWeight={600}
                        fill="var(--ink)"
                        stroke="var(--surface-card)"
                        strokeWidth={2}
                        strokeOpacity={0.8}
                        strokeLinejoin="round"
                        paintOrder="stroke"
                        data-value-label
                      >
                        {formatValue(value)}
                      </text>
                    )}
                    {average !== null && (
                      <line x1={c - band * 0.42} x2={c + band * 0.42} y1={yOf(side, average)} y2={yOf(side, average)} stroke="var(--ink)" strokeWidth={1.5} strokeDasharray="5 3" data-average />
                    )}
                  </g>
                );
              })}
              <text x={c - logo / 2 - 5} y={footerTop + 6 + logo / 2} textAnchor="end" dominantBaseline="central" fontSize={11} fontWeight={600} fill="var(--ink-muted)" data-site-marker>
                {game.site === "away" ? "@" : "vs"}
              </text>
              <TeamMark team={game.opponent} cx={c} cy={footerTop + 6 + logo / 2} size={logo} />
              <text x={c} y={footerTop + 12 + logo + 6} textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={700} fill={RESULT_FILL[game.result[0]] ?? "var(--ink)"} data-result={game.result[0]}>
                {game.result}
              </text>
              <text x={c} y={footerTop + 12 + logo + 20} textAnchor="middle" dominantBaseline="central" fontSize={10} fill="var(--ink-muted)">
                {`Wk ${game.week}${game.site === "neutral" ? " · neutral" : ""}`}
              </text>
            </g>
          );
        })}
      </svg>
      {tipGame && (
        <div
          role="status"
          data-testid="chart-tooltip"
          className="pointer-events-none absolute z-10 max-w-72 rounded-lg border border-line bg-surface-card px-2.5 py-1.5 text-xs leading-snug text-ink shadow-md"
          style={tooltipPosition(log.games.indexOf(tipGame))}
        >
          {describe(tipGame)}
        </div>
      )}
    </div>
  );
}
