# Week 1 Operations

- **Status:** In Progress — Stage A complete; Stage B complete; Stage C initial publish done; freeze + Vercel update pending
- **Created:** 2026-08-31
- **Updated:** 2026-09-02
- **Planner:** Fast-path (documentation + established operational commands)
- **Approval source:** User approved implementation plan on 2026-08-31; approved execution of validation, commit, and Preview Stage B on 2026-09-02.
- **Commit policy:** Propose commit after docs and session log are complete;
  operational commands run by assistant in preview, user executes production commands.

## Goal

Close out Week 0 cleanly and have Week 1 predictions frozen in production
before Thursday ~September 4 kickoff.

## Current State (2026-08-31)

- Production run `2026w0-55de0317120d`: state `published`, 8/8/8 coverage,
  last publish 2026-08-20. Never frozen.
- Week 0 games were played Aug 29–30, 2026.
- V4 bundle `week0-2026-v4-strict-20260818-r2` is the active production model.
- Vercel `CFB_PUBLICATION_WEEKS=0` (needs `0,1` after Week 1 is live).
- R1 ratings run in-flight at `e9edee5`, independent of this work.

## Stage A — Close Week 0

### A1. Freeze the Week 0 run ✅ Done 2026-08-31

`freeze-week` was run on 2026-08-31. Run `2026w0-55de0317120d` is now frozen.

### A2. Close Week 0 (scoring) ✅ Done 2026-09-02

`close-week` ran successfully on 2026-09-02. The Week 0 run is now `scored`,
`prediction_grades` were written, and `system_stats` were derived.

### A3. Verify close (Tuesday) ✅ Done 2026-09-02

Production `/api/health` reports `state: scored` for run `2026w0-55de0317120d`.
All 8 Week 0 games have completed results in `game_results`.

## Stage B — Prepare Week 1 ✅ Done 2026-09-02

### B1. Ingest Week 0 results ✅

`prepare-week` automatically ingested Week 0 plays and game_stats. Week 0 outcomes were already in R2 from the earlier `close-week` run.

### B2. Build Week 1 Gold (preview first) ✅

Succeeded with prepared Gold ref:
`artifacts/preview/pipeline-runs/c9b80bf11d364c84978f2c4203dd1165/point_in_time_matchups_ref.json`
(content_sha `30ac8b5d37719160ff9d751c`).

```bash
zsh scripts/ops/with_preview_env.sh make prepare-week \
  YEAR=2026 WEEK=1 AS_OF=2026-09-03T04:00:00Z ENV=preview
```

### B3. Preview readiness check ✅

Passed.

### B4. Preview publish ✅

Preview prediction run `2026w1-2ba9ea0d113d` is `published` with 43/43/43 coverage.

```bash
zsh scripts/ops/with_preview_env.sh make publish-week \
  YEAR=2026 WEEK=1 AS_OF=2026-09-03T04:10:00Z ENV=preview \
  CONFIG=conf/weekly_bets/v4_2026.yaml \
  PREPARED_GOLD_REF_URI=artifacts/preview/pipeline-runs/c9b80bf11d364c84978f2c4203dd1165/point_in_time_matchups_ref.json
```

## Stage C — Week 1 Production

### C1. Production publish (repeat as lines arrive Mon–Wed) ✅ Initial publish done 2026-09-02

Initial production run `2026w1-b2c739321e5d` is `published` with 43/43/43 coverage.

```bash
make publish-week YEAR=2026 WEEK=1 AS_OF=YYYY-MM-DDTHH:MM:SSZ \
  ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml \
  PREPARED_GOLD_REF_URI=artifacts/preview/pipeline-runs/c9b80bf11d364c84978f2c4203dd1165/point_in_time_matchups_ref.json
```

### C2. Update Vercel CFB_PUBLICATION_WEEKS ✅ Done 2026-09-02

Set to `0,1,2` via the Vercel CLI (redeployed production). Week 2 is
pre-authorized: the web app only shows weeks that have an activated run, so
listing 2 early is safe — the homepage keeps showing Week 1 until a Week 2
run is activated. `/api/health` now reports `weeks: [0,1,2]`.

### C3. Final production publish + freeze (by Thursday kickoff)

```bash
# Final publish ~5 min before your AS_OF
make publish-week YEAR=2026 WEEK=1 AS_OF=YYYY-MM-DDTHH:MM:SSZ \
  ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml

# User reviews run, then freeze:
make freeze-week YEAR=2026 WEEK=1 ENV=production
```

### C4. Smoke test

```bash
curl https://c-ks-picks-cfb.vercel.app/api/health
```

Expect: state frozen, Week 1 coverage, predictions mode active.

## Definition of Done

- [x] A1: Week 0 frozen
- [x] A2: Week 0 closed/scored
- [x] A3: Health confirms scored state for Week 0
- [x] B1: Week 0 results ingested
- [x] B2–B4: Preview prepare + publish verified
- [x] C1: Production Week 1 publish (progressive) — initial run published
- [x] C2: Vercel CFB_PUBLICATION_WEEKS=0,1,2 live
- [ ] C3: Final freeze before Thursday kickoff
- [ ] C4: Health confirms Week 1 frozen + predictions active

## Week 2 cadence (pre-authorized via CFB_PUBLICATION_WEEKS=0,1,2)

`prepare-week WEEK=2` cannot run until Week 1 games are final — it ingests
completed results for weeks 0..1 and the Gold it builds must include them.

1. Tuesday Sept 8 (after finals): `make close-week YEAR=2026 WEEK=1 AS_OF=... ENV=production`
2. `zsh scripts/ops/with_preview_env.sh make prepare-week YEAR=2026 WEEK=2 AS_OF=... ENV=preview`
3. Readiness → progressive production publish (no Vercel env change needed) →
   freeze before the next kickoff.

## Risks and Notes

- `prepare-week` requires completed game outcomes in R2. If `ingest-week`
  has not captured finals yet, re-run after data is available.
- The Week 1 CFBD provider week may differ from the canonical week number.
  The market step handles the mapping automatically from the weekly policy.
- Pick'em for Week 1: requires a fresh CFBD_PREDICTION_TOKEN. Export and
  validate before submission; submission is a separate approval-gated step.
