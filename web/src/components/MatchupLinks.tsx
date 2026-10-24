"use client";

import Link from "next/link";
import { createContext, useContext } from "react";

/**
 * Whether the matchup pages are open (local dev, fixture mode, or the
 * CFB_MATCHUP_ENABLED flag). The root layout decides on the server and provides
 * it here so client-rendered cards can show a Matchup button without the flag
 * ever being exposed to the browser. Closed by default.
 */
export const MatchupLinksContext = createContext(false);

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
      className={`inline-flex min-h-11 items-center justify-center gap-1 rounded-md px-3 py-2 text-sm font-medium sm:min-h-9 sm:px-2 sm:py-0.5 sm:text-[11px] focus-visible:outline-2 focus-visible:outline-accent ${className ?? "border border-line bg-surface-card text-ink hover:border-accent hover:text-accent-ink max-sm:-mr-2 max-sm:-my-2 max-sm:border-transparent max-sm:bg-transparent max-sm:font-semibold max-sm:text-accent-ink"}`}
    >
      Matchup <span aria-hidden>→</span>
    </Link>
  );
}
