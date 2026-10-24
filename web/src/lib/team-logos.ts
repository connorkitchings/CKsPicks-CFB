import { LOGO_IDS, TEAM_DISPLAY } from "./team-logos.generated.ts";

export type LogoSize = "sm" | "lg";
export type LogoTheme = "light" | "dark";

// Audited primary marks remain readable on the dark surface. Their dark assets
// are white, so retain team color; other schools keep their contrast variants.
const PRIMARY_COLOR_LOGO_IDS = new Set([2633, 228, 2534, 251, 249, 2084, 254]);

/** Other spellings of a school name -> the CFBD name used as the key in LOGO_IDS. */
const LOGO_ALIASES: Record<string, string> = {
  "Appalachian State": "App State",
  "Southern Mississippi": "Southern Miss",
  "Louisiana Monroe": "UL Monroe",
  "Sam Houston State": "Sam Houston",
  "San Jose State": "San José State",
  "UT San Antonio": "UTSA",
  Hawaii: "Hawai'i",
  "Hawai_i": "Hawai'i",
  "Hawai i": "Hawai'i",
  Connecticut: "UConn",
  UMass: "Massachusetts",
  FIU: "Florida International",
  "Miami (FL)": "Miami",
  "Miami FL": "Miami",
  "Louisiana-Monroe": "UL Monroe",
};

/** House abbreviations where CFBD's read poorly ("TA&M", "CONN"); keyed by CFBD school name. */
const ABBR_OVERRIDES: Record<string, string> = {
  "Texas A&M": "TAMU",
  UConn: "UCONN",
  Louisiana: "ULL",
  Tulane: "TUL",
};

function schoolKey(teamName: string): string {
  return teamName in LOGO_IDS ? teamName : (LOGO_ALIASES[teamName] ?? teamName);
}

export function logoId(teamName: string): number | null {
  return LOGO_IDS[teamName] ?? LOGO_IDS[LOGO_ALIASES[teamName] ?? ""] ?? null;
}

export function hasLogo(teamName: string): boolean {
  return logoId(teamName) !== null;
}

export function logoSrc(teamName: string, size: LogoSize, theme: LogoTheme): string | null {
  const id = logoId(teamName);
  const assetTheme = id !== null && PRIMARY_COLOR_LOGO_IDS.has(id) ? "light" : theme;
  return id === null ? null : `/logos/v2/${size}/${assetTheme}/${id}.webp`;
}

export function teamInitials(teamName: string): string {
  const words = teamName.replace(/[^A-Za-z\s]/g, "").split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? words.slice(0, 2).map((w) => w[0]).join("") : words[0]?.slice(0, 2) ?? "?";
  return letters.toUpperCase();
}

/** Neutral chart color for a team without published color metadata. */
export const FALLBACK_TEAM_COLOR = "#64748b";

/** CFBD abbreviation (display only); falls back to the team's initials. */
export function teamAbbr(teamName: string): string {
  const key = schoolKey(teamName);
  const abbr = ABBR_OVERRIDES[key] ?? TEAM_DISPLAY[key]?.abbr;
  if (abbr) return abbr;
  const words = teamName.replace(/[^A-Za-z\s]/g, "").split(/\s+/).filter(Boolean);
  const text = words.length > 1 ? words.map((w) => w[0]).join("").slice(0, 4) : (words[0] ?? "").slice(0, 4);
  return (text || "?").toUpperCase();
}

/** Names longer than this wrap a phone pick label, so phones show the abbreviation instead. */
const PHONE_NAME_MAX_CHARS = 14;

/** The name a phone pick label shows: the full name when short, otherwise the abbreviation. */
export function phoneTeamName(teamName: string): string {
  return teamName.length > PHONE_NAME_MAX_CHARS ? teamAbbr(teamName) : teamName;
}

/** CFBD primary color (display only), or a neutral fallback. */
export function teamColor(teamName: string): string {
  return TEAM_DISPLAY[schoolKey(teamName)]?.color ?? FALLBACK_TEAM_COLOR;
}

/** CFBD alternate color, or null when none is published. */
export function teamAltColor(teamName: string): string | null {
  return TEAM_DISPLAY[schoolKey(teamName)]?.altColor ?? null;
}
