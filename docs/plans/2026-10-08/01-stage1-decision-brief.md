# Stage 1 decision brief: what the corrected data work produced and how to release it

- **Status:** For decision
- **Created:** 2026-10-08
- **Contract:** [`2026-10-07/04-stage1-week5-corrected-data-finalization.md`](../2026-10-07/04-stage1-week5-corrected-data-finalization.md) (Task 9)
- **Evidence:** `docs/plans/2026-10-07/stage1-evidence/` (checksummed) and `session_logs/2026-10-08/01-stage1-completion.md`
- **Labels:** **verified** = re-derived or read back this session; **agent-reported** = a read-only subagent's reading of code that I did not re-open; **inference** = my reading, not tested.


> **Correction, 2026-10-08 (after the first Task 7 spike; verified, see `stage1-evidence/task7-findings.r2.json`).** The prediction-change figures in section 2, item 4 (mean margin change 3.12, 27 spread and 13 total flips, 38 grade changes, record 130-136-5) are **mostly not an effect of the data corrections.** The 6B replay applies the bundle refit by the 6A `offsets_refit` stage (call it B1: trained on the selected-design team states, 0.04-0.13 from the accepted forecast-v1 bundle `f80b63ef`). Production serves a different bundle (`30c4f1eb`, B2: the successor bridge refit on repaired game-at-cutoff states), which is 1.07-1.15 away from B1 in coefficient terms. Running the existing successor bridge builder unchanged on the corrected 6A frames gives a bundle within 0.07 (margin) and 0.13 (total) of the served one, and predictions from it differ from the **served** predictions by a mean of **0.33** margin points (max 1.51; 16 of 271 games over 1 point; the win side differs in 1 game) and 0.17 total points, versus 3.12 and 0.74 for B1. So the corrected data move predictions little; the large 6B deltas come from using a bundle that is not the one the site serves. The 6B outputs in Preview are internally consistent but are **not** a release candidate; the grade and record figures in this brief are not what a corrected successor release would show. Section 3's Task 7 estimate and section 5's route table stand, with this addition: the corrected bridge must come from the successor builder (B2), and the 6B replay must be rerun with it before any prediction, selection or grade figure is quoted.

## 1. What now exists (Preview only; Production is unchanged)

| Product | Where | Status |
|---|---|---|
| Week 5 ingest on the revised CFBD data | Preview R2 + catalog (`stage1-w5-ingest-20261007-r2`) | verified |
| Corrected 6A rebuild through Week 5 | `rebuild/6a/6a-rebuild-w5-20261007-r2/` (root raw sha `7865d353…`) | built, verified, published, idempotent retry wrote 0 |
| Task 4 receipt and comparison for that run | `rebuild/6a/6a-task4-w5-r2/` (root `3681c884…`, receipt `1cd439de…`) | all differences explained, 0 unexplained |
| Corrected 6B replay, Weeks 0-5 | `rebuild/6b/6b-replay-w5-20261008-r1/` (root `0b3308df…`) | built, verified, published, retry 0 writes |
| Corrected team stats, as-of 1-5 | local payload pair + verifier receipt | verified; not applied anywhere |
| Team stats, as-of 6 | local candidate payload (3,036 rows) | independent recompute passes; no database counterpart |
| Matchup tables Weeks 0-6 | local candidate and previous (Production) payloads | static gates 7/7, 0 unexplained differences; database gates not run |

## 2. What the work found

1. **Option B (adopt all revised CFBD data) cost nothing on ratings.** Raw and normalized Silver parents for Weeks 0-4 differ only in game 401856660 (Clemson at LSU): 71 plays, one `excitement_index`, 2 team-game-stat rows. Every Weeks 0-4 observation, prior and rating is bit-identical to the first corrected run; the game's PPA edits (69 rows) do not enter the PPP-only design. The only team-stat effect is last-digit float noise (11 cells for LSU and Clemson, about 1e-16).
2. **Historical 2015-2025 outputs reproduce.** Content is identical for all 40 historical Silver datasets and 50 of 50 Gold datasets apart from a lineage column (`source_versions`); ratings, forecast offsets and parity stages are byte-identical.
3. **One provider kickoff was revised after the lock froze:** Charlotte at Memphis (401862787) moved from 19:30Z to 15:00Z. The lock records it explicitly (old, new, source version); only that game changed, and no rating changed (4 `cutoff_utc` values move).
4. **6B reproduces exactly.** Predictions, selections, grades, offsets, frames and finals are value-identical to the first 6B run. Against what Production serves: mean margin change 3.12 pts (max 15.16), mean total change 0.74, **27 spread-lean and 13 total-lean flips, 40 selection sides and 38 lines changed (29 are the issue-13 fixes), 38 grade results changed.** Retrospective spread record **130-136-5** (served 128-139-4); overall 266-269-6 (served 265-271-5).
5. **Corrected team stats differ from Production only in the EPA/PPA family:** 1,328 value changes and 263 rank-only changes across 11,506 rows (same key set), the nullable-PPA effect.
6. **A finding about the catalog:** the corrected publishes created ties. For nine Silver datasets the newest `as_of` (2026-10-05) now has two or three validated versions for season 2026 (`byplay`, `drives`, `games`, `game_outcomes`, `plays`, `reconciled_team_game`, `source_reconciliation`, `team_game_stats`, `schedule_week_policy`). Anything that picks "the newest for 2026" is broken by `created_at` only. The weekly path uses explicit refs, so no release is affected, but the ingest quality check now reports it. Pin by version id wherever a consumer selects by dataset name.

## 3. What was deliberately not done

- **Task 7 (successor-format chain).** The 6B outputs are `retrospective_reconstruction` artifacts. The release code needs the successor chain: rating manifest, bridge manifest and verifier, forecast manifest, serving manifest, serving verifier, then the authorization. **Agent-reported (read-only subagent; I did not open the source-lock generator or the DDL):** the rating manifest is built by running the rating engine, not from state files, so a corrected-lineage version needs an importer plus its own independent verifier; the 6A bundle needs a new bridge manifest and verifier; the packaging, authorization and live-serving scripts hardcode Weeks 0-5 and the `20260929-p1` release tag and the old Week 5 run. Roughly 8-10 files and 15-25 functions plus tests. It is a build task, not a copy, and its design depends on the route chosen below.
- **Week-parameterizing the successor scripts and a successor-chain lock builder.** Same reason; the rebuild-lock extension (Task 3B) is a different, smaller tool and is delivered.
- **The matchup publisher's database gates.** They need the corrected rating manifest published and `v5_rating_snapshots` for it (agent-reported: published by `publish_v5_intended_update_ratings.py`; the gate compares each component with its snapshot to 1e-12 and requires the site's selected rating source to match). They follow Task 7.
- **No Production write of any kind.**

## 4. Code delivered (all on `dev`, tested, ruff clean, full suite 2,107 passed / 13 skipped)

Controller provenance amendment; release-payload builder, verifier and tests; cutoff-aware reconciliation; lock extension with recorded kickoff revisions; explicit-version Silver pin tool; scope-aware published comparison; 6B receipt checksum as a plan policy; parameterized team-stats builder with an as-of candidate; matchup candidate tool; ingest checks wired. **Weekly default:** `build_team_game_dataset.py` now keeps provider-missing PPA null by default (`--no-nullable-ppa` reproduces a zero-filled build). **D7f was already fixed** by `850ca383` (2026-10-04): `publish_to_db.py` writes a selection only when the lean is `home/away` or `over/under`; the contract's line numbers were stale. It has no end-to-end regression test (the selection insert sits inside the large `publish_week` body); that gap remains.

## 5. Release options

Calendar (verified earlier): Week 6's last game ends 2026-10-11T02:30Z; **Week 7 first kickoff 2026-10-13T23:00Z** (a freeze is due 22:00Z, about 1.5 days after Week 6 stabilizes); **Week 8 first kickoff 2026-10-20T23:00Z**. Week 6 stays on the hold screen (your earlier decision).

| Option | What it needs | Risk | When |
|---|---|---|---|
| **A. Corrected cutover at Week 8 (recommended)** | Task 7 chain for six replay weeks and the pending run N; Week 6 and 7 data through the same 6A/6B pattern; rating-snapshot publish; matchup republish; Preview rehearsal incl. rollback; the amended controller (provenance) is ready | Moderate, with a comfortable window (inference: about a week of build plus review; I have not timed Task 7) | Freeze and apply before the first Week 8 kickoff, 2026-10-20T23:00Z |
| **B. Corrected cutover at Week 7 (stretch)** | Same as A in 1.5 days after Week 6 stabilizes | High: the Task 7 build and its review would have to be finished before Oct 12 | Decide by Oct 11 |
| **C. Interim corrected replay with no pending week** | A change to `v5_batch_selection_v2.py` (it requires a frozen pending run N and certifies Weeks 0..N-1) | High: it weakens the single-use, kickoff-guarded controller; **not recommended** | n/a |
| **D. Display-only Week 6 / keep the hold screen** | Hold screen: nothing. Display-only: old-lineage refresh plus an explicit mode in the three kickoff-guarded scripts, throwaway if A follows, and a visible mix of lineages | Display-only: user-visible mixed lineage | Hold: now |

**Recommendation:** A, with B only if Task 7's design is accepted and built before Oct 11. Choose the Task 7 design before building: (1) an importer that expresses the 6A states in the existing rating-manifest format plus a verifier independent of the importer, or (2) re-running the existing engine on the corrected inputs so the existing builders and verifier apply unchanged (agent-reported as possible only for the rating step; the bridge and lock still need work). I have not tested which is smaller; a one-day spike on (2) would settle it.

## 6. Decisions recorded, nothing built

- **#8 stored prices are all -110 defaults:** keep the default but never present a price-based claim; before any staking work, find out whether the Odds API plan returns prices that the fetch drops (`data/the_odds_api.py`). Recommended: investigate the provider response in a read-only call when staking is next considered.
- **#11 lines are early captures from one or two books:** record that graded lines are not closing lines. Recommended: do not build closing-line capture now; if wanted later, schedule a capture 5-15 minutes before kickoff, starting with the Week N cutover so the evidence is prospective.
- **#9 neutral-site model:** unchanged, separate contract; Oklahoma-Texas in Week 6 is the first neutral game.

## 7. What I need from you

1. The release route (A recommended).
2. For A or B, the Task 7 design choice, or approval of a one-day spike to choose.
3. Commits of the work listed in the session log (by path), then the contract can be set to Implemented once Task 7 has an owner.
4. Whether to keep the as-of 6 stats and the Week 6 matchup tables as candidates (they have no consumer until a cutover).
