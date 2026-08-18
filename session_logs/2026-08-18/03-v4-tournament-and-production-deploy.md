# Session: V4 Tournament and Production Deploy

## TL;DR

- **Worked On:** Executed the full V4 tournament (selection → locked 2025 → refit → rehearsal), fixed four latent pipeline bugs, set up production Neon + R2 + Vercel, and published the V4 model to the live site.
- **Outcome:** V4 is the first model to pass sealed selection and locked-2025 gates. Production site is live at https://c-ks-picks-cfb.vercel.app in fail-closed market mode (8/8 games, 0 high-confidence).
- **Plan Contract:** `docs/plans/2026-08-18/week0-launch-execution.md` (In Progress — Stages 1–3 complete, Stages 4–5 pending game week)
- **Approval / Status:** User authorized the full plan and implementation on 2026-08-18.
- **Blockers:** Stage 4 (progressive publish + freeze) waits for game week (Aug 25–29). Pick'em needs `CFBD_PREDICTION_TOKEN`.
- **Next:** Rerun publish-week in production as lines update; freeze before Aug 29 kickoff; flip publication mode to predictions on user approval.

## Context and Decisions

- V4 uses the `prior_core` feature variant only (all additive preseason families
  were unavailable in the strict reference — by design, since CFBD talent and
  other sources lack pre-kickoff effective-time evidence for every required
  season).
- All 8 Week 0 games route to `game_1` (zero completed games). The launch model
  is spread/game_1 = direct_catboost, total/game_1 = baseline (prior-quality
  fallback).
- Production R2 shares the preview bucket (`cks-picks-cfb-preview`); immutable
  artifacts are checksummed and environment-neutral. Neon branches separate
  databases.
- The production Neon catalog was hydrated from Preview via COPY (7,163 source
  captures, 85 dataset versions).
- A `cks_prod_web` LOGIN role was created for Vercel with SELECT grants only.

## Work Completed

### Stage 1 — V4 tournament (Preview only)

- Applied migration `0008` to `preview-2026`; verified frozen V2 run intact.
- Resolved frozen input refs from active run `a0edb9e72cb1` `input_refs.json` in R2.
- Built guarded 2025 baselines (frozen design SHA `ae34ddc7…`).
- Assembled strict V5 model-ready Gold (version `e6ebb94b…`).
- Sealed 2022–2024 selection → design SHA `ae34ddc7…`.
- Locked 2025 validation: all 8 routes passed anti-regression.
- Refit ten-route V4 bundle on 2021–2025 (`week0-2026-v4-strict-20260818-r2`).
- Private V4 rehearsal + V2/V3/V4 comparison CSV generated.
- 2025 betting simulation: +17.9 units combined (+3.1% ROI); +5.9 units
  value-add over baseline.

### Bug fixes (commit `33432e8`)

1. Runtime target guard: parent marks resolved environment for children.
2. Build-baselines: forward `--environment` to child script.
3. Subnormal BLAS warnings: flush subnormals to NaN, record warnings, keep
   non-finite outputs fatal.
4. Resultless rows: exclude canceled/unreported labeled games from training,
   baselines, and baseline-join guard. Fix refit blend-weight variant nesting.

### Stage 2 — Launch decision

- Created `conf/weekly_bets/v4_2026.yaml` (commit `fe017b9`).
- V4 readiness passed in Preview; V4 published and activated (run
  `2026w0-3e4fa1b9b07d`).

### Stage 3 — Production setup

- Production Neon: migrations 0002–0008 applied; catalog hydrated from Preview.
- Production `cks_prod_web` role created (read-only, LOGIN).
- Production R2: `CFB_R2_*` env vars pointed at the preview bucket.
- `publish-week ENV=production` succeeded: run `2026w0-79ec2aebcb00` (8/8
  predicted, 8/8 lined, 0 high-confidence).
- Vercel production deployed: `https://c-ks-picks-cfb.vercel.app` (HTTP 200,
  market mode, 8 games with lines and kickoff times).
- `/api/health` verified: status=ok, active run published, coverage 8/8/8.

## Files Modified

- `src/cks_picks_cfb/data/runtime.py` — resolved-target marker
- `src/cks_picks_cfb/ops/__main__.py` — set marker + forward --environment
- `src/cks_picks_cfb/models/regime_training.py` — subnormal flush + warning policy
- `src/cks_picks_cfb/model_bundle_v3.py` — warning policy in inference
- `src/cks_picks_cfb/models/baselines.py` — exclude resultless rows
- `src/cks_picks_cfb/models/training_policy.py` — exclude resultless labeled rows
- `src/cks_picks_cfb/features/point_in_time.py` — baseline-join resultless carve-out
- `scripts/pipeline/assemble_model_ready_features.py` — validation carve-out
- `scripts/pipeline/refit_game_ordinal_bundle.py` — V4 blend-weight variant nesting
- `tests/test_runtime_target.py` — 3 new tests
- `tests/test_training_policy.py` — 1 new test
- `conf/weekly_bets/v4_2026.yaml` — V4 launch config (new file)
- `docs/plans/2026-08-18/week0-launch-execution.md` — status + amendments
- `.env` — production R2 credentials (not committed)

## Commits

- `33432e8` fix(pipeline): unblock V4 tournament
- `fe017b9` feat(config): add V4 2026 launch configuration

## Validation

- [x] `uv run pytest -q` — 355 passed, 2 skipped.
- [x] `uv run ruff check src/cks_picks_cfb scripts/pipeline tests`.
- [x] `uv run python contracts/validation.py`.
- [x] `uv run mkdocs build --quiet`.
- [x] `git diff --check`.
- [x] Preview readiness + publish (run `2026w0-3e4fa1b9b07d`).
- [x] Production publish (run `2026w0-79ec2aebcb00`).
- [x] Vercel production deploy + `/api/health` smoke test.

## Amendments and Blockers

- Plan contract amended with 3 amendments (bug fixes, R2 config, tournament
  results). Stages 4–5 pending game week. Pick'em blocked on
  `CFBD_PREDICTION_TOKEN`.

## Handoff Notes

- **Resume at:** Stage 4 — rerun `publish-week ENV=production` as lines update
  during game week (Aug 25–29). Freeze before Aug 29 kickoff. Flip
  `CFB_PUBLICATION_MODE` to `predictions` on Vercel only after user approval.
- **Watch out for:**
  - The AS_OF timestamp must be set ~5 minutes ahead of the publish run so the
    market capture falls before the cutoff.
  - `catalog.quality_results` in production Neon was truncated (preview-specific
    data); it will repopulate as production audits run.
  - The stale `.env` `PREVIEW_DATABASE_URL` (line 34, pointing at deleted
    `ep-delicate-sun` branch) should be removed; Preview operations use the
    Keychain wrapper.

**tags:** ["modeling", "v4", "tournament", "production", "vercel", "week0", "launch"]
