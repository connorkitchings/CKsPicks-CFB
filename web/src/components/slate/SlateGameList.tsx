"use client";

import { useSyncExternalStore } from "react";
import type { Game } from "@/lib/queries";
import { SlateGameCard } from "./SlateGameCard";
import { ResultGameCard } from "./ResultGameCard";
import { SlateGameRow } from "./SlateGameRow";
import { ResultGameRow } from "./ResultGameRow";
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
  mode,
  showBetResult,
}: {
  games: Game[];
  view: SlateLayout;
  mode: "picks" | "results";
  showBetResult: boolean;
}) {
  const desktop = useSyncExternalStore(subscribe, desktopSnapshot, serverSnapshot);
  const list = view === "list" && desktop;
  const Card = mode === "results" ? ResultGameCard : SlateGameCard;
  const Row = mode === "results" ? ResultGameRow : SlateGameRow;
  return (
    <ul
      data-layout={list ? "list" : "grid"}
      data-card={list ? "" : undefined}
      className={list ? "overflow-hidden rounded-xl border border-line bg-surface-card shadow-sm" : "grid gap-3 md:grid-cols-2"}
    >
      {games.map((game) => list ? (
        <Row key={game.gameId} game={game} showBetResult={showBetResult} />
      ) : (
        <Card key={game.gameId} game={game} showBetResult={showBetResult} />
      ))}
    </ul>
  );
}
