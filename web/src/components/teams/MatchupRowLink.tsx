"use client";

import Link from "next/link";
import { useContext } from "react";
import { MatchupLinksContext } from "@/components/MatchupLinks";

/** The schedule table's link to a game's matchup page; nothing while matchups are closed. */
export function MatchupCellLink({ gameId }: { gameId: number }) {
  const enabled = useContext(MatchupLinksContext);
  if (!enabled) return null;
  return (
    <Link href={`/matchup/${gameId}`} data-testid="schedule-matchup-link" aria-label="Matchup" className="rounded px-1 font-medium text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
      <span aria-hidden>→</span>
    </Link>
  );
}

/** Wraps a schedule row in a link to its matchup page while matchups are open; a plain block otherwise. */
export function MatchupRowLink({ gameId, children }: { gameId: number; children: React.ReactNode }) {
  const enabled = useContext(MatchupLinksContext);
  if (!enabled) return <div className="px-3 py-2.5">{children}</div>;
  return (
    <Link href={`/matchup/${gameId}`} data-testid="matchup-link" className="block px-3 py-2.5 hover:bg-surface-inset focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent">
      {children}
    </Link>
  );
}
