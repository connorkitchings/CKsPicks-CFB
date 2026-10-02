import { forwardRef, type CSSProperties } from "react";
import type { MatchupData } from "@/lib/matchup";
import { formatKickoff, venueLine } from "@/lib/matchup-format";
import { logoSrc, teamInitials } from "@/lib/team-logos";
import {
  groupUnitRows,
  hasMissingValue,
  mismatchSummary,
  rankLabel,
  rankTier,
  topMismatches,
  type Mismatch,
  type RankTier,
  type UnitMatchupRow,
} from "@/lib/team-stats";

/** Export size in CSS pixels; the button rasterizes at 2x. */
export const SHARE_CARD_WIDTH = 1080;
export const SHARE_CARD_HEIGHT = 1350;

/**
 * Fixed-size, always-dark card for sharing one matchup as an image. Its colors are
 * literal values, not theme tokens, and logos are the dark variants chosen with
 * `logoSrc(..., "dark")` (never `TeamLogo`, which swaps by the viewer's theme), so
 * the capture looks the same in a light- or dark-mode browser.
 */
const C = {
  bg: "#0b0b0d",
  panel: "#141417",
  inset: "#1c1c21",
  line: "#2a2a31",
  ink: "#f4f4f5",
  muted: "#a1a1aa",
  faint: "#71717a",
  accent: "#93c5fd",
} as const;

const TIER_STYLE: Record<RankTier, CSSProperties> = {
  none: { background: "#1a1a1d", color: C.faint, border: `1px solid ${C.line}`, fontWeight: 500 },
  top: { background: "rgba(59,130,246,0.18)", color: "#93c5fd", border: "1px solid rgba(59,130,246,0.4)", fontWeight: 700 },
  high: { background: "rgba(6,182,212,0.12)", color: "#67e8f9", border: "1px solid rgba(6,182,212,0.3)", fontWeight: 600 },
  mid: { background: C.inset, color: C.muted, border: `1px solid ${C.line}`, fontWeight: 500 },
  low: { background: "rgba(239,68,68,0.14)", color: "#fca5a5", border: "1px solid rgba(239,68,68,0.3)", fontWeight: 500 },
};

const sans = "var(--font-geist-sans), system-ui, -apple-system, 'Segoe UI', sans-serif";
const mono = "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, monospace";

function Logo({ name, size }: { name: string; size: number }) {
  const src = logoSrc(name, "lg", "dark");
  if (!src) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: size,
          background: C.inset,
          color: C.muted,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: size * 0.38,
          fontWeight: 600,
          flexShrink: 0,
        }}
      >
        {teamInitials(name)}
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt="" width={size} height={size} style={{ width: size, height: size, objectFit: "contain", flexShrink: 0 }} />;
}

function Badge({ rank, cohort, tied }: { rank: number | null; cohort: number | null; tied: boolean }) {
  return (
    <span
      style={{
        ...TIER_STYLE[rankTier(rank, cohort)],
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        height: 26,
        minWidth: 46,
        padding: "0 7px",
        borderRadius: 6,
        fontSize: 15,
        whiteSpace: "nowrap",
      }}
    >
      {rankLabel(rank, tied)}
    </span>
  );
}

function TeamHeader({
  name,
  side,
  record,
  rank,
}: {
  name: string;
  side: string;
  record: string | null;
  rank: number | null;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", width: 232, flexShrink: 0 }}>
      <Logo name={name} size={120} />
      <div style={{ marginTop: 10, fontSize: 29, fontWeight: 700, lineHeight: 1.1, letterSpacing: -0.5, minHeight: 64, display: "flex", alignItems: "center" }}>
        {name}
      </div>
      <div style={{ marginTop: 2, fontSize: 17, color: C.faint }}>
        {side}
        {record ? ` · ${record}` : ""}
      </div>
      <div
        style={{
          marginTop: 10,
          background: C.inset,
          borderRadius: 7,
          padding: "5px 14px",
          fontSize: 18,
          fontWeight: 600,
        }}
      >
        Model Rank <span style={{ fontFamily: mono }}>#{rank ?? "—"}</span>
      </div>
    </div>
  );
}

function Cell({ value, accent = false, muted = false }: { value: string; accent?: boolean; muted?: boolean }) {
  return (
    <div
      style={{
        textAlign: "center",
        fontFamily: mono,
        fontSize: 20,
        fontWeight: 500,
        lineHeight: 1.15,
        color: muted ? C.faint : accent ? C.accent : C.ink,
      }}
    >
      {value}
    </div>
  );
}

function Forecast({ matchup }: { matchup: MatchupData }) {
  const predictions = matchup.publicationMode === "predictions";
  const isFinal = matchup.homeFinalPoints !== null && matchup.awayFinalPoints !== null;
  const label: CSSProperties = { fontSize: 17, fontWeight: 500, color: C.muted, whiteSpace: "nowrap" };
  const head: CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    color: C.faint,
    textAlign: "center",
  };
  const betSpread = matchup.spreadLean
    ? matchup.spreadLean === "home"
      ? matchup.homeTeam
      : matchup.awayTeam
    : null;
  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        margin: "0 16px",
        background: C.panel,
        border: `1px solid ${C.line}`,
        borderRadius: 14,
        padding: "16px 18px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: 1.4, textTransform: "uppercase", color: C.muted }}>
        Forecast &amp; Lines
      </div>
      <div
        style={{
          marginTop: 12,
          width: "100%",
          display: "grid",
          gridTemplateColumns: "auto minmax(0, 1fr) auto",
          columnGap: 14,
          rowGap: 12,
          alignItems: "center",
        }}
      >
        <span />
        <span style={head}>Spread</span>
        <span style={head}>Total</span>
        <span style={label}>Market</span>
        <Cell value={matchup.marketSpread} />
        <Cell value={matchup.marketTotal ? matchup.marketTotal.toFixed(1) : "—"} />
        {predictions && (
          <>
            <span style={label}>Model</span>
            <Cell value={matchup.modelSpread} />
            <Cell value={matchup.modelTotal ? matchup.modelTotal.toFixed(1) : "—"} />
            <div style={{ gridColumn: "1 / -1", borderTop: `1px solid ${C.line}` }} />
            <span style={label}>Model Bet</span>
            <Cell accent={Boolean(betSpread)} muted={!betSpread} value={betSpread ?? "No Spread"} />
            <Cell
              accent={Boolean(matchup.totalLean)}
              muted={!matchup.totalLean}
              value={matchup.totalLean ? (matchup.totalLean === "over" ? "Over" : "Under") : "—"}
            />
          </>
        )}
      </div>
      {isFinal && (
        <div style={{ marginTop: 12, fontSize: 13, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: C.muted }}>
          Final: {matchup.awayFinalPoints}–{matchup.homeFinalPoints}
        </div>
      )}
    </div>
  );
}

function MismatchBox({ items }: { items: Mismatch[] }) {
  return (
    <div
      data-testid="share-mismatches"
      style={{ width: 494, background: C.panel, border: `1px solid ${C.line}`, borderRadius: 14, padding: "12px 16px 10px" }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: 1.4, textTransform: "uppercase", color: C.accent }}>
        Biggest mismatches
      </div>
      {items.length === 0 && <div style={{ marginTop: 8, fontSize: 15, color: C.faint }}>No lopsided matchups here.</div>}
      {items.map((m) => (
        <div
          key={m.metric}
          style={{ marginTop: 9, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.3 }}>{m.metric}</div>
            <div style={{ marginTop: 2, fontSize: 15, color: C.accent }}>{mismatchSummary(m)}</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <Badge rank={m.favored.rank} cohort={m.favored.cohort} tied={m.favored.tied} />
            <span style={{ fontSize: 12, color: C.faint, textTransform: "uppercase", letterSpacing: 1 }}>vs</span>
            <Badge rank={m.other.rank} cohort={m.other.cohort} tied={m.other.tied} />
          </div>
        </div>
      ))}
    </div>
  );
}

const COLS = ["96px", "56px", "minmax(0, 1fr)", "56px", "96px"].join(" ");

function Panel({
  offenseTeam,
  defenseTeam,
  rows,
  offenseRank,
  defenseRank,
}: {
  offenseTeam: string;
  defenseTeam: string;
  rows: UnitMatchupRow[];
  offenseRank: number | null;
  defenseRank: number | null;
}) {
  const unitName: CSSProperties = { fontSize: 17, fontWeight: 700, lineHeight: 1.1, textAlign: "center" };
  const unitRole: CSSProperties = { fontSize: 12, fontWeight: 600, letterSpacing: 1.2, textTransform: "uppercase" };
  const unitRank: CSSProperties = { fontSize: 13, color: C.muted, whiteSpace: "nowrap" };
  return (
    <div
      style={{
        width: 494,
        background: C.panel,
        border: `1px solid ${C.line}`,
        borderRadius: 14,
        padding: "14px 10px 8px",
      }}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", columnGap: 8, alignItems: "start", paddingBottom: 8, borderBottom: `1px solid ${C.line}` }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
          <Logo name={offenseTeam} size={36} />
          <div style={unitName}>{offenseTeam}</div>
          <div style={{ ...unitRole, color: C.accent }}>Offense</div>
          <div style={unitRank}>Model Offense Rank #{offenseRank ?? "—"}</div>
        </div>
        <div style={{ marginTop: 14, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: C.faint, textTransform: "uppercase" }}>vs</div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
          <Logo name={defenseTeam} size={36} />
          <div style={unitName}>{defenseTeam}</div>
          <div style={{ ...unitRole, color: C.muted }}>Defense</div>
          <div style={unitRank}>Model Defense Rank #{defenseRank ?? "—"}</div>
        </div>
      </div>
      {groupUnitRows(rows).map((group) => (
        <div key={group.section}>
          <div
            style={{
              height: 28,
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "center",
              paddingBottom: 3,
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: 1.2,
              textTransform: "uppercase",
              color: C.faint,
            }}
          >
            {group.label}
          </div>
          {group.rows.map((row) => (
            <div
              key={row.key}
              style={{
                height: 41,
                display: "grid",
                gridTemplateColumns: COLS,
                alignItems: "center",
                borderTop: `1px solid ${C.line}`,
              }}
            >
              <div style={{ paddingLeft: 6, fontFamily: mono, fontSize: 17, fontWeight: 500, whiteSpace: "nowrap" }}>
                {row.offenseValue}
              </div>
              <div style={{ textAlign: "center" }}>
                <Badge rank={row.offenseRank} cohort={row.offenseCohort} tied={row.offenseTied} />
              </div>
              <div style={{ padding: "0 4px", textAlign: "center", fontSize: 13, fontWeight: 600, lineHeight: 1.1, textTransform: "uppercase", letterSpacing: 0.3 }}>
                {row.name.replace(/\//g, "/\u200b")}
              </div>
              <div style={{ textAlign: "center" }}>
                <Badge rank={row.defenseRank} cohort={row.defenseCohort} tied={row.defenseTied} />
              </div>
              <div style={{ paddingRight: 6, textAlign: "right", fontFamily: mono, fontSize: 17, fontWeight: 500, whiteSpace: "nowrap" }}>
                {row.defenseValue}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

/** The card root node; the share button rasterizes exactly this element. */
export const ShareCard = forwardRef<HTMLDivElement, { matchup: MatchupData }>(function ShareCard(
  { matchup },
  ref,
) {
  const stats = matchup.stats;
  if (!stats) return null;
  const venue = venueLine(matchup);
  const awayPanelEdges = topMismatches(
    [{ offenseTeam: matchup.awayTeam, defenseTeam: matchup.homeTeam, rows: stats.awayOffVsHomeDef }],
    2,
  );
  const homePanelEdges = topMismatches(
    [{ offenseTeam: matchup.homeTeam, defenseTeam: matchup.awayTeam, rows: stats.homeOffVsAwayDef }],
    2,
  );
  return (
    <div
      ref={ref}
      data-testid="share-card"
      style={{
        width: SHARE_CARD_WIDTH,
        height: SHARE_CARD_HEIGHT,
        boxSizing: "border-box",
        padding: "34px 40px 28px",
        background: C.bg,
        color: C.ink,
        fontFamily: sans,
        display: "flex",
        flexDirection: "column",
        gap: 16,
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", borderBottom: `1px solid ${C.line}`, paddingBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <span style={{ fontSize: 28, fontWeight: 800, letterSpacing: -0.5 }}>CK&rsquo;s Picks</span>
          <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: 1.4, textTransform: "uppercase", color: C.accent }}>
            CFB · Week {matchup.week}
          </span>
        </div>
        <div style={{ fontSize: 16, color: C.muted }}>
          {formatKickoff(matchup.startDate, "America/New_York")}
          {venue ? ` · ${venue}` : ""}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <TeamHeader name={matchup.awayTeam} side="Away" record={matchup.awayRecord} rank={matchup.awayRating.rank} />
        <Forecast matchup={matchup} />
        <TeamHeader name={matchup.homeTeam} side="Home" record={matchup.homeRecord} rank={matchup.homeRating.rank} />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Panel
          offenseTeam={matchup.awayTeam}
          defenseTeam={matchup.homeTeam}
          rows={stats.awayOffVsHomeDef}
          offenseRank={matchup.awayRating.offenseRank}
          defenseRank={matchup.homeRating.defenseRank}
        />
        <Panel
          offenseTeam={matchup.homeTeam}
          defenseTeam={matchup.awayTeam}
          rows={stats.homeOffVsAwayDef}
          offenseRank={matchup.homeRating.offenseRank}
          defenseRank={matchup.awayRating.defenseRank}
        />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <MismatchBox items={awayPanelEdges} />
        <MismatchBox items={homePanelEdges} />
      </div>

      <div style={{ marginTop: "auto", fontSize: 12, lineHeight: 1.45, color: C.faint }}>
        <div>
          Stats through Week {stats.asOfWeek - 1}. FBS opponents only, regulation play, garbage time excluded; raw, not
          opponent-adjusted.
        </div>
        <div>
          Defense columns show what that defense allowed.
          {stats.cohortSize !== null ? ` Ranks are among ${stats.cohortSize} teams; T = tied.` : ""}
          {hasMissingValue(stats.awayOffVsHomeDef, stats.homeOffVsAwayDef) ? " — = not enough clean data." : ""}
        </div>
        <div>Team names and logos are trademarks of their respective schools and owners, shown for identification only.</div>
      </div>
    </div>
  );
});
