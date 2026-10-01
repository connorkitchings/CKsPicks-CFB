import { LOGO_IDS } from "./team-logos.generated.ts";
import { TEAM_LOGO_MAP, logoUrl as legacyLogoUrl } from "./teams.ts";

export type LogoSize = "sm" | "lg";
export type LogoTheme = "light" | "dark";

/** True once `scripts/build-team-logos.mjs` has produced the id map. */
export const LOGOS_BUILT = Object.keys(LOGO_IDS).length > 0;

export function logoId(teamName: string): number | null {
  return LOGO_IDS[teamName] ?? LOGO_IDS[TEAM_LOGO_MAP[teamName] ?? ""] ?? null;
}

export function hasLogo(teamName: string): boolean {
  return logoId(teamName) !== null;
}

export function logoSrc(teamName: string, size: LogoSize, theme: LogoTheme): string | null {
  const id = logoId(teamName);
  return id === null ? null : `/logos/v2/${size}/${theme}/${id}.webp`;
}

/** Legacy 32 px file; used only until the v2 set is built (contract 07, Phase C). */
export function legacyLogoSrc(teamName: string): string {
  return legacyLogoUrl(teamName);
}

export function teamInitials(teamName: string): string {
  const words = teamName.replace(/[^A-Za-z\s]/g, "").split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? words.slice(0, 2).map((w) => w[0]).join("") : words[0]?.slice(0, 2) ?? "?";
  return letters.toUpperCase();
}
