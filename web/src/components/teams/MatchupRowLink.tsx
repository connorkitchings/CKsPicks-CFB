"use client";

import Link from "next/link";
import { useContext } from "react";
import { MatchupLinksContext } from "@/components/MatchupLinks";

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
