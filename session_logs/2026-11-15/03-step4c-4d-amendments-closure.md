# Session: Steps 4C and 4D, amendment drafts and audit closure

## TL;DR

- **Worked On:** Closed out the V5 baseline audit: made the step 4 analysis reproducible, ran the totals-head (4C) and venue-flag (4D) experiments, drafted protocol amendments 7 to 10 with a YAML diff, and wrote the audit conclusions.
- **Outcome:** Neither experiment helps. Totals: no shrinkage or feature form beats the baseline by more than 0.02 total MAE (declared bar 0.20); the ratings carry little totals signal. Venue: using the neutral-site flag moves the neutral bias from -1.50 to +2.53 on 80 FBS-vs-FBS games, so it overshoots. P3 is frozen as a named specification with script hashes. Audit steps 1 to 4 are complete.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved the plan (all declarations, thresholds and the alpha list) on 2026-11-15. Contract stays `Draft`. Four local commits on `dev`, not pushed. Nothing from 2026 was scored; no 2026 data scored in 4C or 4D.
- **Blockers:** Open: amendments 1 and 2 (to be edited before applying) and the location of the other session's analysis script (only its two output files are known).
- **Next:** Run the rating-recipe check (recompute 2025 states with the 2026 pipeline and diff against the historical states); revisit the 2027 offset rule before 2027.

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

## Owner decisions (end of session)

Approved amendments 7, 9, 10 (applied to the protocol and `protocol.yaml`, additive keys only); amendment 8 held; go to the 2027 forward test and skip the rest of step 5 except the rating-recipe check; other session's work to be treated as unverified. Files also modified: `docs/plans/2026-11-12/02-offseason-research-protocol.md`, `conf/research/offseason_2027/protocol.yaml`.

Later the same day the owner also approved amendment 8 (FBS-vs-FBS headline, FBS-vs-FCS kept as a separate secondary), 3, 5 and 6 (4 folded into 7), and the provisional 2027 offset rule (amendment 11). All were applied to the protocol and `protocol.yaml`. The other session's analysis outputs are `~/cfb_ratings_lab_v6/output/step4a-2026-11-15/step4a_results.json` and `step4b-2026-11-15/step4b_results.json`; its script was not found. Uncommitted `web/` changes on `dev` belong to the site session and were left alone.
