# V5 Ratings Successor: Current Status

> **Model development:** Complete and accepted on 2026-09-22.
> **Live 2026 forecasts:** The full-corpus inference bundle is pinned and a read-only Week 4 preflight passed. First current-state certification awaits stabilized Week 4 finals and refreshed, independently verified 07/08 parents.
> **Public site:** V5 replay is primary for 2026 Weeks 0–4 since 2026-09-25 (clearly labeled retrospective; W0–3 scored vs frozen quotes, W4 pending finals). V4 runs stay frozen/scored as the tested rollback. First *live* V5 activation still requires a verified live forecast, Preview serving rehearsal, rollback proof, and a separate activation decision.

The [manual weekly operator](../ops/v5_weekly_operator.md) and exact one-slate
release guard are implemented and rehearsed. Migration 0014 is applied on both
Preview and production with an empty authorization table in each, and
production V5 publication/selection now requires the restricted
`cks_prod_pipeline` login through `scripts/ops/with_production_pipeline_env.sh`
(both `session_user` and `current_user` are checked; the owner credential is
rejected). A fixture-class Preview operator rehearsal (cycle
`v5-rehearsal-2026w4`, repair run `repair-2026-rehearsal-20260925` on the
stabilized Weeks 0–3 inputs, 157/157/157 games) exercised preflight, apply with
independent verification, status, and idempotent resume. That rehearsal is not
live evidence. On 2026-09-25 the replay cutover released V5 to production under
separate exact replay authorizations (migration 0015, five rows, pipeline
SELECT-only): Weeks 0–4 select V5 replay runs, Weeks 0–3 are scored against
frozen pre-kickoff quotes (spread 72-82-3, total 67-54-0, labeled replay), and
Week 4 awaits its 58 certified finals for scoring. No live authorization or
prospective V5 activation has been created. The existing Weeks 0–3 replay
rehearsal does not replace the stabilized Week 4
07/08 refresh or a prospective 09/05 certification.

## What V5 is

V5 estimates each team's offensive and defensive scoring efficiency per possession, adjusts for opponents, and updates one continuous season-long rating as games finish. The selected candidate is `ppp__rho_0_60__exposure`: true points per possession, a 0.60 carryover prior, and exposure-weighted rating updates. A fixed Ridge bridge turns pregame team states and earlier-only non-offense offsets into predicted home margin and game total. The selected bridge uses an expanding fitting history, alpha 10 reference heads, and a verified through-2025 final fit. Neither bookmaker lines nor 2026 outcomes select or refit V5. See the [full methodology](possession_rating_methodology.md).

V5 ratings successor is unrelated to the V4 *feature schema v5* diagnostic.

## What is verified

The accepted lineage is Repair v2; r9 measurements `possession-v1-measurements-20260921-r9`; r9 ratings `possession-v1-ratings-20260921-11d59ee-r9cert`; bridge and through-2025 final fit `forecast-v1-20260921-5afd577-11c`; and independent 11D forecast verification (`4cfe5ef8…`). All four historical audit findings are closed. The [historical review](../research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md) independently accepted 7,318 prediction rows across 2022–2025 with zero exclusions.

For 2025, V5 margin MAE was 14.160 and total MAE was 13.356 across 934 games per target. Its 80% intervals covered 80.1% of margins and 82.0% of totals. The separate 762-game, postseason-recorded market diagnostic had lower market error than V5 for both targets. A like-for-like point-in-time V4 backtest under this evaluation protocol is unavailable. These results support completion and live testing; they do not establish that V5 is superior to V4.

## What remains operational

1. Contract 07 certified 157 2026 games through Week 3. Contract 08 independently verified the Weeks 0–3 rating replay `possession-v1-rating-replay-20260922-fcaa571`.
   The inference bundle SHA-256 is `f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b`; full-corpus equivalence covered 8,935 games. Preview holds 452 version-bound rating snapshots. Retrospective Weeks 0–3 forecast reconstruction is immutable replay `v5-replay-20260924-cb2252a` (157 games, zero gaps), pinned for serving, published and scored on Preview as run `2026w0-cb2252a0w0v5`, and explicitly selected after a same-week V4 rollback drill and V5 restoration (see the [rehearsal contract](../plans/2026-09-24/01-v5-replay-preview-rehearsal.md)).
2. Once Week 4 finals stabilize, refresh 07 and 08 under new immutable IDs. Contract 09 then applies the fixed V5 bridge to the next eligible slate, independently verifies its forecast and readiness, and repeats idempotently. The current [shadow runbook](../ops/v5_shadow_runbook.md) carries the exact commands and gates.
3. Rehearse V5's conversion to the existing public prediction format on Preview, checking schedule coverage, pregame timing, sign conventions, health, and V4 rollback. Present the evidence for a separate production activation decision. No Week 4 or later result is allowed to refit this V5 identity.
4. Keep immutable prospective freezes and outcome-versioned reports after launch. Six slates are a useful review window, not a prerequisite for declaring V5 developed or proposing a site cutover. Historical and diagnostic runs never become prospective observations.

## Contract map

The many numbered contracts record **how the evidence was produced**, not a list of unfinished model features. Contracts 00–04 built the original method; 10–12 audited, corrected, verified, and accepted the historical result. Contract 05 built live shadow tooling. Contracts 07–09 are the 2026 application chain. Contract 06 operates prospective monitoring. The [contracts index](../plans/index.md) links current procedures and the [archive](../archive.md) preserves completed and superseded decisions. The [current product transformation contract](../plans/2026-09-23/01-v5-product-transformation.md) tracks the remaining implementation work.
