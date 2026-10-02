/**
 * Dependency-free helpers for raw `db.execute()` results.
 *
 * drizzle's Neon HTTP driver returns `{ rows: [...], fields, ... }`, while other
 * drivers return a bare array. Reading only the array shape made every
 * `to_regclass` guard report "table missing" even when it existed, so the
 * optional tables (selections, venues, team stats) never rendered.
 */
export function rowsOf(result: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(result)) return result as Array<Record<string, unknown>>;
  const rows = (result as { rows?: unknown } | null | undefined)?.rows;
  return Array.isArray(rows) ? (rows as Array<Record<string, unknown>>) : [];
}

/** True when a `SELECT ... AS exists` query returned a truthy first row. */
export function existsFrom(result: unknown): boolean {
  return Boolean(rowsOf(result)[0]?.exists);
}
