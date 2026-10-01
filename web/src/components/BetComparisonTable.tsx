import { clsx } from "clsx";
import { signedSpread } from "@/lib/betting-format";

const SPREAD_EDGE_LOW = 3;
const SPREAD_EDGE_HIGH = 8;
const TOTAL_EDGE_LOW = 2;
const TOTAL_EDGE_HIGH = 7;

function edgeTone(edge: number, target: "spread" | "total"): string {
  const magnitude = Math.abs(edge);
  const [lowThreshold, highThreshold] =
    target === "spread"
      ? [SPREAD_EDGE_LOW, SPREAD_EDGE_HIGH]
      : [TOTAL_EDGE_LOW, TOTAL_EDGE_HIGH];
  if (magnitude < lowThreshold) return "edge-low";
  if (magnitude <= highThreshold) return "edge-medium";
  return "edge-high";
}

function EdgeNote({ edge, target }: { edge: number | null; target: "spread" | "total" }) {
  if (edge === null) return null;
  const note = `(${signedSpread(edge)})`;
  return (
    <span
      className={clsx("ml-1 font-medium", edgeTone(edge, target))}
      title="Model minus market"
      aria-label={`Model minus market ${note}`}
    >
      {note}
    </span>
  );
}

function ResultCell({ result }: { result: "win" | "loss" | "push" | null }) {
  if (result === null) {
    return <span className="text-ink-faint">—</span>;
  }
  return (
    <span
      className={clsx(
        "inline-block rounded px-1.5 py-0.5 text-[11px] font-medium",
        result === "win" && "bg-win-soft text-win",
        result === "loss" && "bg-loss-soft text-loss",
        result === "push" && "bg-surface-inset text-ink-muted",
      )}
    >
      {result === "win" ? "Win" : result === "loss" ? "Loss" : "Push"}
    </span>
  );
}

/**
 * Responsive betting comparison table consolidating desktop and mobile layouts.
 * Renders a single semantic table in the DOM, adapting responsive columns and
 * stacked result badges via CSS breakpoints.
 */
export function BetComparisonTable({
  marketSpread,
  modelSpread,
  spreadEdge,
  spreadBet,
  spreadResult,
  totalLine,
  predictedTotal,
  totalEdge,
  totalBet,
  totalResult,
  showBetResult = true,
}: {
  marketSpread: string;
  modelSpread: string;
  spreadEdge: number | null;
  spreadBet: string | null;
  spreadResult: "win" | "loss" | "push" | null;
  totalLine: number | null;
  predictedTotal: number | null;
  totalEdge: number | null;
  totalBet: string | null;
  totalResult: "win" | "loss" | "push" | null;
  showBetResult?: boolean;
}) {
  return (
    <div className="mt-3">
      <table
        className="w-full tabular-nums text-[11px] sm:text-xs"
        aria-label="Market and model comparison"
      >
        <thead>
          <tr>
            <th
              scope="col"
              className="w-[16%] py-1 text-left text-[10px] font-medium uppercase tracking-wide text-ink-faint sm:w-auto"
            >
              <span className="sr-only">Bet type</span>
            </th>
            <th
              scope="col"
              className="py-1 pl-2 text-right text-[10px] font-medium uppercase tracking-wide text-ink-faint"
            >
              Market
            </th>
            <th
              scope="col"
              className="py-1 pl-2 text-right text-[10px] font-medium uppercase tracking-wide text-ink-faint"
            >
              Model
            </th>
            <th
              scope="col"
              className="py-1 pl-2 text-right text-[10px] font-medium uppercase tracking-wide text-ink-faint"
            >
              <span className="sm:hidden">Bet</span>
              <span className="hidden sm:inline">Model Bet</span>
            </th>
            {showBetResult && (
              <th
                scope="col"
                className="hidden py-1 pl-2 text-right text-[10px] font-medium uppercase tracking-wide text-ink-faint sm:table-cell"
              >
                Bet Result
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {/* Spread Row */}
          <tr className="border-t border-line">
            <th
              scope="row"
              className="py-1.5 pr-2 text-left font-medium text-ink-muted"
            >
              Spread
            </th>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums text-ink">
              {marketSpread}
            </td>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums text-ink">
              {modelSpread}
              <EdgeNote edge={spreadEdge} target="spread" />
            </td>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums">
              {spreadBet ? (
                <span className="font-medium text-accent-ink">{spreadBet}</span>
              ) : (
                <span className="text-ink-faint">No lean</span>
              )}
              {showBetResult && spreadResult && (
                <div className="mt-1 sm:hidden">
                  <ResultCell result={spreadResult} />
                </div>
              )}
            </td>
            {showBetResult && (
              <td className="hidden py-1.5 pl-2 text-right sm:table-cell">
                <ResultCell result={spreadResult} />
              </td>
            )}
          </tr>

          {/* Total Row */}
          <tr className="border-y border-line">
            <th
              scope="row"
              className="py-1.5 pr-2 text-left font-medium text-ink-muted"
            >
              Total
            </th>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums text-ink">
              {totalLine === null ? "—" : totalLine.toFixed(1)}
            </td>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums text-ink">
              {predictedTotal === null ? "—" : predictedTotal.toFixed(1)}
              <EdgeNote edge={totalEdge} target="total" />
            </td>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums">
              {totalBet ? (
                <span className="font-medium text-accent-ink">{totalBet}</span>
              ) : (
                <span className="text-ink-faint">No lean</span>
              )}
              {showBetResult && totalResult && (
                <div className="mt-1 sm:hidden">
                  <ResultCell result={totalResult} />
                </div>
              )}
            </td>
            {showBetResult && (
              <td className="hidden py-1.5 pl-2 text-right sm:table-cell">
                <ResultCell result={totalResult} />
              </td>
            )}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
