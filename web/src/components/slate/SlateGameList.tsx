"use client";

import type { Game } from "@/lib/queries";
import { isFinal } from "@/lib/team-games";
import { useIsPhone } from "@/lib/use-is-phone";
import { MarketGameCard } from "./MarketGameCard";
import { PredictionGameCard } from "./PredictionGameCard";
import { SlateGameRow } from "./SlateGameRow";
import type { SlateLayout } from "./SlateToolbar";

/** One copy of each game/anchor in either layout; the list is compact rows on phones. */
export function SlateGameList({
  games,
  view,
  now,
}: {
  games: Game[];
  view: SlateLayout;
  now: Date;
}) {
  const phone = useIsPhone(true); // the server renders the phone layout
  const list = view === "list";
  return (
    <ul
      data-layout={list ? "list" : "grid"}
      data-card={list ? "" : undefined}
      className={list ? "overflow-hidden rounded-xl border border-line bg-surface-card shadow-sm" : "grid gap-3 md:grid-cols-2"}
    >
      {games.map((game) => list ? (
        <SlateGameRow key={game.gameId} game={game} now={now} compact={phone} />
      ) : game.publicationMode === "market" ? (
        <MarketGameCard key={game.gameId} game={game} showBetResult={isFinal(game)} now={now} />
      ) : (
        <PredictionGameCard key={game.gameId} game={game} results={isFinal(game)} now={now} />
      ))}
    </ul>
  );
}
