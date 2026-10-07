import { test } from "node:test";
import assert from "node:assert/strict";
import { prospectiveEvidenceLabel } from "./prospective-provenance.ts";
const sha = "a".repeat(64);
test("legacy attestation is disclosed and constrained to Week 5", () => {
  const uri = `artifacts/prospective/v5/environment=preview/season=2026/week=5/original/legacy-attestation-v1-${sha}.json`;
  assert.match(prospectiveEvidenceLabel(uri, 2026, 5, "original", sha), /retrospectively attested/);
  assert.throws(() => prospectiveEvidenceLabel(uri, 2026, 6, "original", sha));
  assert.throws(() => prospectiveEvidenceLabel(uri, 2026, 5, "other", sha));
});
test("normal receipt and unknown kinds", () => {
  assert.match(prospectiveEvidenceLabel(`artifacts/prospective/v5/season=2026/week=6/original/freeze-${sha}.json`, 2026, 6, "original", sha), /contemporaneous/);
  assert.throws(() => prospectiveEvidenceLabel("unknown", 2026, 5, "original", sha));
});
