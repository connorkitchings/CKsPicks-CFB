export function prospectiveEvidenceLabel(uri: string, season: number, week: number, runId: string, sha: string): string {
  if (!/^[a-f0-9]{64}$/.test(sha) || season !== 2026 || week < 5) throw new Error("Invalid prospective evidence scope");
  const normal = `artifacts/prospective/v5/season=${season}/week=${week}/${runId}/freeze-${sha}.json`;
  if (uri === normal) return "Prospective · contemporaneous freeze receipt";
  if (week === 5 && ["preview", "production"].some((environment) =>
    uri === `artifacts/prospective/v5/environment=${environment}/season=2026/week=5/${runId}/legacy-attestation-v1-${sha}.json`,
  )) return "Prospective · retrospectively attested (no contemporaneous receipt)";
  throw new Error("Unknown prospective receipt kind");
}
