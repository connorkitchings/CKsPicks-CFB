# Two-week preparation for the 2027 model

- **Status:** In Progress (2026-11-19)
- **Approval:** Owner authorized the plan in the November 19 Codex session.
- **Implementation log:** `session_logs/2026-11-19/01-model-head-start.md`
- **Commit policy:** Local research changes on `dev`.

## Totals preparation

The [totals experiment declaration](../../modeling/offseason_totals_drive_sample.md) specifies the comparisons, inputs and thresholds. Assemble a historical point-in-time sample of scoring opportunities per eligible drive, points per opportunity, and starting field position for both teams and their opponents. Report coverage by season and completed-game stage, compare definitions with the V5 exclusions and closed V6 inputs, and reconcile an ordinary game, a zero-opportunity game and an excluded-scoring game. Freeze the experiment setup before fitting a challenger. Candidate fitting begins after the December 13 final close.

Use Operational V5 as the engineering reference for the totals experiment and the training mean as a sanity check. The governing promotion protocol still needs explicit approval of the proposed Operational V5 comparator and season/week paired resampling. The proposed interval is two-sided 95%, with paired games kept inside resampled week blocks within each season, 2,000 draws and the existing seed. Preserve season representation and document cross-week team dependence as a limitation. Keep the current promotion thresholds until the protocol is amended.

## Weather pilot

Run the Week 13 and Week 14 captures at 11:45 a.m. Eastern on November 22 and 29, ahead of the noon dispatch. The Codex desktop automation performs the two captures on this Mac. Review the resulting receipts against each slate's initial rollover manifest. A forecast counts at issuance when the provider issue time precedes or equals retrieval, retrieval precedes or equals the certified forecast cutoff, and retrieval precedes kickoff. The kickoff must fall within the saved forecast hour, with wind and precipitation probability present. Receipt coverage refers to the kickoff and venue in the capture-time CFBD schedule. Check any later kickoff or venue revisions against that receipt before treating a captured forecast as valid for the changed game.

For each slate the collector selects the first ten known outdoor FBS-vs-FBS games with a known kickoff, ordered by kickoff and game ID. The receipt records other games, including unknown roof classifications. Raw response files and receipts live in a Git-ignored local research evidence directory because lab R2 credentials were unavailable in the checked environment. Keep that directory through the pilot and copy it to private research storage once provisioned.

A November 19 rehearsal saved ten Week 12 kickoff-hour forecasts. All ten arrived after the published cutoff. A separate archival check returned wind and precipitation for Ohio Stadium at 17:00 UTC on November 30, 2024, from the November 24 00:00 UTC ECMWF IFS run. The [Single Runs archive](https://open-meteo.com/en/docs/single-runs-api) starts in March 2024 for that model and requires an allowance for distribution delay. It supports a same-lead-time feasibility check for 2024–2025. The [NOAA NDFD archive](https://www.ncei.noaa.gov/products/weather-climate-models/national-digital-forecast-database) is the longer-history source to investigate for 2022–2025. Coverage and issue-time provenance across the full historical window remain to be established.

## Frozen margin replay

Preserve the P3 reference bundle and input hashes. Verify historical game-level parity and the early FBS-vs-FBS gain using explicit development seasons. Reject holdout requests before input access. Document the evidence for rating recipe identity and retain the 2027 forward-test specification.

## Capture and holdout follow-through

Check near-kickoff receipts against the eligible game universe using actual capture-to-kickoff lead times. Review the Week 14 schedule at the November 29 rollover, and verify the final manifest and export hash after the December 13 close. Keep near-kickoff quotes analysis-only. The [holdout preflight](../2026-11-12/05-holdout-replay-readiness.md#2026-11-19-export-preflight) identified an existing Week 7 cutoff violation that requires a contract decision before export.

## Acceptance

The totals sample, written experiment, and historical P3 replay are reproducible from pinned inputs. The weather report accounts for both scheduled slates, including any empty schedule or missing vintage. The final 2026 holdout export requires a successful final close and a repeatable hash.
