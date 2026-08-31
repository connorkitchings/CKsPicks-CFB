# Week 1 Operations

- **Status:** In Progress
- **Created:** 2026-08-31
- **Planner:** Fast-path (documentation + established operational commands)
- **Approval source:** User approved implementation plan on 2026-08-31.
- **Commit policy:** Propose commit after docs and session log are complete;
  user executes git operations. Operational commands (freeze, close, publish)
  require user execution from terminal.

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

### A2. Close Week 0 (scoring) — **Wait until Tuesday Sept 2**

CFBD takes ~24–48 h to finalize all game scores. Running close-week on
Sunday/Monday produces `away_points`/`home_points` missing errors because
not all scores are recorded yet. Run on Tuesday Sept 2:

```bash
make close-week YEAR=2026 WEEK=0 \
  AS_OF=2026-09-02T14:00:00Z ENV=production
```

This writes `prediction_grades` and derives `system_stats`. If any games
were canceled, add `CANCELLATION_WAIVERS="game_id:reason"`.

### A3. Verify close (Tuesday)

```bash
curl https://c-ks-picks-cfb.vercel.app/api/health
```

Health should report `state: scored` for the Week 0 run.

## Stage B — Prepare Week 1

### B1. Ingest Week 0 results

```bash
make ingest-week YEAR=2026 WEEK=0
```

Captures final scores and outcomes for all Week 0 games into R2.

### B2. Build Week 1 Gold (preview first)

Set AS_OF to ~5 minutes ahead of when you run it:

```bash
zsh scripts/ops/with_preview_env.sh make prepare-week \
  YEAR=2026 WEEK=1 AS_OF=2026-09-01T14:00:00Z ENV=preview
```

### B3. Preview readiness check

```bash
zsh scripts/ops/with_preview_env.sh make readiness \
  YEAR=2026 WEEK=1 AS_OF=2026-09-01T14:00:00Z ENV=preview
```

### B4. Preview publish

```bash
zsh scripts/ops/with_preview_env.sh make publish-week \
  YEAR=2026 WEEK=1 AS_OF=2026-09-01T14:05:00Z ENV=preview \
  CONFIG=conf/weekly_bets/v4_2026.yaml
```

Review coverage, predictions, edges.

## Stage C — Week 1 Production

### C1. Production publish (repeat as lines arrive Mon–Wed)

```bash
make publish-week YEAR=2026 WEEK=1 AS_OF=YYYY-MM-DDTHH:MM:SSZ \
  ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml
```

### C2. Update Vercel CFB_PUBLICATION_WEEKS to 0,1

In Vercel dashboard environment variables. The publish-week script fires
on-demand ISR revalidation automatically via CFB_REVALIDATION_URL.

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

- [ ] A1: Week 0 frozen
- [ ] A2: Week 0 closed/scored
- [ ] A3: Health confirms scored state for Week 0
- [ ] B1: Week 0 results ingested
- [ ] B2–B4: Preview prepare + publish verified
- [ ] C1: Production Week 1 publish (progressive)
- [ ] C2: Vercel CFB_PUBLICATION_WEEKS=0,1 live
- [ ] C3: Final freeze before Thursday kickoff
- [ ] C4: Health confirms Week 1 frozen + predictions active

## Risks and Notes

- `prepare-week` requires completed game outcomes in R2. If `ingest-week`
  has not captured finals yet, re-run after data is available.
- The Week 1 CFBD provider week may differ from the canonical week number.
  The market step handles the mapping automatically from the weekly policy.
- Pick'em for Week 1: requires a fresh CFBD_PREDICTION_TOKEN. Export and
  validate before submission; submission is a separate approval-gated step.
