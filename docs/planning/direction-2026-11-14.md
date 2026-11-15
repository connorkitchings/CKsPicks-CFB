# Direction: model first, site in the summer (2026-11-14)

Owner decision of 2026-11-14 on what to work on next. It sets order and timing only. Every item that changes pipeline, model, schema or Production behavior still needs its own contract in `docs/plans/` and owner approval. Live release and week state stays in [Current Status](../status.md); the item list stays in the [offseason backlog](offseason-2027-backlog.md).

## Decision

Amendment, 2026-11-15: the owner approved the [site redesign and analytical usability contract](../plans/2026-11-15/site-redesign-and-analytical-usability.md) and explicitly authorized its implementation. That contract is an exception to the summer-only timing below: existing-data site improvements may proceed now. It authorizes neither model changes nor deployment; new data coverage and predictive ranges remain separately scoped.

The model is what limits the product, so the model is the focus. The site gets no new feature or performance work until summer 2027. The weeks left in the 2026 season go to work that cannot be done later.

Owner answers that shaped it:

- The audience is mostly the owner and friends, so site polish has little payoff.
- Model research starts after the 2026-12-13 final close. This replaces the backlog's earlier 2027-01-01 start.
- The ambition level for the 2027 model (repair V5, or reopen the architecture) is decided after the first measured candidate results.

## Why

- The 2026 record through Week 10 is 271-279-9 on spreads (49.3%) and 267-289-2 on totals (48.0%), against a 52.4% break-even. In the 2025 holdout the market had lower error than V5 on both targets.
- The [prediction-error diagnostics for 2021 to 2025](../modeling/prediction_error_diagnostics_2021_2025.md) show structural gaps. Correction, 2026-11-14: these describe Historical V5 (the 2026-09-21 frozen model) and have not yet been established for Operational V5, the intended-update model that serves the site; see the [baseline audit and analysis framework](../plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md). Treat them as hypotheses until that audit confirms them. Update, same day: the audit scored Operational V5 on 2022 to 2025 with earlier-only fitting and confirmed flat totals (predicted totals vary by 1.57 points) and the early-season margin bias (+7.51 before a team's first game); the neutral-site margin bias is smaller than first reported: 202 of the 328 neutral-site games were postseason games forecast from priors alone, and on the 126 regular-season neutral-site games the bias is -2.69. The owner excluded postseason games from the benchmark on 2026-11-15.
    - Totals: predicted totals have a standard deviation of 1.43 points, so a totals lean is close to asking whether the market line is above or below about 56. Predictions also run 2.4 points high in every slice.
    - Venue: every game is forecast as a home game; neutral-site margin bias is -4.32 points over 328 games.
    - Early season and mismatches: margin bias is +6.79 before a team's first game and +3.01 in non-conference games; Week 1 to 3 margin MAE is about 1.4 points above the rest of the season.
- V5 is frozen for the 2026 record, so no model change can ship in-season. What can be lost in-season is data and evidence.

## Phase 1: now to 2026-12-13 (protect the season and the holdout)

In date order.

1. Sunday 2026-11-15: the Week 11 to 12 close runs unattended. No code pushes to `dev` before or during it.
2. Monday 2026-11-16: after the close, push `dev` and rehearse the Monday kickoff-time refresh on Preview with `skip_production` ([contract](../plans/2026-11-12/06-monday-kickoff-time-refresh.md)).
3. Tuesday 2026-11-17 to Thursday 2026-11-19: release `dev` into `main` (regular-season end state, near-kickoff capture workflow, rollback readback fix, kickoff refresh, small site fixes). It must land before 2026-12-12 regardless; landing it this week makes item 4 possible.
4. Before Saturday 2026-11-21: finish the [near-kickoff capture contract](../plans/2026-11-12/01-near-kickoff-line-capture.md) (dry run, Preview capture check), then set `CFB_NEAR_KICKOFF_CAPTURE_ENABLED=true`. Closing lines for Weeks 12 to 15 cannot be reconstructed later. If the release slips, capture by hand per the [runbook](../ops/weekly_runbook.md#near-kickoff-capture-analysis-only).
5. Any midweek window outside a weekly run: the Production rollback drill (never run).
6. Approve and implement the [holdout replay contract](../plans/2026-11-12/05-holdout-replay-readiness.md): the re-prepare check for every manifest and the export tool before 2026-12-13; per-manifest exception pins wait for the 2027 rollover.
7. Owner action: provision the private research bucket and `CFB_R2_LAB_*` credentials in Cloudflare.
8. Sunday 2026-11-29: watch the Week 13 to 14 close (the provider schedule had no Week 14 games on 2026-11-11).
9. Sunday 2026-12-13: final close, then run the holdout export and record its hash.
10. Decide whether rule R4 plus the quarter-line check becomes the next-model scoring rule ([score-attribution investigation](../modeling/score_attribution_investigation_2026.md)). Only the decision is needed now.

## Phase 2: from 2026-12-14 (model research)

Run under the approved [research protocol](../plans/2026-11-12/02-offseason-research-protocol.md); 2026 stays unseen until a candidate is frozen.

1. Baseline audit first (corrected 2026-11-14; the earlier text said a research harness had to be built, which was wrong). Much of the research code exists in `src/cks_picks_cfb/ratings_lab/`, but it pins Historical V5, most of its inputs are not available offline, and no historical replay of Operational V5 exists. Follow the work order in the [baseline audit and analysis framework](../plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md): baselines and inventory, replay parity, chronological baselines and scoring accounting, then bounded experiments.
2. Bounded experiment: venue. Use the stored neutral-site flag instead of `home_host=1.0`.
3. Bounded experiment: totals. Update 2026-11-15: the audit found the cause is small fitted total coefficients plus offense-defense cancellation, and that possession volume (eligible regulation possessions) is not the missing input; game totals vary with scoring efficiency. The totals experiment needs redefining before it runs.
4. Bounded experiment: preseason priors and the early-season blend.
5. Checkpoint: with measured gains from items 2 to 4, decide between shipping a repaired V5 and reopening the architecture.
6. After the checkpoint: measurement repairs (score attribution, garbage-time rule, turnover margin, historical EPA replacement).
7. Freeze the candidate, score 2026 once on the holdout export, refit through 2026, then the 2027 rollover list (backlog section C) and a Week 0 Preview rehearsal.

## Phase 3: summer 2027 (site)

Batch site work just before the season, when it can present the new model: [web read performance](../plans/2026-10-29/01-web-read-performance.md) (measure first), explainability and market-comparison content, any postseason support, and the turnover factor on the matchup card.

## Not doing

- New site features or performance work during the rest of 2026.
- Any change to V5 or the 2026 record, or any model choice informed by 2026 results.
- The deferred data backlog, except where a Phase 2 candidate needs it.

## Done when

- Phase 1: `main` contains the end-state and capture code; near-kickoff captures exist for Weeks 12 to 15; the rollback drill evidence is logged; every 2026 manifest re-prepares or is listed with a reason; the holdout export hash is recorded.
- Phase 2, item 1: the completion criteria of step 2 in the baseline audit contract are met (row-level reproduction, documented operational equivalence, temporal rule across the dependency chain).
- Each candidate is judged only by the thresholds in the research protocol.
