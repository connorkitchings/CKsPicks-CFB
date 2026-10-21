"use client";

import { useSyncExternalStore } from "react";
import type { Game } from "@/lib/queries";
import { isFinal } from "@/lib/slate";
import { MarketGameCard } from "./MarketGameCard";
import { PredictionGameCard } from "./PredictionGameCard";
import { SlateGameRow } from "./SlateGameRow";
import type { SlateLayout } from "./SlateToolbar";

function subscribe(callback: () => void) {
  const media = window.matchMedia("(min-width: 640px)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}
const desktopSnapshot = () => window.matchMedia("(min-width: 640px)").matches;
const serverSnapshot = () => false;

/** Keep one copy of each game/anchor while adapting a desktop list selection to phone cards. */
export function SlateGameList({
  games,
  view,
}: {
  games: Game[];
  view: SlateLayout;
}) {
  const desktop = useSyncExternalStore(subscribe, desktopSnapshot, serverSnapshot);
  const list = view === "list" && desktop;
  return (
    <ul
      data-layout={list ? "list" : "grid"}
      data-card={list ? "" : undefined}
      className={list ? "overflow-hidden rounded-xl border border-line bg-surface-card shadow-sm" : "grid gap-3 md:grid-cols-2"}
    >
      {games.map((game) => list ? (
        <SlateGameRow key={game.gameId} game={game} />
      ) : game.publicationMode === "market" ? (
        <MarketGameCard key={game.gameId} game={game} showBetResult={isFinal(game)} />
      ) : (
        <PredictionGameCard key={game.gameId} game={game} results={isFinal(game)} />
      ))}
    </ul>
  );
}
