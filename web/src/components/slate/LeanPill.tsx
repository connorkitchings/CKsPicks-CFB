import clsx from "clsx";
import type { Lean } from "@/lib/slate";
import { edgeTone, leanDetail, phoneLean } from "@/lib/slate";
import { PhoneSwap } from "@/components/ui/PhoneSwap";
import { LeanMarker } from "./LeanMarker";

const LABEL = { spread: "Spread", total: "Total" } as const;

/**
 * One lean: bet type, direction marker, the pick with its edge in parentheses,
 * and one line under it with the model's prediction and the sportsbook the
 * (best available) line came from.
 */
export function LeanPill({ lean }: { lean: Lean; compact?: boolean }) {
  const sentence = leanDetail(lean);
  const phone = phoneLean(lean);
  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline gap-2">
        <span className="w-12 shrink-0 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          {LABEL[lean.kind]}
        </span>
        {/* The pick is never truncated: phones abbreviate a long team name, and anything still long wraps the edge to the next line. */}
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
          <LeanMarker lean={lean} />
          <span data-pick className="min-w-0 break-words text-sm font-semibold text-accent-ink">
            <PhoneSwap full={lean.pick} phone={phone.pick} />
          </span>
          <span className={clsx("whitespace-nowrap text-xs tabular-nums", edgeTone(lean.edge, lean.kind))} title="Edge: points the model differs from the market">
            ({lean.edge.toFixed(1)})
          </span>
        </span>
      </div>
      {sentence && (
        <p
          className="truncate pl-[3.75rem] text-xs text-ink-muted max-[380px]:overflow-visible max-[380px]:whitespace-normal"
          title={lean.source ? `${sentence} (best available line for the model's side)` : sentence}
        >
          <PhoneSwap full={sentence} phone={leanDetail(phone) ?? sentence} />
        </p>
      )}
    </div>
  );
}
