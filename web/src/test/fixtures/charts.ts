import type { AdjustedRow, PossessionRow, RatingSnapshotRow, RosterRow, TeamGameRow, TeamGameYardageRow } from "@/lib/charts";
import { LOGO_IDS } from "@/lib/team-logos.generated";

/**
 * Deterministic chart data for UI tests: a 17-team FBS roster (one team with no games),
 * four completed weeks of mirrored team-game rows (weeks 0-3), their mirrored yardage
 * rows and adjusted windows for as_of_week 3 and 4. Values are plausible, not real. A
 * `charts_v1` release serves the game rows alone; `charts_v2` adds the yardage.
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

/**
 * One mirrored `team_game_yardage` row per team-game, within the release bounds
 * (`explosive_n <= yards_n <= plays`, `success_yards_n <= success_n`). It draws from its
 * own generator so the game rows stay unchanged.
 */
function buildYardage(rows: readonly TeamGameRow[], seed: number): TeamGameYardageRow[] {
  const random = lcg(seed);
  const offense = new Map<string, Pick<TeamGameYardageRow, "offYardsN" | "offExplosiveN" | "offSuccessYardsN" | "offSuccessYardsSum">>();
  for (const row of rows) {
    const yards = row.offPlays - (random() < 0.2 ? 1 : 0);
    const successYards = Math.min(Math.round(row.offSuccessSum), yards);
    offense.set(`${row.gameId}:${row.team}`, {
      offYardsN: yards,
      offExplosiveN: Math.floor(yards * (0.03 + random() * 0.08)),
      offSuccessYardsN: successYards,
      offSuccessYardsSum: Math.round(successYards * (9 + random() * 5) * 10) / 10,
    });
  }
  return rows.map((row) => {
    const own = offense.get(`${row.gameId}:${row.team}`)!;
    const other = offense.get(`${row.gameId}:${row.opponent}`)!;
    return {
      gameId: row.gameId, team: row.team, ...own,
      defYardsN: other.offYardsN, defExplosiveN: other.offExplosiveN,
      defSuccessYardsN: other.offSuccessYardsN, defSuccessYardsSum: other.offSuccessYardsSum,
    };
  });
}

export const chartsYardageFixture: TeamGameYardageRow[] = buildYardage(chartsGameRowsFixture, 20);

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
 * `current` V5 rating snapshots for weeks 0-3 of the 16 playing teams (Wyoming has none).
 * Tulane has no week 2 snapshot (a gap), and Georgia and Texas tie on every metric in
 * week 1. Ratings drift around 0.4, not zero, like the real scale.
 */
export function chartsRatingSnapshotsFixture(): RatingSnapshotRow[] {
  const random = lcg(31);
  const rows: RatingSnapshotRow[] = [];
  for (let week = 0; week <= 3; week++) {
    for (const team of PLAYING) {
      const offense = Number((0.4 + (random() - 0.5) * 1.6).toFixed(3));
      const defense = Number((0.4 + (random() - 0.5) * 1.6).toFixed(3));
      const offenseVariance = Number((0.09 - week * 0.015).toFixed(4));
      const defenseVariance = Number((0.08 - week * 0.012).toFixed(4));
      if (team === "Tulane" && week === 2) continue;
      rows.push({
        week, team, offenseRating: offense, offenseVariance, defenseRating: defense, defenseVariance,
        overallRating: (offense + defense) / 2, overallVariance: (offenseVariance + defenseVariance) / 4,
      });
    }
  }
  const georgia = rows.find((row) => row.week === 1 && row.team === "Georgia")!;
  const texas = rows.find((row) => row.week === 1 && row.team === "Texas")!;
  Object.assign(texas, { ...georgia, team: "Texas" });
  return rows;
}

export const chartsPossessionWeeksFixture = [3, 4];

/**
 * Opponent-adjusted possession rows for as_of_week 3 and 4, both measurements, for the
 * 16 playing teams. Missing roles: App State has no defense rows in window 3, and Boise
 * State's window-4 defense `ppp` has a null adjusted value. Defense values are allowed.
 */
export function chartsPossessionFixture(asOfWeek: number): PossessionRow[] {
  const random = lcg(40 + asOfWeek);
  const rows: PossessionRow[] = [];
  for (const team of PLAYING) {
    for (const role of ["offense", "defense"] as const) {
      if (asOfWeek === 3 && team === "App State" && role === "defense") continue;
      const possessions = Math.round((asOfWeek - 1) * (11 + random() * 3));
      for (const measurementId of ["ppp", "epa_per_possession"] as const) {
        const raw = measurementId === "ppp" ? 1.4 + random() * 1.4 : (random() - 0.5) * 1.6;
        const opponentAdjustment = Number(((random() - 0.5) * 0.2).toFixed(3));
        const missing = asOfWeek === 4 && team === "Boise State" && role === "defense" && measurementId === "ppp";
        rows.push({
          asOfWeek, team, role, measurementId,
          rawValue: Number(raw.toFixed(3)),
          adjustedValue: missing ? null : Number((raw - opponentAdjustment).toFixed(3)),
          opponentAdjustment: missing ? null : opponentAdjustment,
          adjustedRank: null, cohortSize: null,
          primaryExposure: possessions, games: asOfWeek - 1,
        });
      }
    }
  }
  // Stored minimum ranks per role and measurement: offense descending, defense ascending.
  for (const role of ["offense", "defense"] as const) {
    for (const measurementId of ["ppp", "epa_per_possession"] as const) {
      const cohort = rows.filter((row) => row.role === role && row.measurementId === measurementId && row.adjustedValue !== null);
      const sign = role === "offense" ? -1 : 1;
      for (const row of cohort) {
        row.adjustedRank = 1 + cohort.filter((other) => sign * other.adjustedValue! < sign * row.adjustedValue!).length;
        row.cohortSize = cohort.length;
      }
    }
  }
  return rows;
}

/**
 * A full Week 0 slate (69 games between every logo-bearing school) for export-width tests:
 * 140 + 30 * 69 = 2210 px wide.
 */
export function chartsSlateFixture(): { roster: RosterRow[]; rows: TeamGameRow[]; yardage: TeamGameYardageRow[] } {
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
  return { roster: names.map((team) => ({ team, conference: "Fixture" })), rows, yardage: buildYardage(rows, 70) };
}

/** Forty logo-bearing teams with distinct schedule effects, including a tie at each cut.
 * This fixture exercises the real top/bottom-15 browser layout without changing the
 * smaller fixtures used by the scatter and trajectory tests.
 */
export function chartsScheduleFixture() {
  const slate = chartsSlateFixture();
  const roster = [...slate.roster].sort((a, b) => a.team.localeCompare(b.team)).slice(0, 40);
  const teams = new Set(roster.map((row) => row.team));
  const rows = slate.rows.filter((row) => teams.has(row.team));
  const adjustedWeeks = [3, 4];
  const adjustedFor = (asOfWeek: number): AdjustedRow[] => roster.flatMap(({ team }, index) =>
    (["offense", "defense"] as const).map((role) => {
      // Adjacent teams at positions 15/16 and 25/26 tie: team name breaks each tie.
      const position = index === 15 ? 14 : index === 25 ? 24 : index;
      const effect = (19.5 - position) / 200;
      const opponentAdjustment = role === "offense" ? -effect : effect;
      const rawEpaPerPlay = (role === "offense" ? 0.12 : 0.08) + index / 2000;
      const venueCorrection = index % 2 === 0 ? 0.004 : -0.004;
      return {
        asOfWeek, team, role, rawEpaPerPlay, venueCorrection, opponentAdjustment,
        adjustedEpaPerPlay: rawEpaPerPlay - venueCorrection - opponentAdjustment,
        epaN: 140, games: 2, adjustedRank: index + 1, cohortSize: roster.length,
      };
    }),
  );
  return { roster, rows, yardage: slate.yardage.filter((row) => teams.has(row.team)), adjustedWeeks, adjustedFor };
}
