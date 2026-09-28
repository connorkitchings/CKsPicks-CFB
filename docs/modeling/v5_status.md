# V5 Ratings Successor: Current Status

> **Model development:** Complete and accepted on 2026-09-22.
> **Live 2026 forecasts (2026-09-27):** After stabilized Week 4 finals, refreshed and independently verified 07/08 parents supported the verified Week 5 live forecast `forecast-v1-2026w5-live-r2` (56 games). Candidate picks were published to Preview as `2026w5-d6366e59fd43` and [authorized for production](../../session_logs/2026-09-27/06.md).
> **Public site:** V5 best-quote replay is selected for 2026 Weeks 0–4; Week 4 is scored. The [refreshed Week 5 live run](../../session_logs/2026-09-27/14-week5-line-refresh-candidate.md) `2026w5-5d436e58c072` is selected in production (56 predicted games, all 56 with spread and total lines). The earlier Week 5 V5 run is the immediate same-week rollback; V4 runs remain frozen/scored for prior slates.

The [manual weekly operator](../ops/v5_weekly_operator.md) and exact one-slate
release guard are implemented and rehearsed. Migrations 0014 and 0015 and
separate replay authorizations enabled the Weeks 0–4 production replay cutover;
the Week 5 live run used its own exact authorization. Future live publications
require separate exact authorizations.
Production V5 publication/selection requires the restricted
`cks_prod_pipeline` login through `scripts/ops/with_production_pipeline_env.sh`
(both `session_user` and `current_user` are checked; the owner credential is
rejected). A fixture-class Preview operator rehearsal (cycle
`v5-rehearsal-2026w4`, repair run `repair-2026-rehearsal-20260925` on the
stabilized Weeks 0–3 inputs, 157/157/157 games) exercised preflight, apply with
independent verification, status, and idempotent resume. That rehearsal is not
live evidence. The production replay selection is retrospective for Weeks 0–3;
Week 4 closed after 58 certified finals on 2026-09-27. The refreshed 07/08
parents and independently verified Week 5 forecast supported the authorized
Week 5 production release.

## What V5 is

V5 estimates each team's offensive and defensive scoring efficiency per possession, adjusts for opponents, and updates one continuous season-long rating as games finish. The selected candidate is `ppp__rho_0_60__exposure`: true points per possession, a 0.60 carryover prior, and exposure-weighted rating updates. A fixed Ridge bridge turns pregame team states and earlier-only non-offense offsets into predicted home margin and game total. The selected bridge uses an expanding fitting history, alpha 10 reference heads, and a verified through-2025 final fit. Neither bookmaker lines nor 2026 outcomes select or refit V5. See the [full methodology](possession_rating_methodology.md).

V5 ratings successor is unrelated to the V4 *feature schema v5* diagnostic.

## What is verified

The accepted lineage is Repair v2; r9 measurements `possession-v1-measurements-20260921-r9`; r9 ratings `possession-v1-ratings-20260921-11d59ee-r9cert`; bridge and through-2025 final fit `forecast-v1-20260921-5afd577-11c`; and independent 11D forecast verification (`4cfe5ef8…`). All four historical audit findings are closed. The [historical review](../research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md) independently accepted 7,318 prediction rows across 2022–2025 with zero exclusions.

For 2025, V5 margin MAE was 14.160 and total MAE was 13.356 across 934 games per target. Its 80% intervals covered 80.1% of margins and 82.0% of totals. The separate 762-game, postseason-recorded market diagnostic had lower market error than V5 for both targets. A like-for-like point-in-time V4 backtest under this evaluation protocol is unavailable. These results support completion and live testing; they do not establish that V5 is superior to V4.

## What remains operational

1. Contracts 07 and 08 were refreshed and independently verified through Week 4: 215 completed games and 860 rating states under `possession-v1-measurements-20260927-w4` and `possession-v1-rating-replay-20260927-w4`. V5 ratings were projected to Preview and production Neon.
2. Weekly ratings history is complete: independently verified post-Week 0/1/2 generations (`possession-v1-rating-replay-2026w{0,1,2}`, 8/51/100 games) join the certified post-Week 3/4 generations in production, serving six week tabs with priors backfill for teams yet to play. Fresh W3/W4 reruns reproduced the certified generations bit-for-bit and were never projected. See the [history replay contract](../plans/2026-09-27/05-weekly-ratings-history-replay.md) (Implemented).
2. Contract 09 produced and independently verified Week 5 live forecast `forecast-v1-2026w5-live-r2` (112 target predictions across 56 games). Preview candidate run `2026w5-d6366e59fd43` contains 56 games, 34 with market quotes at publication. Follow the [weekly operator](../ops/v5_weekly_operator.md) and [weekly pipeline](../ops/weekly_pipeline.md) for further line refreshes and readiness checks.
3. The initial exact Week 5 release authorized `2026w5-d6366e59fd43` with 34 lined games. A fresh capture found spread and total lines for all 56; a separately authorized exact packet then published and selected `2026w5-5d436e58c072`. Recheck markets and freeze the reviewed run before first kickoff (2026-10-02 00:00Z), subject to the existing lead-time gate. No Week 4 or later result may refit the fixed V5 identity.
4. Keep immutable prospective freezes and outcome-versioned reports after live activation. Six slates are a useful review window, not a prerequisite for declaring V5 developed or proposing prospective activation. Historical and diagnostic runs never become prospective observations.
5. **Best-quote line policy (`model_side_best_quote_v1`) — unified 1.0 no-bet rule live (2026-09-26).** Edges below 1.0 point publish no lean for either target (artifact "No Bet" labels authoritative; quote lineage kept); totals in [1.0, 1.5) display a side without a grade; the total grade threshold stays 1.5. All five 2026 weeks serve the rebuilt runs (`2026w{0..4}-v5replay-bestquote-20260926-r3`, authorized under `v5-bestquote-replacement-review-2026-09-26`): 270 W0–3 grades (146 spread + 124 total; 11 sub-1.0 spread grades removed vs the prior batch), every line a real market tick. Week 4 closed with 97 graded rows after certified finals. V4, original, and `-r2` runs stay frozen/scored as audit records and rollback targets. See the [no-bet contract](../plans/2026-09-26/02-unified-no-bet-threshold.md) (Implemented).


## Contract map

The many numbered contracts record **how the evidence was produced**, not a list of unfinished model features. Contracts 00–04 built the original method; 10–12 audited, corrected, verified, and accepted the historical result. Contract 05 built live shadow tooling. Contracts 07–09 are the 2026 application chain. Contract 06 operates prospective monitoring. The [contracts index](../plans/index.md) links current procedures and the [archive](../archive.md) preserves completed and superseded decisions. The [current product transformation contract](../plans/2026-09-23/01-v5-product-transformation.md) tracks the remaining implementation work.
