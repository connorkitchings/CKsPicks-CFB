const MAX_GAME_ID = 2_147_483_647;

/** Parses the `/matchup/[gameId]` segment: a positive integer that fits a 32-bit id, else null. */
export function parseGameId(segment: string): number | null {
  if (!/^[0-9]+$/.test(segment)) return null;
  const id = Number(segment);
  return id > 0 && id <= MAX_GAME_ID ? id : null;
}
