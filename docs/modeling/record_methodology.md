# 2026 record methodology

> **Status:** active; updated 2026-10-15 for the atomic season controller. Live numbers and release IDs are in [Current Status](../status.md). Decisions are in the [decision log](../decisions/decision_log.md).

## One continuous record

The public 2026 record is one cumulative V5 record from Week 0, presented as if V5 had been active for the whole season. A selection is the model side against its chosen eligible quote, settled win, loss or push against the certified final. Spread and total records are separate. Every forecast with an eligible line can receive a grade; there is no edge threshold. Missing lines remain ungraded.

Started and reconstructed games stay on Games without a retrospective label. The point-in-time claim concerns the observations used by the forecast, not when the replay was built. Freeze receipts, original runs and reconstruction provenance remain audit evidence. “Prospective” describes predictions frozen before kickoff only; it does not define a separate public record or a six-slate admission requirement.

## Admission and verification

The controller requires a passing `season_verification_v2` report, produced during `run_season.py prepare`, covering both football preparation and serving projections. This replaces the legacy `audit_point_in_time_leakage.py` receipt as the operational release gate. A passing historical leakage receipt alone cannot authorize a release. Follow the [weekly runbook](../ops/weekly_runbook.md) for exact commands and release approval requirements.

| Check | Required behavior |
|---|---|
| Earlier-week evidence | Pregame ratings use only earlier-week games available by the rating cutoff; forecasts have a cutoff strictly before kickoff. Offsets use earlier-week observations. Post-week ratings may use that completed week's evidence. |
| Fixed identity | Model parameters retain the sealed 2015–2019 and 2021–2025 design and through-2025 fit; no 2020 or 2026 refit. |
| Feature integrity | Market fields do not enter model features; selected rating states match forecast features; predictions remain paired. |
| Football inputs | Required prior-week finals and play inputs are present; scoring events reconcile exactly per team-game unless an exact declared exception applies. |
| Provenance | Reads verify checksums; the model, revision, grading policy, code and configuration identities bind the release. |
| Serving integrity | Schedule, grades, quote links, summary records, rating lineage, matchup publication, venues and completed-game regimes pass independent projection checks. |

Score exceptions identify an exact `game_id`, `team` and reason in `conf/season/2026/score_reconciliation_exceptions.json`, pinned by the revision manifest. An unlisted mismatch or an unused exception fails preparation and verification. Malformed-score tags are not an automatic bypass, and there is no season-wide percentage waiver. Refresh the exceptions against new completed-week inputs; acceptance records a known limitation, not a repaired score stream.

## Market precedence and settlement

Selection is independent for each game and each target. Retained quotes captured strictly before kickoff take precedence (`retained_prekickoff`); the live week also applies the preparation `as_of` cutoff. The cumulative registered capture set retains real fetch times. When it supplies raw quotes, the selector keeps the latest eligible quote per provider, builds the canonical target snapshot using valid CFBD Consensus first and otherwise provider median, then fixes model direction against that canonical line. It shops only linked quotes for the chosen side under `model_side_best_quote_v2`; an exact directional tie is Away/Under. Spread points are stored home-signed and reversed for Away settlement. Selection records quote, snapshot, provider, point, price and benchmark provenance.

For a completed non-live game with no retained eligible quote, an explicitly supplied CFBD retrospective benchmark may be used (`cfbd_retrospective`). This is recorded separately; it is not authentic pre-kickoff capture evidence. Live-week selections never use that fallback. Without either permitted source, the game-target is ungraded. Fallback is per game-target, not an entire-week switch. Best-quote grading of reconstructed forecasts is the owner's intended policy; it is a retrospective comparison and does not prove the quoted execution was available when an original pick was published.

## Model page market comparison

The `/model` page also shows the market's error beside the model's for the same games. It is an accuracy comparison, not a betting result, and it never changes the official win-loss-push record, which stays settled at the best quote inside the canonical snapshot.

- **Canonical line:** the comparison reads the canonical pre-kickoff line (`market_snapshots.spread` and `total`) reached through `prediction_grades.market_snapshot_id`, per target. The displayed `predictions.home_team_spread_line` and `total_line` are the shopped best quote and are not used. Closing-line comparison is out of scope: no true closing line exists, and capture timestamps are fetch times.
- **Inclusion rule:** per target, a game is compared when it has a grade, both final scores, a model forecast and a non-null canonical line, and the line source is `retained_prekickoff`. The source is the suffix of `prediction_grades.grading_version` (`model_side_best_quote_v2:retained_prekickoff` or `:cfbd_retrospective`). Retrospective grades and unrecognized values (fail closed, shown as unknown) are excluded and their counts shown on the page. Pushes are included.
- **Definitions:** the forecast home margin is compared with the market-implied home margin, which is minus the canonical home spread (a pick'em is 0, never negative zero); totals compare the forecast with the canonical total. Error is prediction minus actual; average miss is the mean absolute error and lean is the mean signed error.
- **Tie rule:** the model is closer when its absolute error is strictly smaller than the line's, and the line when strictly larger. Exact ties are shown as "even" and excluded from the "closer in X of N games" denominator.
- **Big-miss threshold:** a miss counts when the absolute error is strictly greater than 28 points, so a miss of exactly 28 is not counted. The threshold was fixed before examining the 2026 tail numbers.
- **Break-even band:** the record caveat uses the 95% range 52.4% plus or minus 1.96 times the square root of 0.524 x 0.476 / n, where n is wins plus losses. It chooses the caveat wording only; it is not a hypothesis test or a verdict.

## Published state and the accepted quote correction

The current active release includes grades for the three early Week 6 games. On October 15, the owner confirmed registration of three Week 2–4 CFBD captures in Preview and accepted a rebuilt-quote candidate. The rebuilt data restore the real capture time for six Week 6 target quotes: games `401871090`, `401871051` and `401871066` have no eligible pre-kickoff quotes and become ungraded for both spread and total in that candidate. No late-quote exception is enabled to rescue them. The candidate remains pending activation; [Current Status](../status.md) holds both the unchanged public scoreboard and accepted candidate result. Other unregistered market captures remain pending owner review because adding quotes can change best-quote selections.

## Underdog picks

The Games page lists games where the model picks the market underdog to win outright. It is display only: it is about who the model picks to win, and no prices, payouts or staking appear because none are stored. It does not change the spread or total record above.

- **Underdog.** The market favorite is decided by the consensus pre-kickoff line (`market_snapshots.spread`, reached through the prediction's `market_snapshot_id`), not by the shopped line shown on the cards, so line shopping never turns a near pick'em into an upset. The model favorite is the team the forecast home margin favors. A game is an underdog pick when both margins are non-zero and disagree.
- **Exclusions.** A consensus pick'em (line 0) has no favorite, and a model margin under 0.05 is no call, matching the 0.05 rule the lean labels use. A game with no linked snapshot has no consensus line and is excluded everywhere; it is counted nowhere.
- **Display.** Only unfinished games in prediction mode, ranked by the gap between the model's margin and the market's implied margin (largest first), then earlier kickoff, then game id. Every qualifying pick is listed; the first 5 show and a "Show all N" button (collapsed on every load) reveals the rest. The list shares one card with "Biggest edges" and a control flips between them (Biggest edges is the default on every load); the control appears only when both have content, and the card is hidden when the week is final or nothing qualifies.
- **Straight-up grading.** A finished pick is graded on the model's winner against the actual final score. A tie is excluded.
- **Season record.** The record counts every qualifying underdog pick from every scored week (previously only each week's top 5, the same cap as "Biggest edges", which still applies to that record) and is shown as "x–y", with the card footer explaining that it is the straight-up record of picks won outright. Counting all picks avoids hiding the weaker-gap calls from the record. It is a small sample, reported as counts only.

## Limits and historical evidence

- Later provider corrections to past play-by-play were adopted. Event-time boundaries hold, but the corrected content may have been published after the original forecast week.
- CFBD capture timestamps are fetch times, not bookmaker posting times. Retained pre-kickoff eligibility proves capture timing only.
- Design and repair decisions were made with early 2026 outcomes known, although those outcomes do not fit parameters. Reconstructed records are not blind forward testing.
- A quote or final missing for one target leaves that target ungraded; a complete schedule does not imply complete grading.
- Non-monotonic score streams and declared reconciliation exceptions remain quality limitations; verification does not claim those feeds were repaired.

The October 10 leakage audit and `verify_cfbd_closing_lines.py` comparison remain historical evidence in `session_logs/2026-10-10/`. The comparison found 19 matches and 40 differences among 59 sampled provider/target captures; it did not support a blanket post-kickoff CFBD-line exception. Frozen Week 5 originals and their receipts remain immutable even where the public record now uses reconstructed forecasts. Training precedes prediction, no 2026 outcome refits the V5 identity, no freeze receipt is created after kickoff, and bookmaker data stays outside model inputs.
