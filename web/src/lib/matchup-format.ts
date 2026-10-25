import type { MatchupData } from "./matchup.ts";
import { etWeekdayDateTime } from "./time-et.ts";

/** "Thu, Oct 1, 8:00 PM ET" */
export const formatKickoff = etWeekdayDateTime;

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
