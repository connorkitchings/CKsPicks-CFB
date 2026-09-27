# Session: Amendment 2 sealed changes implemented (no applies yet)

## TL;DR
- **Worked On:** Implemented the Amendment 2 sealed-change unit of the approved all-five ratings-history contract: per-cutoff Silver pin sets, three measurement configs, runner registrations, seal-test updates.
- **Outcome:** Code complete and fully validated locally (1475 passed, 3 env-skips; ruff/format/contracts/mkdocs clean). No R2/Neon writes, no `--apply` runs. Awaiting user commit before any staged execution.
- **Plan Contract:** `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` (Amendment 2 approved; Tasks 2–4 pending).
- **Approval / Status:** Implementation done in worktree; nothing executed. Sealed changes need user commit (gates require committed HEAD + clean tree).
- **Blockers:** None.
- **Next:** Commit → CI green → construct 3 input bundles → per-cutoff repair chain (W0 first) → W3/W4 compare-only reruns → projections → web tabs.

## Context and Decisions
- Restructured `SEASON_2026_SILVER_INPUTS` → `SEASON_2026_SILVER_INPUT_SETS` keyed `w0/w1/w2/w4` (w4 values byte-identical). Matching requires all four refs from ONE entry — mixing cutoffs fails closed with a distinct error.
- New configs are byte-identical to the 2026 design except `expected_population` (8/51/100); diff-verified. Registered in `SEALED_CONFIGS` + `RELEVANT_PATHS`.
- Seal tests updated to the new structure (w4 pins preserved verbatim + new-entry exact asserts). No other importers of the old name exist.
- New configs must be `git add`ed (tracked): the measurements gate checks dirty-vs-HEAD on relevant paths, and the repair gate requires `ls-files` tracking.

## Work Completed
- `scripts/research/run_data_first_repair_v2.py` — per-cutoff pin sets + same-entry matching
- `scripts/research/run_data_first_possession_measurements.py` — CONFIG_W0/W1/W2, SEALED_CONFIGS, RELEVANT_PATHS
- `conf/.../possession_measurement_2026_w{0,1,2}_v1.yaml` — new sealed configs
- `tests/test_data_first_2026_extension.py` — seal asserts updated/extended

## Files Modified
- Above 6 files (+ this log). No other files touched.

## Validation
- [x] `pytest tests/test_data_first_2026_extension.py`: 22 passed
- [x] Full suite: 1475 passed, 3 skipped (all 3 = DB-gated migration tests, env-only)
- [x] `ruff format --check` + `ruff check` on touched files; `contracts/validation.py`; `mkdocs build --quiet`; `git diff --check`
- [ ] CI on push (expect green; the ~7 min pytest job is the one to watch)

## Amendments and Blockers
None. Scope/stprecedented behavior unchanged: w4 entry and all runner/verifier logic untouched; only additive admissions.

## Handoff Notes
- **Resume at:** Commit (command below) → verify CI → build the 3 `season_2026_inputs` bundles → W0 repair preflight/apply.
- **Watch out for:** Commit MUST include the 3 new YAMLs (untracked). Any `--apply` before commit is refused by tooling gates. Keep staged execution out of the Week 5 freeze lease window.

**tags:** ["v5", "ratings", "history", "sealed-changes", "amendment-2"]
