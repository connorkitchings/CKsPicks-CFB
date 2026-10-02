import { clsx } from "clsx";
import { signedSpread } from "@/lib/betting-format";
import { edgeTone, type LeanKind } from "@/lib/slate";

/**
 * Parenthesized model-minus-market gap with the shared edge tone.
 * Preserved from the retired comparison table; the lean sentences use the
 * tone class directly on their edge number.
 */
export function EdgeNote({ edge, target }: { edge: number | null; target: LeanKind }) {
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
