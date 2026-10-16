import type { AdjustedRow, RosterRow, TeamGameRow } from "@/lib/charts";
import { LOGO_IDS } from "@/lib/team-logos.generated";

/**
 * Deterministic chart data for UI tests: a 17-team FBS roster (one team with no games),
 * four completed weeks of mirrored team-game rows (weeks 0-3) and adjusted windows for
 * as_of_week 3 and 4. Values are plausible, not real.
 */
export const chartsRosterFixture: RosterRow[] = [
  ["Alabama", "SEC"], ["Georgia", "SEC"], ["Texas", "SEC"], ["LSU", "SEC"],
  ["Michigan", "Big Ten"], ["Ohio State", "Big Ten"], ["Oregon", "Big Ten"], ["Penn State", "Big Ten"],
  ["Utah", "Big 12"], ["Kansas State", "Big 12"], ["Clemson", "ACC"], ["Miami", "ACC"],
  ["Notre Dame", "FBS Independents"], ["Tulane", "American Athletic"], ["Boise State", "Mountain West"],
  ["App State", "Sun Belt"], ["Wyoming", "Mountain West"],
].map(([team, conference]) => ({ team, conference }));

const PLAYING = chartsRosterFixture.slice(0, 16).map((r) => r.team);

function lcg(seed: number) {
  let state = seed;
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}

/** Circle-method round robin: every team plays once per week. */
function pairings(week: number): Array<[string, string]> {
  const rest = PLAYING.slice(1);
  const rotated = [...rest.slice(week % rest.length), ...rest.slice(0, week % rest.length)];
  const order = [PLAYING[0], ...rotated];
  const half = order.length / 2;
  return Array.from({ length: half }, (_, i) => [order[i], order[order.length - 1 - i]] as [string, string]);
}

function buildGameRows(): TeamGameRow[] {
  const random = lcg(2026);
  const strength = new Map(PLAYING.map((team) => [team, random() * 0.5 - 0.25]));
  const rows: TeamGameRow[] = [];
  let gameId = 1000;
  for (let week = 0; week <= 3; week++) {
    for (const [home, away] of pairings(week)) {
      gameId += 1;
      const side = (team: string, opponent: string) => {
        const plays = 55 + Math.floor(random() * 25);
        const edge = (strength.get(team) ?? 0) - (strength.get(opponent) ?? 0) * 0.5;
        const success = Math.min(plays, Math.max(0, Math.round(plays * (0.42 + edge * 0.35 + (random() - 0.5) * 0.08))));
        const epa = (edge * 0.5 + (random() - 0.5) * 0.12) * plays;
        return { plays, success, epa: Number(epa.toFixed(3)) };
      };
      const h = side(home, away);
      const a = side(away, home);
      const homePoints = Math.max(0, Math.round(24 + (h.epa - a.epa) * 0.9 + (random() - 0.5) * 10));
      const awayPoints = Math.max(0, Math.round(24 + (a.epa - h.epa) * 0.9 + (random() - 0.5) * 10));
      const pair = [
        { team: home, opponent: away, site: "home" as const, own: h, other: a, pf: homePoints, pa: awayPoints },
        { team: away, opponent: home, site: "away" as const, own: a, other: h, pf: awayPoints, pa: homePoints },
      ];
      for (const { team, opponent, site, own, other, pf, pa } of pair) {
        rows.push({
          week, gameId, team, opponent, site, pointsFor: pf, pointsAgainst: pa,
          offPlays: own.plays, offSuccessN: own.plays, offSuccessSum: own.success, offEpaN: own.plays, offEpaSum: own.epa,
          defPlays: other.plays, defSuccessN: other.plays, defSuccessSum: other.success, defEpaN: other.plays, defEpaSum: other.epa,
        });
      }
    }
  }
  return rows;
}

export const chartsGameRowsFixture: TeamGameRow[] = buildGameRows();

/** Adjusted windows for as_of_week 3 and 4; Notre Dame has no defense row in window 4. */
export function chartsAdjustedFixture(asOfWeek: number): AdjustedRow[] {
  const rows: AdjustedRow[] = [];
  for (const { team } of chartsRosterFixture.slice(0, 16)) {
    const mine = chartsGameRowsFixture.filter((r) => r.team === team && r.week < asOfWeek);
    if (!mine.length) continue;
    for (const role of ["offense", "defense"] as const) {
      if (asOfWeek === 4 && team === "Notre Dame" && role === "defense") continue;
      const n = mine.reduce((sum, r) => sum + (role === "offense" ? r.offEpaN : r.defEpaN), 0);
      const total = mine.reduce((sum, r) => sum + (role === "offense" ? r.offEpaSum : r.defEpaSum), 0);
      const raw = total / n;
      const venue = 0.004;
      const opponent = 0.011;
      rows.push({
        asOfWeek, team, role, rawEpaPerPlay: raw, venueCorrection: venue,
        opponentAdjustment: opponent, adjustedEpaPerPlay: raw - venue - opponent,
        epaN: n, games: mine.length, adjustedRank: 1, cohortSize: 16,
      });
    }
  }
  return rows;
}

export const chartsAdjustedWeeksFixture = [3, 4];

/**
 * A full Week 0 slate (69 games between every logo-bearing school) for export-width tests:
 * 140 + 30 * 69 = 2210 px wide.
 */
export function chartsSlateFixture(): { roster: RosterRow[]; rows: TeamGameRow[] } {
  const names = Object.keys(LOGO_IDS);
  const random = lcg(7);
  const rows: TeamGameRow[] = [];
  const build = (
    gameId: number, team: string, opponent: string, site: "home" | "away",
    pf: number, pa: number, own: number, other: number,
  ): TeamGameRow => ({
    week: 0, gameId, team, opponent, site, pointsFor: pf, pointsAgainst: pa,
    offPlays: 70, offSuccessN: 70, offSuccessSum: own, offEpaN: 70, offEpaSum: own / 100,
    defPlays: 70, defSuccessN: 70, defSuccessSum: other, defEpaN: 70, defEpaSum: other / 100,
  });
  for (let i = 0; i < Math.floor(names.length / 2); i++) {
    const home = names[2 * i];
    const away = names[2 * i + 1];
    const homeSuccess = 20 + Math.floor(random() * 25);
    const awaySuccess = 20 + Math.floor(random() * 25);
    const homePoints = 14 + Math.floor(random() * 30);
    const awayPoints = homePoints + (3 + Math.floor(random() * 14)) * (random() < 0.5 ? 1 : -1); // never tied
    rows.push(build(5000 + i, home, away, "home", homePoints, awayPoints, homeSuccess, awaySuccess));
    rows.push(build(5000 + i, away, home, "away", awayPoints, homePoints, awaySuccess, homeSuccess));
  }
  // Keep Week 0 as the full 69-game export slate; a second completed window
  // also exercises dense national scatter layouts without changing that slate.
  const later = rows.map((row) => ({ ...row, week: 2, gameId: row.gameId + 1000, offEpaSum: Number(((random() - 0.5) * 0.5 * row.offEpaN).toFixed(3)) }));
  for (let i = 0; i < later.length; i += 2) {
    later[i].defEpaSum = later[i + 1].offEpaSum;
    later[i + 1].defEpaSum = later[i].offEpaSum;
  }
  rows.push(...later);
  return { roster: names.map((team) => ({ team, conference: "Fixture" })), rows };
}
