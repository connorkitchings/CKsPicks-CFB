export const TEAM_LOGO_MAP: Record<string, string> = {
  "Sam Houston": "Sam Houston State",
  "UL Monroe": "Louisiana Monroe",
  Massachusetts: "UMass",
  "App State": "Appalachian State",
  "San José State": "San Jose State",
  UTSA: "UT San Antonio",
  "Hawai'i": "Hawai_i",
  Hawaii: "Hawai_i",
  "Hawai i": "Hawai_i",
  UConn: "Connecticut",
  "Southern Miss": "Southern Mississippi",
  FIU: "Florida International",
  "Texas A&M": "Texas A&M",
};

export function logoFilename(teamName: string): string {
  const mapped = TEAM_LOGO_MAP[teamName] ?? teamName;
  return `${mapped}.png`;
}

export function logoUrl(teamName: string): string {
  return `/logos/${encodeURIComponent(logoFilename(teamName))}`;
}
