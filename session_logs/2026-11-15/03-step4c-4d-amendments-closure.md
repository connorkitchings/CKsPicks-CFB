# Session: Steps 4C and 4D, amendment drafts and audit closure

## TL;DR

- **Worked On:** Closed out the V5 baseline audit: made the step 4 analysis reproducible, ran the totals-head (4C) and venue-flag (4D) experiments, drafted protocol amendments 7 to 10 with a YAML diff, and wrote the audit conclusions.
- **Outcome:** Neither experiment helps. Totals: no shrinkage or feature form beats the baseline by more than 0.02 total MAE (declared bar 0.20); the ratings carry little totals signal. Venue: using the neutral-site flag moves the neutral bias from -1.50 to +2.53 on 80 FBS-vs-FBS games, so it overshoots. P3 is frozen as a named specification with script hashes. Audit steps 1 to 4 are complete.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved the plan (all declarations, thresholds and the alpha list) on 2026-11-15. Contract stays `Draft`. Four local commits on `dev`, not pushed. Nothing from 2026 was scored; no file in `conf/` or the protocol changed.
- **Blockers:** Owner gates: approve or edit amendments 7 to 10 and the YAML diff; decide step 5 and the 2027 forward test; say where the other session's work lives.
- **Next:** Owner decision on the gates above.

**tags:** ["model-research", "baseline-audit", "totals", "venue", "protocol-amendments"]

## Context and Decisions

- Work ran on local `dev` as the approved plan specified (documentation only in the repository).
- The 2026 exposure from the earlier steps is recorded, not extended.
- 4C and 4D scripts load only the 2015 to 2025 frame; neither touches 2026.

## Work Completed

- Copied the ten earlier scripts to `~/cfb_ratings_lab_v6/scripts/step4-2026-11-15/` with a `SHA256SUMS` file; cited hashes and froze the P3 specification in the contract.
- 4C: eight candidates (F4 at six alphas, F1, F2), baseline reproduced the stored total predictions (difference 0.0, 3,483 games, 2,998 FBS-vs-FBS and 485 FBS-vs-FCS). Class: no material gain.
- 4D: flag joined for all 4,332 games of 2021 to 2025 (126 neutral); both arms fitted from 2021, scored 2023 to 2025. Class: no evidence of an effect.
- Drafted amendments 7 (2026 exposure), 8 (headline population, flagged as the one to scrutinise), 9 (P3 frozen, 95% interval pass condition) and 10 (three-season selection rule), plus the YAML diff, all unapplied.
- Wrote "Audit conclusions", the status line, the handoff entry (2026 exposure, output-file collision, open gates) and the plans index state line.
- Note: the FBS-vs-FCS count is 485 under the 4B tier assignment; step 4A reported 484 plus one untiered game (the same games).

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`
- `docs/plans/index.md`
- `session_logs/2026-11-15/03-step4c-4d-amendments-closure.md`
- Outside the repository: `~/cfb_ratings_lab_v6/scripts/step4-2026-11-15/` (new), `~/cfb_ratings_lab_v6/output/step4c-2026-11-15/step4c_totals_results.json`, `~/cfb_ratings_lab_v6/output/step4d-2026-11-15/step4d_venue_results.json`

## Validation

- [x] Baseline reproduces stored predictions (margin and total, largest difference 0.0)
- [x] Game counts: 3,483 per target; 2,998 FBS-vs-FBS
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`
- [x] Script hashes in the contract match the files on disk (checked below)

## Amendments and Blockers

- None to the plan; see the owner gates above.
