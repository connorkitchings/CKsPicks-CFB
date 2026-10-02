"use client";

import Link from "next/link";
import { createContext, useContext } from "react";

/**
 * Whether the matchup pages are open (local dev, fixture mode, or the
 * CFB_MATCHUP_ENABLED flag). The root layout decides on the server and provides
 * it here so client-rendered cards can show a Matchup button without the flag
 * ever being exposed to the browser. Closed by default.
 */
const MatchupLinksContext = createContext(false);

export function MatchupLinksProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: React.ReactNode;
}) {
  return <MatchupLinksContext.Provider value={enabled}>{children}</MatchupLinksContext.Provider>;
}

/** Link to a game's matchup breakdown; renders nothing while matchups are closed. */
export function MatchupButton({ gameId, className }: { gameId: number; className?: string }) {
  const enabled = useContext(MatchupLinksContext);
  if (!enabled) return null;
  return (
    <Link
      href={`/matchup/${gameId}`}
      data-testid="matchup-link"
      className={
        className ??
        "inline-flex items-center gap-1 rounded-md border border-line bg-surface-elevated px-2 py-0.5 text-[11px] font-medium text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent"
      }
    >
      Matchup <span aria-hidden>→</span>
    </Link>
  );
}
