# Direction: model first, site in the summer (2026-11-14)

Owner decision of 2026-11-14 on what to work on next. It sets order and timing only. Every item that changes pipeline, model, schema or Production behavior still needs its own contract in `docs/plans/` and owner approval. Live release and week state stays in [Current Status](../status.md); the item list stays in the [offseason backlog](offseason-2027-backlog.md).

## Decision

The model is what limits the product, so the model is the focus. The site gets no new feature or performance work until summer 2027. The weeks left in the 2026 season go to work that cannot be done later.

Owner answers that shaped it:

- The audience is mostly the owner and friends, so site polish has little payoff.
- Model research starts after the 2026-12-13 final close. This replaces the backlog's earlier 2027-01-01 start.
- The ambition level for the 2027 model (repair V5, or reopen the architecture) is decided after the first measured candidate results.

## Why

- The 2026 record through Week 10 is 271-279-9 on spreads (49.3%) and 267-289-2 on totals (48.0%), against a 52.4% break-even. In the 2025 holdout the market had lower error than V5 on both targets.
- The [prediction-error diagnostics for 2021 to 2025](../modeling/prediction_error_diagnostics_2021_2025.md) show structural gaps:
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

1. Research harness first. The lab corpus holds frozen ratings and bridge features only, so nothing upstream of the bridge can be tested. Build a control replay that re-estimates measurements, ratings and bridge for 2015 to 2025 and reproduces frozen V5 exactly (2025 margin MAE 14.1596, total MAE 13.3558). Re-baseline the closed V6 tournament as the second benchmark.
2. Candidate: venue. Use the stored neutral-site flag instead of `home_host=1.0`. The smallest change and the first full pass through the protocol.
3. Candidate: totals. First explain why predicted totals barely vary. Hypothesis to check, not a finding: nothing about pace or possessions per game reaches the bridge.
4. Candidate: preseason priors and the early-season blend.
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
- Phase 2, item 1: the control replay matches the frozen V5 MAE to four decimals.
- Each candidate is judged only by the thresholds in the research protocol.
