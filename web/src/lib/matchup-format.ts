import type { MatchupData } from "./matchup.ts";

/** "Thu, Oct 1, 8:00 PM EDT". Pass a time zone for output that must not depend on the machine (the share card). */
export function formatKickoff(startDate: Date, timeZone?: string): string {
  return startDate.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
    ...(timeZone ? { timeZone } : {}),
  });
}

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
