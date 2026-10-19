# SOS/SOR as a season-release projection

- **Status:** Approved 2026-10-19 by the owner. Implementation authorization applies to this exact path, `docs/plans/2026-10-19/02-sos-sor-release-projection.md`; amendments are recorded below. Migration 0028 on Production, and every Production readback, still need separate explicit approval.
- **Created:** 2026-10-19
- **Related:** `01-mobile-week8-production-release.md` (the mobile and Week 8 release this follows); `session_logs/2026-10-19/02-desktop-restoration.md` (desktop layout and Charts cleanup, which this does not depend on)
- **Supersedes:** the per-request SOS/SOR in unpublished commit `6b3f07a1` (kept for reference on the local branch `sos-sor-draft`)

## Goal and observable completion

Strength of schedule (SOS), strength of record (SOR) and wins above average (WAA) are computed once per season release by the Python pipeline, stored in the release, certified by `verification.py`, and read by `/ratings` as release-scoped rows. The web app computes nothing. Done means:

- `uv run pytest tests/test_projection_resume.py` passes, including every hand-computed fixture below.
- `run_season.py prepare` passes all verification checks, including the new ones.
- `/ratings` on Preview, for a known team, shows a W-L (vs FBS) that matches its real FBS record, and an SOR rank that is plausible against a public résumé ranking.
- A release without the new table (the current release and every rollback target) still renders `/ratings`, with "—" in the résumé columns.

## Owner decisions this contract implements

- **Purpose:** résumé plus context. SOR is measured against an elite reference team. SOS is shown against both the elite and the average reference; elite is the primary.
- **FCS games:** excluded; W-L is labeled "vs FBS" and the SOR and SOS copy says FCS games are excluded.
- **Architecture:** a season-release projection, not a per-request computation in the web app.
- **Neutral sites:** ignored. The pinned V5 margin bridge has no neutral-site term, so SOS stays consistent with the model.

## Definitions

A rating period *t* is the preseason or a generation cutoff. **Every game, played or not, is scored with period *t*'s ratings.** The SOS of an already-played game therefore changes each week as the ratings learn; the methodology copy says so explicitly.

### Win probability

`p_ref,g` is the reference team's win probability in game *g* at that game's site (home, away or neutral as recorded), computed through the pinned V5 margin bridge and its calibration σ. The bridge coefficients are read from the pinned bridge artifact (`BRIDGE_SHA256` in `projection_serving.py`), never copied into constants.

### References

- **Average reference:** the mean offense rating and mean defense rating of all rated FBS teams in the period.
- **Elite reference:** the mean offense and defense rating of the period's top 25 teams, ranked by `overall_rating` descending. Ties at rank 25 are broken by `team` ascending, so the ranking is deterministic.
- **Self-exclusion:** a team is never measured against a reference that contains itself. For a team ranked 1–25, the elite reference is **the mean of the 24 other top-25 teams plus the 26th-ranked team**. For every other team, including the team ranked 26th, the reference is the plain top-25 mean. The 26th-ranked team is not self-excluded because it is not in the top 25.
- **The elite reference is computed per team, not shared across the period.** Each period has up to 26 distinct reference vectors: one for each of the 25 top teams, plus the plain top-25 mean used by everyone else. The cost is small (at most 26 means, about 140 teams, about 12 games each).

### Completed games (one shared rule)

A game counts as **completed at period *t*** when `kickoff_utc <= cutoff_utc` **and** the game has a final score in the release's `finals` frame. A game that kicked off before the cutoff but has no final score is not completed.

This single rule is used by the Python SOS/SOR/WAA, by the served W-L, and by the displayed game counts.

Verification of the rule against the existing definitions, to be completed and recorded before implementation starts:

- The `finals` frame is the source of the served `game_results` rows (`projection_serving.py`, built near line 471). Confirm that `game_results` takes final scores from `finals` unmodified, so the projection and the graded results agree on both the completed set and the scores.
- The declared score-reconciliation exceptions (`conf/season/2026/score_reconciliation_exceptions.json`, enforced by `score_reconciliation_problems` in `season/inputs.py`) allow a team-game's scoring-event total to differ from its final score. They do **not** alter `finals`. So the final score used here is the `finals` score even for an excepted game. `game_results` holds every final in the release with no cutoff filter, so parity is stated per period, not as set equality: **for each period *t*, the completed set equals `game_results` filtered by `kickoff_utc <= cutoff_utc` of *t*, with identical scores.** For the latest period this is every final whose kickoff is at or before its cutoff. The implementation adds a test asserting this for every served period of the current candidate, including every excepted game.
- If this check finds that grading uses a different set or different scores, stop and amend this contract rather than choosing silently.

### Metrics

- **SOS Played / Remaining / Full:** the mean of `(1 − p_ref,g) × 100` over, respectively, completed games up to *t*, games after *t*, and all games. Higher means harder. Reported for both references; elite is primary.
- **SOR (résumé):** let `P` be the probability that the elite reference team, playing this team's completed FBS schedule, finishes with at least this team's number of wins. `P` is computed exactly as a Poisson-binomial distribution over the completed games' `p_elite,g`. Display `SOR = (1 − P) × 100`, so higher means a stronger résumé, and show the rank alongside (1 is best). Store `P` as well.
  - Worked example: three games with `p_elite` of 0.9, 0.6 and 0.5, and a 3-0 record, give `P = 0.9 × 0.6 × 0.5 = 0.27` and SOR = 73.0. At 2-1, `P = 0.27 + (0.1·0.6·0.5 + 0.9·0.4·0.5 + 0.9·0.6·0.5) = 0.27 + 0.48 = 0.75`, so SOR = 25.0.
- **WAA (context):** `wins − Σ p_avg,g` over completed games, using the average reference.
- **Minimum evidence:** SOR and WAA are null (shown as "—") in the preseason and for any team with fewer than 3 completed FBS games. SOS Full and Remaining are shown from the preseason onward.
- **W-L vs FBS:** wins and losses over completed games against FBS opponents the period rates. Games against opponents the period does not rate (FCS) are excluded, and that exclusion is stated in the UI.
- **Ties:** FBS games cannot end tied (overtime). An equal final score in the input is a verification failure, not half a win. Betting pushes are grading outcomes and play no part here.

## Pipeline

- New `src/cks_picks_cfb/season/projection_resume.py`, called from `prepare.py` next to `projection_football.py`.
- It emits one row per (period, team) with `period_id`, `cutoff_utc`, `post_week`, `completed_games`, the reference descriptors, and the metrics above, for both references.
- `post_week` comes from `frames["current_ratings"]`, which already pairs `post_week` with `cutoff_utc` (`projection_football.py` near line 503). The row also carries the completed-game count.
- Retire `src/cks_picks_cfb/ratings/schedule_strength.py` into this module. Reuse its existing hand-computed expected values only for the average-reference SOS and WAA. Everything else needs new fixtures.

### Required test fixtures (`tests/test_projection_resume.py`)

All expected values are computed by hand and written into the test, not derived from the code under test.

1. The Poisson-binomial worked example above (3-0 gives SOR 73.0; 2-1 gives SOR 25.0).
2. **A team ranked inside the top 25** (for example rank 7): its reference equals the mean of the other 24 top-25 teams plus team #26, and differs from the plain top-25 mean.
3. **The team ranked 26th:** it is not self-excluded; its reference is the plain top-25 mean.
4. **A team ranked 30:** it uses the plain top-25 mean, and the fixture asserts that reference differs from the one used in fixture 2.
5. Per-team variants: a period with a full top 25 produces 25 distinct self-excluded references plus the shared one, and each rated team resolves to the correct one.
6. The rank-25 tie: two teams with equal `overall_rating` at ranks 25 and 26; `team` ascending decides, deterministically.
7. A game that kicked off before the cutoff but has no final score is not completed, and changes neither W-L, SOS Played nor SOR.
8. Preseason, and a team with fewer than 3 completed FBS games: SOR and WAA are null; SOS Full and Remaining are present.
9. An FCS opponent is excluded from W-L, SOS and SOR.
10. An equal final score raises a verification error.
11. Per-period completed-set parity: for each period, the completed set and scores equal `game_results` filtered by `kickoff_utc <= cutoff_utc`, including an excepted game (see "Completed games"). Earlier periods are strict subsets of the latest; the test does not require equality with the unfiltered table.
12. Fewer than 26 rated teams (a short rating table): the elite reference falls back to the mean of all rated teams other than the one being evaluated (or the plain mean of the rated teams for a team outside the top 25), and the fixture asserts the verification guard below does not fire.

## Schema

- Migration `0028_team_resume.sql` adds `season_release_team_resume`, keyed by `(release_id, period_id, team)`.
- Mirror the change in `contracts/schema.sql`, `schema.ts` and the web copy, then run `make contracts-check`.
- Register the table in `release.py` and `web/src/lib/season-release-query.ts` like the other `season_release_*` tables.

## Verification checks (`verification.py`)

- One row per rated team per served period.
- All probabilities in [0, 1].
- Wins plus losses equal the completed FBS games for that team and period, and no completed game has equal final scores.
- Every elite reference has 25 teams after self-exclusion. This is asserted only for periods with 26 or more rated teams; a period with fewer rated teams (a short table) is exempt from the count and instead checks that the reference is non-empty and excludes the evaluated team. Preseason has the full rated table, but SOR and WAA are null there regardless.
- The bridge SHA matches `PINNED_BRIDGE_SHA256`.
- Per-period completed-set parity with `game_results`: for each served period, the completed set equals `game_results` filtered by `kickoff_utc <= cutoff_utc` of that period (fixture 11 as a release-time check).

## Period labels

Store `post_week` and the completed-game count in the projection. Derive the Ratings period labels from them and delete the hand-maintained `WEEK_GENERATIONS` map in `web/src/lib/rating-periods.ts`. This also removes the unverified Post-Week 5 cutoff.

## Web

- `web/src/lib/v5.ts` reads the projection and computes nothing. Delete `web/src/lib/schedule-strength.ts`.
- `RatingsView` shows "W-L (vs FBS)", "SOR" (résumé), "WAA", and "SOS" with Played, Remaining and Full and an elite/average switch.
- The SOR and SOS headers get a one-line tooltip definition. "Elite" links to the methodology section that explains it as the top-25 average, a descriptive device that is not a model input.
- Methodology copy goes in `docs/modeling/possession_rating_methodology.md` and on the methodology page.

### Releases without the table

Until this ships, the current release and every rollback target have no `season_release_team_resume` rows, and before migration 0028 is applied the table does not exist.

- The web read detects this with `existsFrom` and `rowsOf` from `lib/db-result.ts`, following the AGENTS.md pattern for optional tables.
- When the table or its rows are absent, the résumé columns render "—" and the period labels fall back to date-based labels. The page must not error.
- Cover it with a fixture case (a ratings fixture with no résumé rows) and a Playwright assertion in `e2e/ratings.spec.ts`: the page renders, the résumé columns show "—", and nothing errors.
- Fixture mode bypasses the database, so also check it once against a real Preview database before migration 0028 is applied.

## Sequencing and manual steps (owner-run)

These happen before this contract's implementation and are not performed by the agent.

1. **Neon read, read-only:** `SELECT DISTINCT cutoff_utc` on the active Preview release's `season_release_v5_rating_snapshots`. Preview and Production serve the same candidate. No R2 access, no writes.
2. **Drop the unpublished SOS/SOR commit.** `6b3f07a1` is on no remote branch (`origin/dev` is at `b971da1f`).
   1. Run `git branch sos-sor-draft 6b3f07a1`.
   2. Confirm both preconditions: `git branch --list sos-sor-draft` prints the branch and `git log -1 --format=%h sos-sor-draft` prints `6b3f07a1`; and `git status --porcelain` on `dev` prints nothing. **Do not run the reset unless both hold.**
   3. Run `git reset --hard origin/dev` on `dev`.
3. **Add confirmed `WEEK_GENERATIONS` entries** (Post-Weeks 5–7) to `web/src/lib/rating-periods.ts` only for cutoffs the Neon read confirms. As of this draft **no entries have been added**. Put this in its own small commit, not inside the desktop layout commit. The message must say it is a data change: "adds verified Post-Week 5–7 rating-period labels; this map is temporary and is removed by the SOS/SOR release-projection contract." If it must share a layout commit, the commit body must say the same.
4. Merge the desktop restoration and Charts cleanup branch to `dev`, then release `dev` to `main`.
5. Implement this contract in a fresh task, and release it with the next weekly candidate.

## Release

Pass through the normal weekly runbook. Prepare from a clean commit with no commit between prepare and the last release step. Rehearse on Preview with independent readback. Read Production back with owner approval. Migration 0028 is applied to Preview first and to Production only with its separate explicit approval.

## Rollback and stop conditions

Rollback is the documented release rollback to the prior verified release; the additive table does not need dropping, and the web read tolerates its absence. Stop and amend this contract on: a completed-set mismatch between this projection and `game_results`; a bridge SHA mismatch; any verification failure; a numerical result that hand fixtures do not explain; an unexpected migration or schema difference.

## Out of scope

Model research, changes to the V5 bridge or its calibration, neutral-site adjustment, FCS opponent ratings, Charts publication, and changes to the Charts `schedule` chart (deleted in the Charts cleanup).

## Contract amendments

Deviations found during implementation are recorded here as dated amendments.

**2026-10-19 — stage 1 (`projection_resume.py`) resolutions.** Recorded by the implementer and pending owner confirmation:

1. **The average reference includes the team being evaluated.** The self-exclusion rule applies to the elite reference only. The "never measured against a reference that contains itself" sentence is read as covering the elite reference; "mean of all rated FBS teams" is taken literally for the average reference (this matches the draft's expected values for SOS and WAA).
2. **The margin is ratings-only.** The bridge's per-game `offset_margin` is not applied: it translates non-offense scoring for an actual game and has no meaning for a hypothetical reference team. The margin head has no venue coefficient, so neutral games use their recorded home/away labels.
3. **SOR rank ties** are broken by `overall_rank` ascending.
4. **`completed_games` and `scheduled_games` count FBS-opponent games only.** SOS Remaining covers games with `kickoff_utc` after the cutoff. A game that kicked off at or before the cutoff but has no final score counts in SOS Full only.
5. **Bridge coefficients are derived from the pinned artifact:** slope = coef / scale, intercept = intercept − Σ slope · center, sigma = sqrt(calibration_variance). Restated values (intercept 6.5442094507, home offense 8.5067766511, home defense 9.8433322793, away offense −10.2416516547, away defense −10.9680927057, sigma 17.8226309998) match the unpublished draft's constants.

Added row fields beyond this contract: `overall_rank`, `elite_reference_size`, `elite_reference_kind`, `average_reference_size`, `scheduled_games`, `sor_p`, `sor_rank`.

**Clarification to amendment 2 (owner review, same day).** "Ratings only" still includes the pinned bridge's intercept and the four rating slopes, so home field is applied: for two equal teams the home side wins with probability 0.6433 and the away side 0.3567 (asserted by a real-bridge test). Only the per-game `offset_margin` feature, which is data specific to an actual matchup and not a parameter of the pinned bridge, is not applied.

**2026-10-19 — display decisions (owner), after the Preview release was rehearsed.** The release data is unchanged; only what `/ratings` shows changed.

1. **SOR is displayed as a rank only** (for example "#14"). The score stays in the release and in a hover title, and the SOR sort is by rank.
2. **WAA is not displayed.** It stays in the release. The owner found it hard to understand and largely redundant with SOR and the record.
3. **Overall uncertainty is not displayed**, in the table, on phone cards or in the footnotes. The data stays in the rating rows.
4. **One SOS measure is shown, against the average FBS team,** in three columns: SOS Played, SOS Remaining and SOS Full. This supersedes "SOS is shown against both references, with elite primary" for the UI. The elite-reference SOS stays in the release but is not displayed. The elite reference is explained only as the yardstick for SOR. Elite SOS values run lower than average SOS values by construction (an elite team loses less often), which was the reason for the confusion.
5. **The W-L column is labeled "FBS W-L"** (FCS games excluded).

**2026-10-19 — release sequencing.** The Preview release `season-2026-ac3d6668440e1f3494ba92da` (prepared from commit `7f49dfd3`) was activated and independently read back: every value column of `predictions`, `prediction_grades` and `v5_rating_snapshots` equals the previous release's, and only release-ID-bearing identity columns differ. Because the display decisions above change web code, a candidate pinned to a later commit is prepared before Production, and that candidate is re-released on Preview first.

**2026-10-19 — after the Production release.** SOS is displayed as a rank (1 is hardest). The rank is computed in the web page from the released SOS values, ranking all FBS teams of the period before any search filter, competition ranking for ties. This is a presentation rank over certified numbers, not a new model quantity; it avoids a schema change. The ratings table sorts by clicking column headers; phones keep one Sort by menu. A stored SOS rank would require a new migration and a new candidate.
