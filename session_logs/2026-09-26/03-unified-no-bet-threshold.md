# Session: Unified 1.0 no-bet rule — implemented, released to production

## TL;DR
- **Worked On:** Implemented the unified sub-1.0 no-bet rule (Tasks 1–4), rebuilt the replacement batch on Preview (`-r3`), verified it fully, and built + validated five production packets (Task 5).
- **Outcome:** The public site now serves the `-r3` batch.
- **Plan Contract:** `docs/plans/2026-09-26/02-unified-no-bet-threshold.md` (Implemented)
- **Approval / Status:** User release approval recorded; execution complete.
- **Blockers:** None. W4 scoring waits at its finals gate.
- **Next:** Commit; W4 scoring at finals gate; Week 5 live weekly config must carry the 1.0 thresholds.

## Context and Decisions

- The site showed a model side for all 32 sub-1.5 totals (ungraded) and graded 11 spreads with edge < 1.0, because `prepare_predictions` derived leans arithmetically and ignored the artifact "No Bet" labels (the standard scorer's label-first logic fell back to the lean).
- Fix: artifact bet labels are authoritative for published leans (`No Bet`→null, arithmetic fallback for label-less legacy frames); thresholds split into lean (`spread_edge_threshold: 1.0`, new `total_lean_threshold: 1.0`) and grade (`total_edge_threshold: 1.5` kept) meanings; V4 configs untouched.
- Two real bugs caught by verification during the work: (1) first null leans exposed NaN→enum binding failure in `_row_to_record` (fixed with the established NaN→None pattern for leans + quote IDs); (2) the rehearsal's own stale-rule debris batch failed the updated verifier, proving the harness rejects outdated runs.
- Selections are kept for sub-1.0 targets (lineage for the displayed Market point); verification counts selections vs lined rows and asserts null leans pair only with sub-threshold edges.

## Work Completed

- `resolve_label_thresholds()` in `weekly.py` + wiring in all three generate scripts; V5 replay configs updated (spread 1.0, `total_lean_threshold` 1.0).
- Publish label-honoring + NaN normalization + 5 new publish tests; 3 weekly-inference threshold tests.
- Rehearsal `verify_selections` upgraded (lined counts, null-lean edge assertions, `_lean_thresholds`); full `-r3` Preview batch green: forecasts identical to source runs, 146 spread + 124 total grades (−11 spreads as predicted, totals unchanged), 0 bad market ticks, stats guard, idempotency.
- Serving rehearsal on the `-r3` batch (null leans exactly the sub-1.0 set, zero above-threshold nulls) + rollback restore of Preview selections.
- Production driver pointed at `-r3`; 5 candidates prepared byte-identical; 5 packets validate (`v5-bestquote-2026w{0..4}-{00632b2e,469d2df8,3cd45db9,e9481c48,4f1e8436}`).
- Docs: no-bet rule in `weekly_pipeline.md` + `production_runbook.md`, `v5_status.md` item 5, plan DoD.

## Files Modified

- `src/cks_picks_cfb/inference/weekly.py` — `resolve_label_thresholds()`
- `scripts/pipeline/generate_weekly_bets.py`, `generate_v5_weekly_bets.py`, `generate_v5_replay_weekly_bets.py` — threshold wiring
- `conf/weekly_bets/v5_replay_2026.yaml`, `v5_replay_w4_2026.yaml` — 1.0 lean thresholds
- `scripts/pipeline/publish_to_db.py` — label-honoring leans + NaN→None records
- `scripts/pipeline/rehearse_v5_bestquote_replay_preview.py` — verification upgrades
- `scripts/pipeline/release_v5_bestquote_replacement_production.py` — `-r3` batch
- `tests/test_weekly_inference.py`, `tests/test_publish_to_db.py` — 8 new tests
- `docs/plans/2026-09-26/02-unified-no-bet-threshold.md` — new Approved contract
- `docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`, `docs/modeling/v5_status.md`
- Preview R2/Neon: `-r3` artifacts/runs/selections/grades (W0–3 scored, W4 published); selections restored to originals. Production R2: `-r3` candidates only; zero production Neon writes.

## Validation

- [x] Full suite: 1,456 passed, 2 skipped (8 new tests)
- [x] `ruff check .`, `ruff format`, `make contracts-check`, `git diff --check`
- [x] Web suite unaffected (no web changes in this contract)
- [x] `mkdocs build --strict --quiet`
- [x] Rehearsal gates per week (refs, forecasts, selections, grades, ticks, stats, idempotency)
- [x] Serving selection + rollback drill on Preview
- [x] 5/5 replay packets `{"valid": true}`

## Amendments and Blockers

None. Production re-release of the `-r3` batch needs a fresh explicit decision (parent plan is Implemented; this contract stops at the gate).

## Handoff Notes

- **Resume at:** User commits. Release complete: 5 admin authorization rows (`v5-bestquote-2026w{0..4}-{00632b2e,469d2df8,3cd45db9,e9481c48,4f1e8436}`); W0–3 published/scored/selected (15/76/82/97 = 270 grades); W4 published/selected 58/58 unscored; health `ok`; V4/original/`-r2` runs untouched.
- **Watch out for:** Never select the `-r2` (old-rule, superseded) or unsuffixed debris batches; the Week 5 live weekly config must carry the 1.0 thresholds when created; W4 scoring still waits at its finals gate.

**Suggested commit message:** `feat(release): activate unified no-bet r3 replacement weeks on production`

**tags:** ["v5", "best-quote", "no-bet", "lean", "preview", "packet"]
