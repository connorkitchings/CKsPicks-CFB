import { deriveSpreadView, deriveTotalView } from "./publication.ts";

export type TargetSelectionOverlay = {
  point: number;
  side: string;
  edge: number | null;
  source: string | null;
};

export type GameSelectionsOverlay = {
  spread?: TargetSelectionOverlay;
  total?: TargetSelectionOverlay;
};

type OverlayRow = {
  homeTeamSpreadLine: number | null;
  predictedSpread: number | null;
  spreadLean: "home" | "away" | null;
  edgeSpread: number | null;
  totalLine: number | null;
  predictedTotal: number | null;
  totalLean: "over" | "under" | null;
  edgeTotal: number | null;
};

/**
 * Apply the selected market quote to a prediction row. The selection supplies
 * the line and source. When the prediction has a lean, the selection also
 * supplies the side and edge.
 *
 * A prediction with a null lean (the frozen Week 5 run withheld leans under
 * the old 1.0-point "No Bet" threshold) gets its lean derived from the frozen
 * prediction and the quoted line, exactly as the grade backfill does. The
 * publisher writes a default side ("home"/"over", edge 0.0) for those rows;
 * showing that would present a side the model did not pick.
 */
export function overlaySelection<Row extends OverlayRow>(
  row: Row,
  sel: GameSelectionsOverlay | undefined,
): Row & { spreadSource: string | null; totalSource: string | null } {
  const homeTeamSpreadLine = sel?.spread?.point ?? row.homeTeamSpreadLine;
  const totalLine = sel?.total?.point ?? row.totalLine;

  let spreadLean = row.spreadLean;
  let edgeSpread = row.edgeSpread;
  if (row.spreadLean === null) {
    const view = deriveSpreadView(row.predictedSpread, homeTeamSpreadLine);
    spreadLean = view.lean;
    edgeSpread = row.edgeSpread ?? view.edge;
  } else {
    spreadLean = (sel?.spread?.side as "home" | "away" | undefined) ?? row.spreadLean;
    edgeSpread = sel?.spread?.edge ?? row.edgeSpread;
  }

  let totalLean = row.totalLean;
  let edgeTotal = row.edgeTotal;
  if (row.totalLean === null) {
    const view = deriveTotalView(row.predictedTotal, totalLine);
    totalLean = view.lean;
    edgeTotal = row.edgeTotal ?? view.edge;
  } else {
    totalLean = (sel?.total?.side as "over" | "under" | undefined) ?? row.totalLean;
    edgeTotal = sel?.total?.edge ?? row.edgeTotal;
  }

  return {
    ...row,
    homeTeamSpreadLine,
    spreadLean,
    edgeSpread,
    totalLine,
    totalLean,
    edgeTotal,
    spreadSource: sel?.spread?.source ?? null,
    totalSource: sel?.total?.source ?? null,
  };
}
