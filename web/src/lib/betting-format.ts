/**
 * Pure spread/total formatting and view logic shared by the game cards.
 * Kept free of JSX so the home/away sign-flipping math is directly unit
 * testable (see betting-format.test.ts) instead of only covered through
 * rendered-output assertions.
 */

export function signedSpread(n: number): string {
  return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
}

/** Favorite-relative spread view: the team the number favors plus its line. */
export type SpreadView = { team: string; line: number } | "PK" | null;

/** Market line is the home team's spread: -home favorite, +home dog. */
export function marketSpreadView(
  homeTeam: string,
  awayTeam: string,
  homeLine: number | null,
): SpreadView {
  if (homeLine === null) return null;
  if (homeLine === 0) return "PK";
  return homeLine < 0
    ? { team: homeTeam, line: homeLine }
    : { team: awayTeam, line: -homeLine };
}

/** predictedSpread is the home margin (+home wins); flip to favorite-relative. */
export function modelSpreadView(
  homeTeam: string,
  awayTeam: string,
  predictedSpread: number | null,
): SpreadView {
  if (predictedSpread === null) return null;
  if (predictedSpread === 0) return "PK";
  return predictedSpread > 0
    ? { team: homeTeam, line: -predictedSpread }
    : { team: awayTeam, line: predictedSpread };
}

export function spreadLabel(view: SpreadView): string {
  if (view === null) return "—";
  if (view === "PK") return "PK";
  return `${view.team} ${signedSpread(view.line)}`;
}

/** Signed difference between the displayed model and market spread numbers. */
export function spreadEdge(model: SpreadView, market: SpreadView): number | null {
  if (
    model === null ||
    market === null ||
    model === "PK" ||
    market === "PK"
  ) {
    return null;
  }
  return model.line - market.line;
}

/** Signed difference between the model and market totals. */
export function totalEdge(
  predictedTotal: number | null,
  totalLine: number | null,
): number | null {
  if (predictedTotal === null || totalLine === null) return null;
  return predictedTotal - totalLine;
}

/** The bet the model would place: the leaned team and the line it would take. */
export function spreadBetLabel(
  homeTeam: string,
  awayTeam: string,
  lean: "home" | "away" | null,
  homeLine: number | null,
): string | null {
  if (lean === null || homeLine === null) return null;
  return lean === "home"
    ? `${homeTeam} ${signedSpread(homeLine)}`
    : `${awayTeam} ${signedSpread(-homeLine)}`;
}

export function totalBetLabel(
  lean: "over" | "under" | null,
  totalLine: number | null,
): string | null {
  if (lean === null || totalLine === null) return null;
  return `${lean === "over" ? "↑ Over" : "↓ Under"} ${totalLine.toFixed(1)}`;
}
