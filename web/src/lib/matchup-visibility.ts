import type { Game } from "./queries.ts";
import type { PublicationMode } from "./publication.ts";

/**
 * Public-safe projection of one game for the matchup page. Model fields exist
 * only when the server publication mode is "predictions" AND the game came from
 * the explicitly selected public run (a prediction-bearing Game). Anything else
 * collapses to market-only so an unselected or replayed run can never leak.
 */
export type MatchupPublicView = {
  publicationMode: PublicationMode;
  systemName: string | null;
  modelId: string | null;
  marketSpreadLine: number | null;
  marketTotal: number | null;
  predictedSpread: number | null;
  predictedTotal: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
  highConfidence: boolean;
  homePoints: number | null;
  awayPoints: number | null;
};

export function selectMatchupView(
  game: Game | undefined,
  mode: PublicationMode,
): MatchupPublicView | null {
  if (!game) return null;
  const base = {
    marketSpreadLine: game.homeTeamSpreadLine,
    marketTotal: game.totalLine,
    homePoints: game.homePoints,
    awayPoints: game.awayPoints,
  };
  if (mode !== "predictions" || game.publicationMode !== "predictions") {
    return {
      ...base,
      publicationMode: "market",
      systemName: null,
      modelId: null,
      predictedSpread: null,
      predictedTotal: null,
      spreadLean: null,
      totalLean: null,
      edgeSpread: null,
      edgeTotal: null,
      highConfidence: false,
    };
  }
  return {
    ...base,
    publicationMode: "predictions",
    systemName: game.systemName,
    modelId: game.modelId,
    predictedSpread: game.predictedSpread,
    predictedTotal: game.predictedTotal,
    spreadLean: game.spreadLean,
    totalLean: game.totalLean,
    edgeSpread: game.edgeSpread,
    edgeTotal: game.edgeTotal,
    highConfidence: Boolean(game.highConfidence),
  };
}
