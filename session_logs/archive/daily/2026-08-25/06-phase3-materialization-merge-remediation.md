# Session: Phase 3 Materialization Merge Remediation

## TL;DR

- **Worked On:** Attempted the authorized Preview Phase 3 materialization and
  corrected the schedule/outcome merge it exposed before any artifact write.
- **Outcome:** Both initial attempts stopped before artifact creation. The
  corrected code now uses authoritative outcome-score columns even when the
  canonical schedule also carries scores.
- **Plan Contract:**
  `docs/plans/2026-08-25/phase3-structured-margin-total-baseline.md`
- **Approval / Status:** User authorized Preview materialization on 2026-08-25;
  Phase 3 remains `In Progress` pending a commit and a fresh Preview run.
- **Blockers:** Required corrective-code commit before retry.
- **Next:** Commit the two corrected files, then rerun Preview from a new
  run-stamped prefix using the already-recovered certified parent-ref paths.

## Incident and Correction

- The first invocation found that assumed staged parent-ref filenames did not
  exist; it stopped before raw-data reads or artifact writes. The exact staged
  files were recovered read-only from the Phase 1 input prefix.
- The second invocation reached feature assembly and stopped before a write:
  canonical `games` includes `home_points` and `away_points`, so pandas
  suffixed the separately joined authoritative outcome scores.
- `prepare_prediction_frame` now renames outcome completion and score fields
  before the join and calculates margin/total only from those renamed outcome
  fields. The regression fixture includes conflicting schedule scores.

## Validation

- [x] `uv run pytest tests/ratings/test_predictions.py -q` — 5 passed.
- [x] `uv run pytest tests/ratings -q` — 85 passed.
- [x] `uv run pytest -q` — 499 passed, 2 skipped.
- [x] Scoped Ruff, contracts validation, contracts sync, strict MkDocs, and
  `git diff --check`.
- [ ] Preview materialization — intentionally deferred until the corrective
  paths are committed and can satisfy the CLI identity gate.

## Handoff Notes

- **Resume at:** Commit `src/cks_picks_cfb/ratings/predictions.py` and
  `tests/ratings/test_predictions.py`, then retry from a new UTC run stamp.
- **Watch out for:** Reuse only the recovered Phase 1 games/outcome refs and
  the certified V4 ref; no failed attempt created an immutable artifact.

**tags:** ["ratings", "phase3", "preview", "remediation", "lineage"]
