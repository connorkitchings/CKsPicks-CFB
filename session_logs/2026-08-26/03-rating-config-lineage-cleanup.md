# Session: Rating Config Lineage Cleanup (Supersede v1/v2 Defaults)

## TL;DR

- **Worked On:** Retired the superseded v1/v2 ratings research configs by
  flipping the four research CLI defaults to the current v3 lineage, pinning
  those defaults with a regression test, and recording supersession in the
  authority docs.
- **Outcome:** No script can implicitly resume the pre-remediation
  (Boolean-PPSO) lineage; `docs/plans/index.md`, the measurement catalog, and
  the Phase 3 v2 plan now mark the old chain superseded. No yaml values, R2
  artifacts, lake versions, or gates changed.
- **Plan Contract:** N/A (fast path; user-approved cleanup plan from the
  2026-08-26 version-matrix review)
- **Approval / Status:** User approved option A (supersede in place), cleanup
  first, then Phase 4 planning; historical-only Phase 4 rehearsal chosen.
- **Blockers:** None.
- **Next:** Fresh Sol contract for Phase 4 isolated shadow operations
  (pregame freeze + paired postgame scoring; rehearsal on 2025 historical
  weeks only; no 2026 data until the real Week 1 freeze).

## Context and Decisions

- The stale configs (`measurement_baseline_v1.yaml` — internally
  `measurement_baseline_v2` after the in-place `cba1577` remediation, with the
  Boolean-PPSO defect — plus `team_state_baseline_v1`, `foundation_review_v1`,
  `score_model_tournament_v2`, and `prediction_baseline_v1`) must remain in the
  repository because immutable failed-research artifacts and plans cite their
  design SHAs; deletion or value edits would break the evidence chain.
- Flipping defaults is behaviorally safe: every script replaces its
  RELEVANT-tuple yaml entry with the runtime `--config` path for commit checks,
  and the v3 tournament's frozen run materialized from the explicit config path.
- `build_rating_predictions.py` (Phase 3 v1 margin/total OLS, failed gates) was
  left untouched — superseded via docs only, consistent with its Superseded
  plan.
- One CLI test implicitly relied on `build_rating_team_states.py` defaulting to
  the v1 config; it now passes `--state-config` explicitly, preserving its
  purpose (v1-lineage pin checking) without depending on defaults.

## Work Completed

- Flipped `DEFAULT_CONFIG` (and the matching RELEVANT yaml literal where
  present) in:
  - `scripts/pipeline/build_rating_measurements.py` →
    `measurement_baseline_v3.yaml`
  - `scripts/pipeline/build_rating_team_states.py` →
    `team_state_baseline_v2.yaml`
  - `scripts/pipeline/build_rating_foundation_review.py` →
    `foundation_review_v2.yaml`
  - `scripts/pipeline/build_rating_score_tournament.py` →
    `score_model_tournament_v3.yaml`
- Generalized "Phase 3 v2" wording in the tournament script to "Phase 3"
  (docstring and error messages; no gating semantics).
- Added `test_rating_cli_defaults_point_at_current_lineage_configs` in
  `tests/ratings/test_cli.py` pinning all four defaults.
- Updated `docs/plans/index.md` (Phase 3 v2 contract → Superseded),
  `docs/plans/2026-08-25/phase3-score-model-tournament-v2.md` (status →
  Superseded), and `docs/modeling/measurement_catalog.md` (header reflects v3
  current; Phase 4 plan-eligible note; config-supersession record).

## Files Modified

- `scripts/pipeline/build_rating_measurements.py` — default config flip.
- `scripts/pipeline/build_rating_team_states.py` — default config flip.
- `scripts/pipeline/build_rating_foundation_review.py` — default config flip.
- `scripts/pipeline/build_rating_score_tournament.py` — default config flip +
  version-neutral wording.
- `tests/ratings/test_cli.py` — explicit v1 config in the state CLI test; new
  defaults guard test.
- `docs/plans/index.md`, `docs/plans/2026-08-25/phase3-score-model-tournament-v2.md`,
  `docs/modeling/measurement_catalog.md` — supersession records.
- `session_logs/2026-08-26/03-rating-config-lineage-cleanup.md` — this log.

## Validation

- [x] `uv run pytest tests/ratings -q` — 107 passed.
- [x] `uv run pytest -q` (full suite) — 521 passed, 2 skipped.
- [x] `uv run ruff format . && uv run ruff check .` — clean (one reformat).
- [x] `make contracts-check` — passed.
- [x] `uv run mkdocs build --strict` — exit 0.
- [x] `git diff --check` — clean.

## Amendments and Blockers

None.

## Handoff Notes

- **Resume at:** Sol planning for the Phase 4 shadow-operations contract.
- **Watch out for:** The frozen v3 candidate (models ref `071f4de1…`,
  predictions ref `75e9a9cc…`) must run unchanged in Phase 4; every 2026
  outcome it scores prospectively is protected evidence. Week 0 does not count
  toward the six-slate promotion gate. No Neon/publication/V4 path may read
  rating artifacts before a Phase 7 promotion contract.

**tags:** ["ratings", "cleanup", "config", "supersession", "fast-path"]
