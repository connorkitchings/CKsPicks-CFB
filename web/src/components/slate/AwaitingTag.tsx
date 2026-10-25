import clsx from "clsx";
import { gameState } from "@/lib/slate";

type TaggedGame = Parameters<typeof gameState>[0];

/** A muted "Awaiting result" tag for a game that has kicked off but has no score yet; nothing otherwise. */
export function AwaitingTag({ game, now, className }: { game: TaggedGame; now: Date; className?: string }) {
  if (gameState(game, now) !== "awaiting") return null;
  return (
    <span
      data-testid="awaiting-tag"
      className={clsx("inline-block rounded bg-surface-inset px-1.5 py-0.5 text-xs font-semibold text-ink-muted", className)}
    >
      Awaiting result
    </span>
  );
}
