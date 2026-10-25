const MAX_GAME_ID = 2_147_483_647;

/** Parses the `/matchup/[gameId]` segment: a canonical positive integer (no leading zeros) that fits a 32-bit id, else null. */
export function parseGameId(segment: string): number | null {
  if (!/^[1-9][0-9]*$/.test(segment)) return null;
  const id = Number(segment);
  return id > 0 && id <= MAX_GAME_ID ? id : null;
}
