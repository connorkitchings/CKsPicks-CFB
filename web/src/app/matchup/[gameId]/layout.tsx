import { notFound } from "next/navigation";
import { getMatchupData } from "@/lib/matchup";
import { parseGameId } from "@/lib/matchup-id";
import { isMatchupEnabled } from "@/lib/matchup-gate";

/**
 * Resolves the game above the route's loading boundary: once `loading.tsx` has streamed its
 * shell the status is already 200, so an unknown, invalid or unpublished game must be rejected
 * here to get a real 404. `getMatchupData` is request-cached, so the page reuses this result;
 * the ID is range-validated first and the lookup keys no cross-request cache on it.
 */
export default async function MatchupLayout({ children, params }: { children: React.ReactNode; params: Promise<{ gameId: string }> }) {
  if (!isMatchupEnabled()) notFound();
  const id = parseGameId((await params).gameId);
  if (id === null || !(await getMatchupData(id))) notFound();
  return children;
}
