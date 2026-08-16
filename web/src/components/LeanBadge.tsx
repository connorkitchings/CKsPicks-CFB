function signedSpread(n: number): string {
  return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
}

/**
 * Spread lean for the game card's right rail: the team the model backs and
 * the market line it would take, with the edge magnitude quiet beneath.
 * Direction is carried by team identity, not color — the accent hue marks
 * this as the card's single actionable element.
 */
export function LeanBadge({
  lean,
  edge,
  homeTeam,
  awayTeam,
  homeLine,
}: {
  lean: "home" | "away" | null;
  edge: number | null;
  homeTeam: string;
  awayTeam: string;
  homeLine: number | null;
}) {
  if (lean === null) {
    return <span className="text-xs text-ink-faint">No spread lean</span>;
  }

  const team = lean === "home" ? homeTeam : awayTeam;
  const line =
    homeLine === null ? null : lean === "home" ? homeLine : -homeLine;

  return (
    <div className="flex flex-col sm:items-end">
      <span className="text-sm font-semibold text-accent-ink">
        {team}
        {line !== null && (
          <span className="ml-1 font-mono tabular-nums">
            {signedSpread(line)}
          </span>
        )}
      </span>
      {edge !== null && (
        <span className="font-mono text-[11px] tabular-nums text-ink-faint">
          edge +{edge.toFixed(1)}
        </span>
      )}
    </div>
  );
}

/** Over/under lean for the right rail; neutral, direction carried by arrow. */
export function TotalLeanChip({
  lean,
  edge,
  totalLine,
}: {
  lean: "over" | "under" | null;
  edge: number | null;
  totalLine: number | null;
}) {
  if (lean === null || totalLine === null) {
    return <span className="text-xs text-ink-faint">No total lean</span>;
  }
  const isOver = lean === "over";
  return (
    <div className="flex flex-col sm:items-end">
      <span className="text-sm font-medium text-ink">
        <span aria-hidden>{isOver ? "↑" : "↓"}</span> {isOver ? "Over" : "Under"}{" "}
        <span className="font-mono tabular-nums">{totalLine.toFixed(1)}</span>
      </span>
      {edge !== null && (
        <span className="font-mono text-[11px] tabular-nums text-ink-faint">
          edge +{edge.toFixed(1)}
        </span>
      )}
    </div>
  );
}
