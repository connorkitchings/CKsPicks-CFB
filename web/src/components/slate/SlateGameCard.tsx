import type { Game } from "@/lib/queries";
import { MarketGameCard } from "./MarketGameCard";
import { PredictionGameCard } from "./PredictionGameCard";

export function SlateGameCard({
  game,
  showBetResult = true,
}: {
  game: Game;
  showBetResult?: boolean;
}) {
  if (game.publicationMode === "market") {
    return <MarketGameCard game={game} showBetResult={showBetResult} />;
  }
  return <PredictionGameCard game={game} results={false} />;
}
