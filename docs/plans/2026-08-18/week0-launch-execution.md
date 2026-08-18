# Week 0 Launch Execution

- **Status:** In Progress (Stages 1–3 complete; Stages 4–5 pending game week)
- **Created:** 2026-08-18
- **Planner:** Sol (opencode session)
- **Approval source:** User approved the full plan, including V4 timebox with V2
  fallback, full production setup, Pick'em prep, and no further talent rechecks,
  on 2026-08-18.
- **Planning log:** `session_logs/2026-08-18/02-week0-launch-execution-planning.md`
- **Implementation log:** `session_logs/2026-08-18/03-v4-tournament-and-production-deploy.md`
- **Commit policy:** Plan committed separately; implementation commits remain
  user-controlled unless explicitly authorized in a session.

## Goal

Deliver a fully working public Week 0 launch on August 29, 2026: verified data
ingestion and transformations, a selected early-season model with a proven
fallback, rehearsed publish/freeze pipelines, a production Neon + Vercel
deployment in fail-closed market mode, and an approval-gated flip to
predictions (plus optional Pick'em submission).

## Current State (2026-08-18)

- Historical bootstrap, Silver/Gold, audits, and the weekly publish/freeze
  cycle are proven in Preview.
- Active frozen run `2026w0-a0edb9e72cb1` (V2 display-fallback bundle,
  `week0-2026-preview-20260814`) covers 8/8 opening-slate games with lines.
- V3 was rehearsed privately (2 spread / 7 total lean diffs vs V2).
- The V4 foundation (game_4 route, strict/reconstructed feature references)
  was committed 2026-08-18 (`a7d7ceb`) but the tournament has never run.
- All 8 Week 0 games route to `game_1`, so the launch decision is a
  game_1 spread/total decision with V2 as the proven fallback.
- CFBD talent is empty; `prior_only_fallback` is the accepted launch posture
  (no further rechecks this season).
- Migration `0008` (game_4) is committed but not yet applied to `preview-2026`.
- Local `artifacts/preview/` holds only working copies; durable refs and
  pipeline-run evidence live in Preview R2.

## Decisions

1. **Launch model:** Run the V4 tournament under an Aug 18–20 timebox; decide
   by Aug 22 on evidence. V2 remains the fallback if any gate fails. The
   active frozen V2 run is never mutated.
2. **Production:** Full production setup is in scope (Neon roles + migrations,
   production publish, Vercel production deploy in `market` mode).
3. **Pick'em:** Prep included; submission requires `CFBD_PREDICTION_TOKEN`,
   authenticated reconciliation, and a separate explicit approval.
4. **Talent:** No further rechecks; launch uses `prior_only_fallback`.

## Stage 1 — V4 tournament (Aug 18–20, Preview only)

1. Apply migration `0008` to `preview-2026`; verify the frozen run,
   `current_week`, and regime constraint are intact (additive change).
2. Resolve the current core/baselines refs from the active run's frozen
   `input_refs.json` in Preview R2 (or the Neon catalog); never guess URIs.
3. Assemble strict V5 model-ready Gold with
   `PRESEASON_FEATURES_REF_URI=artifacts/preview/refs/v4/strict-preseason-team-20260817.json`
   and `FEATURE_TRACK=strict`.
4. Generate and seal 2022–2024 selection candidates; evaluate to an immutable
   selection report with a frozen design SHA.
5. Run the single locked-2025 validation using the frozen selection SHA.
6. Refit the ten-route V4 bundle on 2021–2025 (established routes sourced from
   the V2 preview manifest).
7. Generate a private V4 Week 0 rehearsal artifact (no DB activation, mirroring
   the V3 rehearsal pattern) and the V2/V3/V4 comparison CSV.

**Timebox rules:** Any gate failure, non-finite output, or locked-2025
regression on game_1 routes stops V4; the launch ships V2. Failure evidence is
recorded in the session log before moving on.

**Exit gate:** Either a validated, refit V4 bundle plus comparison evidence, or
a documented stop with V2 confirmed as the launch model.

## Stage 2 — Launch model decision gate (by Aug 22)

Present locked-2025 metrics and the V2/V3/V4 comparison to the user. If V4 is
chosen: create `conf/weekly_bets/v4_2026.yaml` (or populate `model_bundle_v3`
in the Preview config) pointing at the new bundle URI+SHA, and rehearse a
publish in Preview. Otherwise keep `v2_preview_2026.yaml`. V2 stays wired as
the fallback either way.

**Exit gate:** User-selected launch bundle with a rehearsed Preview publish.

## Stage 3 — Production setup (Aug 21–25)

1. Create least-privilege production roles (migrator, pipeline, read-only web)
   mirroring the Preview setup; never reuse `neondb_owner` for the app.
2. Run `make migrate-db` against production (through `0008`), then
   `make contracts-check` and preflight.
3. Verify production R2 credentials and `ENV=production` routing before any
   publish; confirm source/destination bucket separation.
4. Publish the chosen launch run to production; verify row-level invariants
   (8/8 games predicted, 0 high-confidence rows).
5. Deploy Vercel production (Root Directory `web/`) with
   `CFB_PUBLICATION_MODE=market`, `CFB_PUBLICATION_SEASON=2026`,
   `CFB_PUBLICATION_WEEKS=0`, and the read-only web `DATABASE_URL`.
6. Smoke-test `/` and `/api/health`; confirm no model output leaks in market
   mode; resolve the Vercel upload file-count issue if it recurs.

**Exit gate:** Production site live in market mode with a published run and a
green health endpoint.

## Stage 4 — Game week (Aug 25–29)

1. Progressive `publish-week` reruns in production as lines arrive; each rerun
   creates a new immutable run and moves `current_week` on activation.
2. August 28: final publish → user review → `freeze-week` before kickoff →
   user flips `CFB_PUBLICATION_MODE=predictions` → redeploy → smoke test.
3. Pick'em: user supplies `CFBD_PREDICTION_TOKEN`; run `--validate-api
   --dry-run` reconciliation against the exact final CSV; submission
   (`--submit-api`) only after a separate explicit approval of game IDs and
   margins.

**Exit gate:** Frozen production run, predictions visible after approval,
Pick'em submitted or explicitly skipped.

## Stage 5 — Post-slate (Aug 30+)

`close-week` + scoring, health freshness checks, retrospective, and the Week 1
operating cadence.

## Validation

- Stage 1 mutation only in Preview; production untouched until Stage 3.
- Every mutating operation runs through `python -m cks_picks_cfb.ops` with an
  explicit `ENV`; failed steps activate nothing.
- Full quality gates (pytest, ruff, contracts, web build) before any repo
  change from Stage 2 config work.

## Stop Conditions

Inherited from
`docs/planning/2026_historical_bootstrap_week0_execution.md`: no 2020 lineage;
no untimestamped market value toward canonical markets/leans/grades; no
production write without explicit ENV and credential verification; no locked
2025 without a frozen design SHA; a failed step never activates anything.

## Definition of Done

- [x] Stage 1 exit gate reached (V4 validated or documented stop).
- [x] Stage 2 launch-model decision recorded.
- [x] Stage 3 production deploy green in market mode.
- [ ] Stage 4 frozen launch run; predictions flip only on approval.
- [ ] Session logs updated; plan status maintained.

## Amendments

### Amendment 1 — V4 tournament bug fixes (2026-08-18)

Four latent pipeline bugs were discovered and fixed during Stage 1 execution
(commit `33432e8`):

1. **Runtime target guard:** The ops parent rewrites `DATABASE_URL` to the
   resolved Preview URL for child steps; children that re-resolve then trip
   the Preview/production separation guard. Fix: parent marks the resolved
   environment via `CFB_RUNTIME_TARGET_RESOLVED` so children trust it.
2. **Build-baselines `--environment`:** The ops `build-baselines` step did
   not forward `--environment` to the child script. Fix: append the flag.
3. **Subnormal BLAS warnings:** macOS Accelerate BLAS emits spurious
   divide-by-zero/overflow FP flags on subnormal intermediates even when all
   outputs are finite. The V4 contract's blanket warning-fatality blocked
   every fit. Fix: flush subnormal inputs to NaN (numerically inert) and
   record RuntimeWarnings rather than raising; non-finite predictions and
   coefficients stay fatal.
4. **Resultless labeled rows + blend weights:** Two canceled/unreported
   games (2024 App State–Liberty, 2025 Army–Navy) had NaN targets that broke
   training and baselines. Fix: exclude resultless labeled-season rows from
   training, baselines, and the baseline-join guard. The refit's blend-weight
   lookup was also updated to handle V4's variant-nested weight structure.

### Amendment 2 — Production R2 configuration (2026-08-18)

Production R2 uses the same `cks-picks-cfb-preview` bucket as Preview
(immutable artifacts are checksummed and environment-neutral). Database
environments remain separated by Neon branch (`preview-2026` vs production).
The production Neon catalog was hydrated from Preview via COPY to register
the 7,163 source captures and 85 dataset versions needed by preflight.

### Amendment 3 — V4 tournament results (2026-08-18)

- Selection (2022–2024 OOF): 4 of 8 routes beat baseline (spread/game_1
  direct_catboost -1.43 MAE; total/game_2-4 blend -0.5 to -1.5 MAE).
- Locked 2025: all 8 routes passed anti-regression. Total blends genuinely
  improved; spread/game_1 regressed slightly (+0.61) but within tolerance.
- Betting simulation (legacy lines, research only): combined +17.9 units
  (+3.1% ROI); value-add +5.9 units over baseline. Totals games 3-4 are
  the real win (+14.0, +13.1 units). Week 0 game_1 routes are negative
  for both V4 and baseline.
- V4 bundle: `week0-2026-v4-strict-20260818-r2`, SHA
  `72429375bfa8c434c7d6fcb455bb9e22333af8c929c0cc3e832f0b80787bf25c`.
- Production run: `2026w0-79ec2aebcb00` (published, 8/8 games, market mode).
