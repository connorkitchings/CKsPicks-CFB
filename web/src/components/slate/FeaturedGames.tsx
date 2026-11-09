"use client";

import { useState } from "react";
import { ResponsiveDisclosure } from "@/components/ui/ResponsiveDisclosure";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { Game } from "@/lib/queries";
import { topLeans, underdogPicks, type LeanKind, type Tally } from "@/lib/slate";
import { edgesRecordText, TopLeansBody } from "./TopLeans";
import { underdogRecordText, UnderdogPicksBody } from "./UnderdogPicks";

type View = "edges" | "underdogs";

const VIEW_OPTIONS = [
  { value: "edges", label: "Biggest edges" },
  { value: "underdogs", label: "Underdog picks" },
] as const;

/**
 * One card for the model's featured games. Biggest edges is the default view on every load; a
 * control flips to Underdog picks, but only when both views have content. Collapsed on phones,
 * open from `sm:`.
 */
export function FeaturedGames({
  games,
  edgesRecord,
  underdogRecord,
  season,
}: {
  games: Game[];
  /** Season record over each scored week's top spread/total leans. */
  edgesRecord?: Tally | null;
  /** Season straight-up record over every underdog pick in each scored week. */
  underdogRecord?: Tally | null;
  season: number;
}) {
  const [view, setView] = useState<View>("edges");
  const [tab, setTab] = useState<LeanKind>("spread");

  const picks = underdogPicks(games);
  const hasEdges = topLeans(games, "spread", 5).length > 0 || topLeans(games, "total", 5).length > 0;
  const hasUnderdogs = picks.length > 0;
  if (!hasEdges && !hasUnderdogs) return null;

  const canFlip = hasEdges && hasUnderdogs;
  // Without both views there is nothing to flip to, whatever was selected before the games changed.
  const active: View = canFlip ? view : hasEdges ? "edges" : "underdogs";
  const label = active === "edges" ? "Biggest edges" : "Underdog picks";
  const recordText = active === "edges" ? edgesRecordText(edgesRecord, season) : underdogRecordText(underdogRecord, season);

  return (
    <section aria-label="Biggest edges">
      <ResponsiveDisclosure
        title={active === "edges" ? "Biggest edges" : "Underdogs"}
        heading={
          <span>
            {label}
            {recordText && <span className="ml-2 text-xs font-normal text-ink-muted">{recordText}</span>}
          </span>
        }
      >
        {canFlip && (
          <div className="mb-3">
            <SegmentedControl label="Featured games view" value={active} onChange={setView} options={VIEW_OPTIONS} fill />
          </div>
        )}
        {active === "edges" ? (
          <TopLeansBody games={games} recordText={recordText} tab={tab} onTabChange={setTab} />
        ) : (
          <UnderdogPicksBody picks={picks} recordText={recordText} />
        )}
      </ResponsiveDisclosure>
    </section>
  );
}
