# Session: Phase 2 v2 Rerun Evidence and Phase 3 v3 Candidate Freeze

## TL;DR

- **Worked On:** Completed the two outstanding Definition-of-Domain items of the
  2026-08-26 rating contract: the Phase 2 v2 byte-identical rerun and the sealed
  Phase 3 v3 score-tournament materialization.
- **Outcome:** Phase 2 v2 rerun is byte-identical (no new lake versions or
  files). Phase 3 v3 **passed every frozen gate** and froze candidate v1
  (`negative_binomial_scores`); Phase 4 shadow operations are now plan-eligible
  under a fresh Sol contract.
- **Plan Contract:** `docs/plans/2026-08-26/phase1-phase2-true-ppso-remediation-and-phase3-v3.md`
- **Approval / Status:** User approved this execution plan on 2026-08-26
  (detached-worktree rerun; stop after Phase 3 closure); contract now
  `Implemented`.
- **Blockers:** None for research closure. Phase 4 requires a new approved
  contract; production (V4, Neon, publication) is untouched.
- **Next:** Fresh Sol planning contract for Phase 4 isolated shadow operations,
  targeting Week 1 as the earliest eligible prospective slate.

## Context and Decisions

- The Phase 2 rerun could not run from HEAD because
  `build_rating_team_states.py` scopes its commit-identity check across the
  whole `src/cks_picks_cfb/ratings` package, which advanced after the recorded
  Phase 2 commit. With user approval, the rerun ran from a detached worktree at
  `ea00bbf` using the main repository's virtualenv (dependency lock unchanged
  between `ea00bbf` and `c4c5cfb`), preserving the exact code identity, as-of
  stamp (`2026-08-26T14:04:00Z`), and output URIs.
- The tournament consumed only historical 2021–2025 outcomes (development
  evidence) plus the 2026 schedule with nulled outcomes for the mandatory
  post-cutoff dry run. No protected 2026 prospective evidence was consumed.

## Work Completed

- **Phase 2 v2 same-stamp rerun** from detached worktree `ea00bbf`:
  `"status": "built"`; every immutable write no-oped. Stored audit report
  SHA-256 `574d0c1a182571f1e89df106745e2d2ceb4a10f0f5f2837361d0b035924ca1da`
  equals the rerun's reported digest; lake versions
  `50c4002b72ed93a9a7ff9f7a` (measurement states) and
  `5237dcb3fdd14c4435d2f050` (team states) unchanged; `states-v2` still holds
  exactly its 3 original files. Worktree removed afterwards.
- **Phase 3 v3 sealed tournament** from HEAD `c4c5cfb`, cutoff
  `2026-08-26T15:02:00Z`, run
  `artifacts/research/rating-successor/score-tournament-v3/503d422c22bc357bfb25b7fe27f8f9c5e14098a1d2748e71d58b043d5a74e6fe/runs/2026-08-26T1502Z-phase3-score-v3/`:
  - Linear scores failed complete-family selection (`Score model emitted
    non-positive or non-finite score means`).
  - `negative_binomial_scores` passed sealed 2022–2024 selection (mean V4 MAE
    ratio `0.9116`, 4,472/4,472 paired rows) and the unchanged locked-2025
    confirmation on 1,522 fully V4-paired games: margin MAE `13.2985` vs V4
    `15.5197` (paired lift 95% CI `[1.585, 2.818]`), total MAE `13.4145` vs V4
    `13.3927` (CI `[-0.568, 0.567]`), all bias/standardized-residual/interval
    coverage gates true.
  - Unchanged refit on 2021–2025; 2026 dry-run predictions written with nulled
    outcomes.
  - Frozen artifacts: tournament SHA-256
    `f71a0f437bf9156670fadd44e5dba6b42f56f8f63f666b682c389da37dfa54bd`; models
    ref `rating_score_models_v3` version `071f4de17b4b351e74e0a670` (content
    `b941a1737ced28543c939496012c742bbb37fe2bb2c3fda57cf45a5038f86d3b`);
    predictions ref `rating_score_predictions_v3` version
    `75e9a9cc7e942823bde56a2a` (content
    `226931b625769f008e91458afb984026c9976efba323030d408838df56be69b3`);
    candidate manifest declares `earliest_eligible_prospective_window` = 2026
    Week 1 normal-coverage slate, `dry_run_only: true`.
- Closed authority docs: plan contract (status + DoD + Amendment 5), plan
  index, roadmap phase queue, rating-system requirements.

## Files Modified

- `docs/plans/2026-08-26/phase1-phase2-true-ppso-remediation-and-phase3-v3.md`
  — status to Implemented; DoD complete; Amendment 5 records both outcomes.
- `docs/plans/index.md` — rating-transition contract statuses.
- `docs/planning/roadmap.md` — phase queue entry for the 2026-08-26 contract.
- `docs/modeling/rating_system_requirements.md` — Phase 3 v3 freeze record and
  candidate identity.
- `session_logs/2026-08-26/02-phase2-rerun-and-phase3-v3-freeze.md` — this log.

## Validation

- [x] Phase 2 rerun byte identity: report SHA match, no new lake versions, no
  new `states-v2` files, worktree cleaned up (`git worktree list` = main only).
- [x] Phase 3 v3 materialization: `"status": "built"`, locked confirmation
  `all_checks_passed: true`, all four run artifacts present under the run
  prefix.
- [x] `uv run pytest tests/ratings -q` and full suite (post-closure run):
      106 ratings passed; 520 passed, 2 skipped.
- [x] Scoped Ruff format/check: 250 files formatted, all checks passed.
- [x] `make contracts-check`: passed.
- [x] `uv run mkdocs build --strict`: built successfully.
- [x] `git diff --check`: clean.

## Amendments and Blockers

- Amendment 5 in the plan contract records the approved detached-worktree rerun
  mechanism and the tournament freeze; no gate, equation, parent, or selection
  rule changed.

## Handoff Notes

- **Resume at:** Sol planning for Phase 4 isolated shadow operations (research
  -only pregame freeze + paired postgame scoring); candidate v1 must run
  unchanged from the frozen refs.
- **Watch out for:** Do not tune or re-materialize the v3 candidate after this
  report; every 2026 outcome it scores prospectively is protected evidence.
  Week 0 does not count toward the six-slate promotion gate. V4 remains the
  production champion; no Neon, publication, bundle, or market path may read
  rating artifacts before a Phase 7 promotion contract.

**tags:** ["ratings", "phase2", "phase3", "tournament", "candidate-freeze", "preview"]
