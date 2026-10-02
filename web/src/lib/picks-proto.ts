import type { Game, PredictionGame } from "./queries.ts";
import { withGameNameAliases } from "./rating-names.ts";
import {
  marketSpreadView,
  modelSpreadView,
  signedSpread,
  spreadEdge,
  totalEdge,
} from "./betting-format.ts";

/** Break-even win rate at -110 odds, the project's primary success metric. */
export const BREAK_EVEN_PCT = 52.4;

export type LeanKind = "spread" | "total";

/** "Los Angeles, CA"; just the city or state when only one is known; "" when neither. */
export function venueLabel(city?: string | null, state?: string | null): string {
  const c = city?.trim() ?? "";
  const s = state?.trim() ?? "";
  return c && s ? `${c}, ${s}` : c || s;
}

const BOOK_NAMES: Record<string, string> = {
  draftkings: "DraftKings",
  fanduel: "FanDuel",
  betmgm: "BetMGM",
  caesars: "Caesars",
  williamhill_us: "Caesars",
  bovada: "Bovada",
  espnbet: "ESPN Bet",
  "espn bet": "ESPN Bet",
  betrivers: "BetRivers",
  pointsbet: "PointsBet",
  mybookieag: "MyBookie",
  betonlineag: "BetOnline",
  fanatics: "Fanatics",
  hardrockbet: "Hard Rock Bet",
};

/**
 * Display name for a quote provider. Known sportsbook keys are mapped; anything
 * else is shown as given, with underscores turned into spaces. Null/blank -> null.
 */
export function bookName(provider: string | null | undefined): string | null {
  const raw = provider?.trim();
  if (!raw) return null;
  const known = BOOK_NAMES[raw.toLowerCase()];
  if (known) return known;
  const spaced = raw.replace(/_/g, " ");
  return spaced === spaced.toLowerCase() ? spaced.replace(/\b\w/g, (c) => c.toUpperCase()) : spaced;
}

/** [low, high] edge thresholds (points); mirrors BetComparisonTable. */
const EDGE_THRESHOLDS: Record<LeanKind, readonly [number, number]> = {
  spread: [3, 8],
  total: [2, 7],
};

/** 0 = no edge, 1 = small, 2 = medium, 3 = large. */
export function edgeTier(kind: LeanKind, edge: number | null): 0 | 1 | 2 | 3 {
  if (edge === null || !Number.isFinite(edge) || edge <= 0) return 0;
  const [low, high] = EDGE_THRESHOLDS[kind];
  if (edge <= low) return 1;
  if (edge <= high) return 2;
  return 3;
}

export type Lean = {
  kind: LeanKind;
  /** Display text, e.g. "New Mexico State -2.5" or "Under 57.5". */
  pick: string;
  /** Which side the lean takes. */
  dir: "home" | "away" | "over" | "under";
  /** Team the spread lean backs; null for totals. */
  team: string | null;
  /** What the model says on the same scale: "wins by 7.6" / "54.1". */
  model: string | null;
  /** Sportsbook behind the line (display name), when the run recorded one. */
  source: string | null;
  /** Edge in points on the pick side; always positive. */
  edge: number;
  tier: 1 | 2 | 3;
};

/** Model margin from the leaned team's side: "wins by 7.6" / "loses by 1.2". */
function modelMarginText(margin: number | null): string | null {
  if (margin === null) return null;
  return margin >= 0 ? `wins by ${margin.toFixed(1)}` : `loses by ${Math.abs(margin).toFixed(1)}`;
}

export function leanFor(game: Game, kind: LeanKind): Lean | null {
  if (game.publicationMode !== "predictions") return null;
  if (kind === "spread") {
    if (game.spreadLean === null || game.homeTeamSpreadLine === null) return null;
    const line =
      game.spreadLean === "home" ? game.homeTeamSpreadLine : -game.homeTeamSpreadLine;
    const team = game.spreadLean === "home" ? game.homeTeam : game.awayTeam;
    const edge = Math.abs(
      game.edgeSpread ??
        spreadEdge(
          modelSpreadView(game.homeTeam, game.awayTeam, game.predictedSpread),
          marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine),
        ) ??
        0,
    );
    const margin =
      game.predictedSpread === null
        ? null
        : game.spreadLean === "home"
          ? game.predictedSpread
          : -game.predictedSpread;
    return {
      kind,
      pick: `${team} ${line === 0 ? "PK" : signedSpread(line)}`,
      dir: game.spreadLean,
      team,
      model: modelMarginText(margin),
      source: bookName(game.spreadSource),
      edge,
      tier: Math.max(1, edgeTier(kind, edge)) as 1 | 2 | 3,
    };
  }
  if (game.totalLean === null || game.totalLine === null) return null;
  const edge = Math.abs(
    game.edgeTotal ?? totalEdge(game.predictedTotal, game.totalLine) ?? 0,
  );
  const over = game.totalLean === "over";
  return {
    kind,
    pick: `${over ? "Over" : "Under"} ${game.totalLine.toFixed(1)}`,
    dir: game.totalLean,
    team: null,
    model: game.predictedTotal === null ? null : game.predictedTotal.toFixed(1),
    source: bookName(game.totalSource),
    edge,
    tier: Math.max(1, edgeTier(kind, edge)) as 1 | 2 | 3,
  };
}

export function hasLean(game: Game): boolean {
  return leanFor(game, "spread") !== null || leanFor(game, "total") !== null;
}

export function isFinal(game: Game): boolean {
  return game.homePoints !== null && game.awayPoints !== null;
}

/** "model: wins by 7.6 · best line: DraftKings"; each part appears only when known. */
export function leanDetail(lean: Lean): string | null {
  const parts = [
    lean.model ? `model: ${lean.model}` : null,
    lean.source ? `best line: ${lean.source}` : null,
  ].filter((p): p is string => p !== null);
  return parts.length > 0 ? parts.join(" · ") : null;
}

export type TopLean = Lean & { game: PredictionGame };

/** Largest edges among games that have not finished, one list per bet type. */
export function topLeans(games: Game[], kind: LeanKind, n: number): TopLean[] {
  const out: TopLean[] = [];
  for (const game of games) {
    if (game.publicationMode !== "predictions" || isFinal(game)) continue;
    const lean = leanFor(game, kind);
    if (lean) out.push({ ...lean, game });
  }
  out.sort((a, b) => b.edge - a.edge || a.game.startDate.getTime() - b.game.startDate.getTime());
  return out.slice(0, n);
}

export type SortKey = "kickoff" | "bestEdge" | "spreadEdge" | "totalEdge";

function edgeOf(game: Game, kind: LeanKind): number | null {
  return leanFor(game, kind)?.edge ?? null;
}

/** Biggest edge first; games with no lean sink to the bottom in kickoff order. */
export function sortGames(games: Game[], sort: SortKey): Game[] {
  const rows = [...games];
  const byKickoff = (a: Game, b: Game) => a.startDate.getTime() - b.startDate.getTime();
  if (sort === "kickoff") return rows.sort(byKickoff);
  const score = (g: Game): number | null => {
    if (sort === "spreadEdge") return edgeOf(g, "spread");
    if (sort === "totalEdge") return edgeOf(g, "total");
    const s = edgeOf(g, "spread");
    const t = edgeOf(g, "total");
    return s === null && t === null ? null : Math.max(s ?? 0, t ?? 0);
  };
  return rows.sort((a, b) => {
    const sa = score(a);
    const sb = score(b);
    if (sa === null && sb === null) return byKickoff(a, b);
    if (sa === null) return 1;
    if (sb === null) return -1;
    return sb - sa || byKickoff(a, b);
  });
}

/** Win rate over decisive games as a number (pushes excluded); null if none. */
export function winRatePct(win: number, loss: number): number | null {
  const decided = win + loss;
  return decided === 0 ? null : (100 * win) / decided;
}

/** 1-based overall rank by rating, best first. */
export function overallRanks(
  ratings: ReadonlyArray<{ team: string; overallRating: number }>,
): Record<string, number> {
  const ranks: Record<string, number> = {};
  [...ratings]
    .sort((a, b) => b.overallRating - a.overallRating)
    .forEach((r, i) => {
      ranks[r.team] = i + 1;
    });
  return withGameNameAliases(ranks);
}

export type Grade = "win" | "loss" | "push";

/** The graded outcome the pipeline recorded for this lean, if any. */
export function resultFor(game: Game, kind: LeanKind): Grade | null {
  if (game.publicationMode !== "predictions") return null;
  return kind === "spread" ? game.spreadResult : game.totalResult;
}

/**
 * Points by which the lean side covered (positive) or missed (negative) the
 * market number, from the final score. Null until the game is final or when
 * there is no lean/line.
 */
export function coverMargin(game: Game, kind: LeanKind): number | null {
  if (game.publicationMode !== "predictions" || !isFinal(game)) return null;
  const home = game.homePoints as number;
  const away = game.awayPoints as number;
  if (kind === "spread") {
    if (game.spreadLean === null || game.homeTeamSpreadLine === null) return null;
    const homeCover = home - away + game.homeTeamSpreadLine;
    return game.spreadLean === "home" ? homeCover : -homeCover;
  }
  if (game.totalLean === null || game.totalLine === null) return null;
  const actual = home + away;
  return game.totalLean === "over" ? actual - game.totalLine : game.totalLine - actual;
}

export function gradeFromMargin(margin: number | null): Grade | null {
  if (margin === null) return null;
  return margin > 0 ? "win" : margin < 0 ? "loss" : "push";
}

export type Tally = { win: number; loss: number; push: number };

/** Spread and total records for one slate, from the recorded grades. */
export function weekRecord(games: Game[]): { spread: Tally; total: Tally } {
  const out = {
    spread: { win: 0, loss: 0, push: 0 },
    total: { win: 0, loss: 0, push: 0 },
  };
  for (const game of games) {
    for (const kind of ["spread", "total"] as const) {
      const r = resultFor(game, kind);
      if (r) out[kind][r] += 1;
    }
  }
  return out;
}

export type GradedLean = Lean & {
  game: PredictionGame;
  grade: Grade;
  /** Positive when the lean covered; see coverMargin. */
  cover: number | null;
};

/** Graded leans with the given outcome, largest edge first. */
export function topResults(games: Game[], grade: "win" | "loss", n: number): GradedLean[] {
  const out: GradedLean[] = [];
  for (const game of games) {
    if (game.publicationMode !== "predictions") continue;
    for (const kind of ["spread", "total"] as const) {
      const lean = leanFor(game, kind);
      if (lean && resultFor(game, kind) === grade) {
        out.push({ ...lean, game, grade, cover: coverMargin(game, kind) });
      }
    }
  }
  out.sort((a, b) => b.edge - a.edge || a.game.startDate.getTime() - b.game.startDate.getTime());
  return out.slice(0, n);
}

export type ResultFilter = "all" | "win" | "loss" | "push" | "none";

/** Whether a game belongs under a result filter (any graded lean matches). */
export function matchesResult(game: Game, filter: ResultFilter): boolean {
  if (filter === "all") return true;
  if (filter === "none") return !hasLean(game);
  return (["spread", "total"] as const).some((k) => resultFor(game, k) === filter);
}

export type ResultSort = "kickoff" | "bestEdge" | "bestResult" | "worstResult";

function coverScore(game: Game, pick: "max" | "min"): number | null {
  const values = (["spread", "total"] as const)
    .map((k) => coverMargin(game, k))
    .filter((v): v is number => v !== null);
  if (values.length === 0) return null;
  return pick === "max" ? Math.max(...values) : Math.min(...values);
}

/** Result-oriented sort; games with nothing to rank sink in kickoff order. */
export function sortResults(games: Game[], sort: ResultSort): Game[] {
  const byKickoff = (a: Game, b: Game) => a.startDate.getTime() - b.startDate.getTime();
  if (sort === "kickoff") return [...games].sort(byKickoff);
  if (sort === "bestEdge") return sortGames(games, "bestEdge");
  const score = (g: Game) => coverScore(g, sort === "bestResult" ? "max" : "min");
  return [...games].sort((a, b) => {
    const sa = score(a);
    const sb = score(b);
    if (sa === null && sb === null) return byKickoff(a, b);
    if (sa === null) return 1;
    if (sb === null) return -1;
    return (sort === "bestResult" ? sb - sa : sa - sb) || byKickoff(a, b);
  });
}

/** Season-level comparison window: the bar spans +/- this many points of win rate. */
export const BAR_RANGE_PTS = 15;

/**
 * Win rate vs the break-even rate. `fill` is signed in [-1, 1] on a fixed scale
 * (BAR_RANGE_PTS each side) so bars are comparable across records.
 */
export function breakEvenDelta(
  win: number,
  loss: number,
): { rate: number | null; delta: number | null; fill: number; decided: number } {
  const rate = winRatePct(win, loss);
  if (rate === null) return { rate: null, delta: null, fill: 0, decided: 0 };
  const delta = rate - BREAK_EVEN_PCT;
  const fill = Math.max(-1, Math.min(1, delta / BAR_RANGE_PTS));
  return { rate, delta, fill, decided: win + loss };
}

/** Actual margin from the named team's side: "won by 7" / "lost by 3" / "tied". */
export function finalMarginText(game: Game, team: string): string | null {
  if (game.publicationMode !== "predictions" || !isFinal(game)) return null;
  const home = game.homePoints as number;
  const away = game.awayPoints as number;
  const margin = team === game.homeTeam ? home - away : away - home;
  if (margin === 0) return "tied";
  return `${margin > 0 ? "won" : "lost"} by ${Math.abs(margin)}`;
}
