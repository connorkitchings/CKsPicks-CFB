/** Charts remain unpublished unless the server explicitly opts in. */
export function isChartsEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return env.CFB_CHARTS_ENABLED === "1";
}
