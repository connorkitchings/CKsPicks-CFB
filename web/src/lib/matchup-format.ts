import type { MatchupData } from "./matchup.ts";
import { etWeekdayDateKickoff } from "./time-et.ts";

/** "Thu, Oct 1, 8:00 PM ET", or "Thu, Oct 1, time TBD" for a placeholder kickoff. */
export const formatKickoff = etWeekdayDateKickoff;

/** "Las Cruces, NM", "Neutral site · Dublin", or null when no location is known. */
export function venueLine(
  matchup: Pick<MatchupData, "venueCity" | "venueState" | "neutralSite">,
): string | null {
  const place = matchup.venueCity
    ? matchup.venueState
      ? `${matchup.venueCity}, ${matchup.venueState}`
      : matchup.venueCity
    : null;
  if (matchup.neutralSite) return place ? `Neutral site · ${place}` : "Neutral site";
  return place;
}
