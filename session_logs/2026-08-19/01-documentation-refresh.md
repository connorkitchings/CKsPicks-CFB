# Session: Full Documentation Refresh — Status Accuracy + V2-Era Disposition

## TL;DR

- **Worked On:** Reviewed all ~95 docs against the authoritative post-launch
  state (V4 tournament complete, production live 2026-08-18), then executed a
  full-repo documentation refresh: status/roadmap corrections, contract
  closures, decision-log backfill, assistant-doc rewrites, a new production
  runbook, and superseded banners on V2-era docs.
- **Outcome:** Documentation now matches reality — buildout complete, launch
  contract Stages 4–5 remaining. 58 files modified + 1 new file
  (`docs/ops/production_runbook.md`). MkDocs nav restructured around the 2026
  season.
- **Plan Contract:** N/A (fast path — documentation-only change with
  established patterns; user approved the full plan in-session)
- **Approval / Status:** User approved scope decisions 2026-08-19: banner-in-place
  + one new runbook; full decision-log backfill; all tiers in one session;
  display-only posture section for betting policy.
- **Blockers:** None.
- **Next:** Stage 4 game-week operations (Aug 25–29) per
  `docs/plans/2026-08-18/week0-launch-execution.md`.

## Context and Decisions

- Authoritative state sourced from `docs/plans/2026-08-18/week0-launch-execution.md`
  (Stages 1–3 complete), session logs 2026-08-18, and the V4 launch artifacts:
  bundle `week0-2026-v4-strict-20260818-r2` (design SHA `ae34ddc7…`), config
  `conf/weekly_bets/v4_2026.yaml`, production run `2026w0-79ec2aebcb00`
  (8/8 games, market mode, 0 high-confidence).
- Phase completion dates sourced from session logs: Phase 2 → 2026-08-13,
  Phases 3–4 → 2026-08-14, Phase 5 (V4 tournament) → 2026-08-18.
- V2-era docs disposition (user decision): banners in place, no moves — avoids
  link breakage; one new as-built runbook replaces them operationally.
- Decision-log backfill: added 2026-08-16 (prediction-only promotion),
  2026-08-17 (strict/reconstructed feature references), 2026-08-18 ×2 (V4
  launch + prior_only_fallback; production deployment + publication gating),
  plus a reconciled 2025-08-10 entry formerly living only in the template.
- The template's two real decisions were moved into the log; the template now
  holds only placeholder structure.

## Work Completed

### Stage A — Status & roadmap accuracy
- `docs/planning/roadmap.md` — full status rewrite: timeline with actual
  completion dates, current-state section (production topology + V4 results),
  remaining work = launch contract Stages 4–5, blockers table updated (talent
  resolved by decision), counts fixed (355 tests, migrations 0002–0008).
- `docs/planning/2026_historical_bootstrap_week0_execution.md` — Phases 2–5
  marked ✅ COMPLETE with artifacts/exit-gate evidence; Phase 6 partial;
  resume point replaced with launch-contract Stages 4–5.
- `README.md` — status section, launch-contract + runbook links, repo URLs
  (`CKsPicks-CFB`), footer date.
- `AGENTS.md` — 2026 status section rewritten (buildout complete, prod live);
  R2-primary storage phrasing; migrations row (0002–0008, `make migrate-db`);
  dead paths fixed (`src/cks_picks_cfb/config/`, `features/pipeline.py`, ops
  module added); footer date.
- `docs/guide.md` — status/phases, production model table → V4 bundle,
  pipeline flows, ops/research sections, env setup (R2 primary), workflows,
  2025 metrics marked historical, repo URLs.
- `docs/index.md` — rewritten from V2-era nav to 2026 framing.
- Contracts closed: `2026-08-17/early-season-v4-modeling.md` → Implemented +
  Amendment 3 (completion via launch contract); `2026-08-15/games-1-3-modeling.md`
  → Superseded with lineage note.
- `docs/decisions/decision_log.md` — 5 new entries (see above);
  `decisions/README.md` highlights refreshed; `decision_template.md`
  placeholder-only.
- `docs/experiments/index.md` — 2026 model lineage table (V2→V3→V4 with
  outcomes), champion header, split-policy section fixed.
- `docs/modeling/early_season_regimes.md` — ten-route refit fix, sealed
  outcome (2026-08-18) section added.
- `web/README.md` — production URL/status, migrations → `contracts/migrations/`
  + `make migrate-db`, scripts table, structure tree, deploy section
  (`cks_prod_web`).

### Stage B — Assistant entry docs
- `.agent/CONTEXT.md` — full rewrite: Bronze/Silver/Gold lake architecture,
  ten-route regime design + V4 bundle, R2/Neon storage, real module paths,
  current conf inventory, 355-test suite, ops-machine production workflow.
- `.codex/MAP.md` — full regeneration against the actual tree (src modules,
  40+ pipeline scripts, conf groups, 54 test files, contracts, docs incl.
  plans/, find-by-task table).
- `.codex/QUICKSTART.md` — removed dead sections (dashboard,
  scripts/analysis, scripts/features); fixed model/experiment names; added
  `CFBD_PREDICTION_TOKEN`, `CFB_PUBLICATION_*`, production publish example;
  MLflow registry framed dev-only.
- `.codex/HYDRA.md` — directory tree, samples, and examples regenerated from
  current `conf/`; 2020 example removed; tuning section updated.
- `CLAUDE.md`/`GEMINI.md` — section inventory bullets fixed.

### Stage C — Ops accuracy
- `docs/ops/weekly_pipeline.md` — v4_2026 launch config, garbled sentence
  fixed, `ENV=production` example, shared-bucket R2 note, ten-route checksum
  language, production health URL, runbook cross-link.
- `docs/architecture/data_platform_2026.md` — deployment sequence marked
  executed with as-built topology; `model_bundle_v3` key naming.
- `docs/ops/data_paths.md` — historical banner + current pointer.
- `docs/ops/validation.md` — path fix, dead monitoring link removed.

### Stage D — Production runbook + V2 banners
- NEW `docs/ops/production_runbook.md` — as-built topology, weekly cycle with
  `ENV=production`, AS_OF guidance, freeze, publication-mode flip procedure,
  health checks, rollback via frozen-run reselection, Pick'em flow, failure
  modes, credential notes.
- Superseded banners on 12 V2-era docs: `deployment/*` (4),
  `ops/production_deployment.md`, `rollback_sop.md`, `monitoring.md`,
  `data_quality.md`, `planning/project_charter.md`, `betting_line_integration.md`
  (marked policy-prohibited), `parquet_migration_plan.md`,
  `modeling/calibration.md`.
- `mkdocs.yml` — nav restructured: "2026 Season" section, runbook added,
  legacy ops/process grouped as historical.

### Stage E — Light touches
- `docs/modeling/betting_policy.md` — new governing "2026 Current Posture —
  Display Only, Fail-Closed" section; V2 champion section marked historical.
- `docs/project_org/feature_registry.md` — 2026 V4 feature families table
  (prior_core active; 7 additive families unavailable-strict); V2 groups
  marked historical.
- Path/claim fixes: `features.md`, `advanced_features.md`,
  `data/pipeline_overview.md` (R2 Bronze flow), `process/hydra_guide.md`,
  `process/mlops_experimentation.md`, `process/ml_workflow.md` (banner +
  current commands), `process/checklists.md`, `process/data_science_navigator.md`.
- Banners: `process/experimentation_workflow.md` (superseded),
  `process/12_week_implementation_plan.md` (elapsed),
  `process/data_quality_workflow.md` + `adjustment_analysis_workflow.md`
  (proposed-never-implemented), `research/power_ratings.md` + PPR memo/PRD
  (not adopted), `docs/phase2_setup_guide.md` (completed; phase-name collision
  note), `history/REFACTORING_PLAN.md` (complete).
- `docs/modeling/evaluation.md` — header aligned to 2026 gates.
- `docs/architecture/cfbd_point_in_time_pipeline.md` — production promotion
  completed note.

## Files Modified

58 modified + 1 new (see `git status`): root entry docs (README, AGENTS,
CLAUDE, GEMINI), `.agent/CONTEXT.md`, `.codex/{QUICKSTART,HYDRA,MAP}.md`,
`web/README.md`, `mkdocs.yml`, and 50 docs under `docs/` incl. new
`docs/ops/production_runbook.md`. No code, config, contract, or pipeline
changes.

## Validation

- [x] `uv run mkdocs build --quiet` — exit 0 (twice, after nav restructure).
- [x] Stale-token grep sweeps — clean for: "Phase 2 next", "Phase 1 complete,
  Phase 2", "285 tests", `train_production_points_for`, "eight-route"
  (non-historical), `week0-2026-v3-preview`, `streamlit run`,
  `dashboard/monitoring`, `scripts/{analysis,features,validation,ratings}/`,
  `experiment=spread_catboost_baseline_v1`, `model=catboost` (bare),
  `tuning=catboost_optuna`.
- [x] Cross-link targets verified (launch contract, runbook, plan cross-refs).
- [x] `git diff --check` — flags only trailing double-space Markdown hard
      breaks on 6 lines, matching the pre-existing repo convention (verified
      against `git show HEAD:` originals).
- [x] No changes outside docs/entry-doc scope; worktree had no pre-existing
      changes (clean at session start on `codex/games-1-3-modeling`).

## Amendments and Blockers

- None. One editing slip during `mkdocs.yml` nav editing was immediately
  reverted (verified by subsequent build).

## Handoff Notes

- **Resume at:** Stage 4 game-week ops — progressive
  `publish-week ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml` as lines
  arrive (Aug 25–28); freeze before Aug 29 kickoff; user-approved
  `CFB_PUBLICATION_MODE=predictions` flip; optional Pick'em
  (`CFBD_PREDICTION_TOKEN`). See `docs/ops/production_runbook.md`.
- **Watch out for:** AS_OF ~5 min ahead of publish runs; roadmap dates for
  Phases 3–4 are session-log-derived (Aug 14) — adjust if better evidence
  emerges; `catalog.quality_results` in production Neon repopulates as audits
  run (expected).

**tags:** ["documentation", "roadmap", "status-sync", "v4", "production", "runbook"]
