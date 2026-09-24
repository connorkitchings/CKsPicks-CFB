/**
 * Rendering eligibility for an explicitly selected weekly run. Mirrors the
 * operator selection policy (`cks_picks_cfb.ops.public_selection`): a V5 run
 * needs a truthful evidence class, and only a complete legacy run may serve
 * as a same-slate V4 fallback. Anything else fails closed — a missing or
 * ineligible selection never guesses a run.
 */
const PUBLISHED_STATES = new Set(["published", "frozen", "scored"]);
const V5_EVIDENCE_CLASSES = new Set(["pending", "replay", "live"]);

export function isSelectableRun(run: {
  modelId: string | null;
  evidenceClass: string | null;
  state: string;
}): boolean {
  if (!PUBLISHED_STATES.has(run.state)) return false;
  const modelId = run.modelId ?? "";
  const evidenceClass = run.evidenceClass ?? "";
  if (modelId.startsWith("v5-")) {
    return V5_EVIDENCE_CLASSES.has(evidenceClass);
  }
  return evidenceClass === "legacy";
}

/** True when the viewed week's selected run is the V5 model. */
export function selectsV5(modelId: string | null | undefined): boolean {
  return typeof modelId === "string" && modelId.startsWith("v5-");
}
