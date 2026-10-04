# Data integrity review: decision packet (D1-D9)

> **Authority update (2026-10-04):** this document preserves dated investigation/decision evidence. [Contract 04, Amendment 2](04-data-integrity-two-window-implementation.md#amendment-2-window-2-measurement-repair-and-prospective-cutover-2026-10-04) and its two appendices document the approved (2026-10-04) Window 2 scope. Earlier neutral-refit, single-batch and all-or-nothing allocation recommendations below are historical, not current instructions. Window 1 remains independent.


- **Status:** Reviewed. Evidence packet only; the user decisions are recorded below and [04-data-integrity-two-window-implementation.md](04-data-integrity-two-window-implementation.md) is the execution authority.
- **Created:** 2026-10-03
- **Author:** Claude (Sonnet 5.5) with the user, from the read-only investigation in [Week 5 data-issue investigation](02-week5-data-issue-investigation.md) (Phases A-F plus the sweep recorded in its Amendment 3).
- **Evidence:** [known data issues](../../data/known_issues.md) (issues 1-12) and the working notes in `artifacts/backups/2026-10-03/investigation/`. Analysis code is present in the worktree; this packet does not claim a commit state.
- **Writes performed:** none. Every query was read-only; every delta ran in memory.

## Escalation notice (the investigation's stop condition)

The investigation plan said to stop and escalate if a finding showed the served V5 ratings are wrong rather than merely thin. This packet is that escalation, stated precisely: the served V5 *inputs* carry two measured, one-directional biases (points lost in 27 quarantined plus 3 silently short team-games; EPA of 155 null-`ppa` plays counted as zero). The served ratings reproduce exactly from those inputs, so nothing was computed wrongly, but the inputs are biased. **No change to the served ratings, any frozen prediction or any grade is proposed except through a separate contract with its own delta report (D4).**

## How to read the evidence column

| Mark | Meaning |
|---|---|
| **V** | Re-derived directly by me from Neon, the lake or the code in this session |
| **A** | Reported by a delegated agent and not independently re-derived (spot-checked where noted) |
| **S** | Superseded: an earlier statement that was wrong; kept visible on purpose |

## Evidence register

| # | Finding | Mark | Where |
|---|---|---|---|
| 1 | Score-stream dips are in CFBD's raw feed: raw Bronze has 0 null scores in 58,379 plays and 272 drop events in 158 team-games (Silver 223 in 133); not a null-fill or sort artifact | V | issue 1, `a1-findings.md` |
| 2 | 6 of 215 games have a running-score maximum that differs from the final (identical in raw): Army 30 vs 24, UCF 13 vs 7, Memphis, Toledo, Middle Tennessee, New Mexico State | V (agent also confirmed) | issues 1 and 7 |
| 3 | V5 quarantines 27 of 430 team-games (not 129, which counted rows); stored points 234 vs about 867 scored; quarantined games average about 3.1 ppp vs 2.15 league | V | issue 1, `b-findings.md` |
| 4 | Points identity: 403 of 430 team-games reconcile; of 27 that do not, 24 are quarantined and 3 observed (Vanderbilt W3, Northern Illinois W3, New Mexico State W4: 26 points short) | V (ledger rebuild reproduces the served quarantine 27 of 27) | issue 1 |
| 5 | Weeks 0-4 grades reproduce: spread 100-112-3, total 112-102-0, zero differences | V | issue 6, `g2-findings.md` |
| 6 | Week 5 shows a defaulted side on 15 null-lean rows (12 games); 5 contradict the model. Cause: the old 1.0-point "No Bet" rule, removed 2026-10-02, frozen in the Week 5 run. Display fixed on `dev` (derive the lean), not yet released | V | issue 6 |
| 7 | All 155 zero-PPA eligible plays are CFBD nulls filled with 0; 127 of 430 offense team-games touched; about -232 EPA counted as 0 (estimate from same-play-type reference means) | V (the -232 is an estimate) | issue 3, `d-findings.md` |
| 8 | Overtime never reaches the drive metrics (0 of 76 overtime plays eligible); published values equal an independent recompute (24 of 24 for four teams). Issue 5 closed, not a defect | V | issue 5 |
| 9 | 11 of 271 games have NULL city/state across 8 venues; cause: Silver `venues` built from captures that stop at 2025; CFBD `/venues` has all of them | V | issue 4, `e-findings.md` |
| 10 | The play-vs-final score reconciliation never runs (column-name mismatch); 2026 reconciliation is a constant label | V (code); A (frame column names) | issue 7 |
| 11 | Every 2026 quote price is null; every stored selection price is the -110 default | V | issue 8 |
| 12 | Neutral-site games: 6 played games lean +5.4 points (SE 2.0, n=6) toward home vs the market | V | issue 9 |
| 12b | Intercept 7.437, 2025 neutral gap +4.2 (n=22, v4 replay), sizing +3 to +3.5 points, Elo benchmark | A | issue 9 |
| 13 | 2025 has the same dips (32%) and quarantine (151 of 1,868, 8.1%); priors 137 of 138 | A | issue 10 |
| 14 | Lines: sign, range and book-agreement checks pass; quotes captured 35+ hours before kickoff; unmatched Odds API event names never saved | A | issue 11 |
| 14b | Weeks 3-4 have one book; stored line differs from the snapshot median in 54 of 100 weeks 0-2 games and 16 of 56 Week 5 games; no side flips; weeks 0-4 record identical under the median line | V | issues 11, 12 |
| 15 | Away best-quote sort (L5) is active: in all 70 games where books disagree the stored line is the highest home line, the worst for all 33 away picks (0.82 points); weeks 0-4 record changes by one result (loss to push) under the best line | V | issue 12 |
| 15-S | **"Selected point equals consensus on every row, so L5 never changed a pick"** | **S (wrong: compared two copies of the same selected quote)** | corrected in issue 12, `g2-findings.md`, session log |
| 16 | Rating-level delta: baseline reproduces the served observations (6,880 of 6,880 rows) and the served Week 5 ratings (112 teams, zero difference); rule R1 lifts reconciliation 403 to 411 of 430 (0 worse), quarantines 27 to 18 | V | `delta-findings.md` |
| 17 | Rule R1 channel A (11 team-games recovered, +113 points) moves 18 teams more than 0.05 overall (rating sd 0.56) and 15 teams more than 5 ranks (max 36); channel B (attribution only, 134 team-games) moves more teams. **Weakened by items 20-21, then restored by items 24-25:** 8 of the 11 recoveries are corroborated by the quarter line scores (the drives check had suggested only 3; see 22-S) | V | `delta-findings.md` |
| 18 | Week 5 margin movement via an approximate bridge (R2 0.997): 16 of 56 margins move more than 1 point under channel A, with **4 approximate spread-side flips** (proxy, not the real bridge) | V (approximation, labelled) | `delta-findings.md` |
| 19 | Total-score movement | **Inconclusive** (proxy R2 0.82; no direction is claimed) | `delta-findings.md` |
| 20 | CFBD `drives` is not a clean oracle: drive scores are monotone in 383 of 430 team-games, and drive points exceed the final in 36; it is clean in only **9 of the 30** affected team-games (it is wrong where the play stream is wrong, e.g. Purdue 78 vs 36) | V | `d1-candidate-rule.md` (shadow check) |
| 21 | On CFBD-clean team-games, per-drive agreement with CFBD is 98.1% for the baseline ledger and 97.9% for R1; where they differ (66 drives) CFBD agrees with the baseline on 36 and with R1 on 28 (neither on 2): **channel B is unsupported** | V | `d1-candidate-rule.md` |
| 22-S | **SUPERSEDED by items 24-25 (the CFBD drives validator was dirty exactly where the recoveries are):** "only 3 of channel A's 11 recoveries are corroborated; small rating effect". Original text: only 3 of channel A's 11 recoveries are corroborated (Vanderbilt W3, Northern Illinois W3, Miami (OH) W4); recovering just those moves 1 team more than 0.05 (max 0.111) and 2 teams more than 5 ranks (max 13). The "ledger total equals the final" identity is true by construction for capped games, so it is not independent evidence | V | `d1-candidate-rule.md`, `delta-findings.md` |
| 23 | The 3 "silently short" team-games are CFBD-clean and their missing 7, 7 and 6 points are non-drive scores (defensive or special-teams touchdowns), not lost offense | V | `d1-candidate-rule.md` |
| 24 | Silver quarter line scores are a clean validator (sum equals the final in 430 of 430 team-games). Rule R1 matches them in every quarter for 8 of the 30 affected team-games (baseline 2); **8 of the 11 channel-A recoveries are quarter-corroborated** and 10 of 11 have at least one independent corroboration | V | `quarter-scores-findings.md` |
| 25 | Rating effect of the quarter-corroborated recoveries: 18 teams move more than 0.05 overall (max 0.352), 13 teams more than 5 ranks (max 36): nearly the whole channel-A effect | V | `quarter-scores-findings.md` |
| 26 | Channel B (R1's attribution changes in 134 team-games) is still unvalidated: quarter totals cannot resolve attribution, and CFBD drives favours the baseline (item 21) | V | `d1-candidate-rule.md` |
| 27 | `non_offense_points` is not used by the ratings; it feeds the forecast offsets (`forecast/offsets.py`, earlier-only regulation non-offense events) and the matchup page (`non_offense_points_per_game`). The three silent-short gaps (7, 7, 6 points) land there; the forecast effect was not measured | V (code); effect unmeasured | `quarter-scores-findings.md` |
| 28 | Why `ppa` is null on the 155: 70% have no valid pricing state or are not plays; CFBD's docs say turnovers are priced and null must not become zero; no null was ever filled by a later capture or a fresh pull. Separately, CFBD revised turnover `ppa` in mid-September (682 plays, weeks 1-2); Silver holds the corrected values | V (docs: A, read from CFBD's pages) | `d-findings.md` addendum |

## Recorded user decisions (2026-10-03)

| Decision | Recorded outcome |
|---|---|
| D1 | Full R1 is the Window 2 candidate. It cannot serve until scoring attribution is independently validated; no V1 fallback or partial release. |
| D2 | No EPA imputation. Withhold affected EPA with provenance while retaining valid PPP and independent measurements. |
| D3 | Ship independently verified punt, missing-PPA display, and venue fixes in Window 1; retain the current scoring-opportunity rule until R1 certification. |
| D4 | Rebuild corrected 2025/2026 V5 lineage, full Ridge refit, and neutral treatment together only in Window 2. |
| D5 | Complete the 2025 matchup backfill last, after the corrected Window 2 lineage is selected. |
| D6 | Matchup pages remain default-on with `CFB_MATCHUP_ENABLED=0` as the emergency opt-out; their data is verified under the two-window release gates. |
| D7 | Use versioned snapshots, canonical existing spread/total fields plus separate selected points, exact ties away/under, and frozen-side grading. |
| D8 | Public Performance is accuracy-only. Remove profit/units/ROI; preserve financial fields and default-price facts in audit. |
| D9 | Add the six prevention gates in the approved contract. The materiality threshold counts independently corroborated movement only. |

The recommendations below are preserved as investigation history. Where they conflict with this table, the recorded decision and [04](04-data-integrity-two-window-implementation.md) control.

### D1: score-stream rule (issue 1)
- **Options:** (a) keep quarantine; (b) rule R1 (monotone envelope capped at the final); (c) take scoring-drive points from CFBD `drives`.
- **Evidence:** (a) is not zero-cost: it drops real points from 27 team-games and biases against good offenses (items 3, 17). R1 improves reconciliation (item 16) but its channel B is not supported by CFBD (item 21) and 18 quarantines (single-row jumps above 8) remain. **The CFBD drives comparison has now been run (items 20-23): option (c) fails as a general oracle** because it is clean in only 9 of the 30 affected team-games.
- **Recommendation (revised again after the quarter line scores, items 24-26):** keep quarantine as today for every team-game, and adopt a narrow validated-recovery rule **V1**: apply R1 only to a team-game whose rebuilt ledger reproduces the Silver quarter line scores exactly in every quarter; all other team-games keep today's behaviour. That recovers 8 team-games (not R1's 145 changes): 4-5 genuine point recoveries (UCF W2, Stanford W1, USC W1, Nebraska W4), two cap-only quarantines the quarter scores show were correct (Memphis W2, Middle Tennessee W3), one timing fix (Army W2) and Vanderbilt W3's non-offense touchdown. Do not use CFBD drives as the source (clean in only 9 of 30 affected team-games); do not adopt R1's attribution changes (channel B: unvalidated, CFBD favours the baseline).
- **Limits:** quarter totals cannot show which drive scored within a quarter, so V1 is validated at quarter level only. The 18 single-row-jump quarantines and New Mexico State stay quarantined; their cost (items 3, 17) remains a documented limitation. Needs its own contract (it moves `ppp`).


### D2: zero-PPA rule (issue 3)
- **Evidence:** displayed team stats do not move visibly if the 155 nulls become missing (max 0.014, no rank move above 4, item 7). In V5 the zero-fill is a real, one-directional bias on `epa_per_possession` (127 team-games, about -232 EPA). Making the nulls null in Silver alone would quarantine EPA for those 127 team-games, which is worse.
- **Why the nulls exist (item 28, addendum to `d-findings.md`):** 108 of the 155 have no valid pricing state or are not plays (10 offsetting-penalty no-plays, 11 turnovers on kick/punt returns, 12 end-zone touchbacks, 75 with a missing start state); 47 have a valid state. CFBD prices most turnover plays, intends to price the rest ("turnovers are handled according to their resulting game state"), and says null "should not be converted to zero without an explicit analytical reason". A re-fetch will not fill them (0 of 155 ever filled across 35 captures; 0 of 67 in a fresh week-3 pull). About 70 turnover-type plays carry almost all of the bias (about -240 EPA).
- **Recommendation (refined):** treat as missing for displayed team stats. For V5, the evidence favors a split policy over quarantining 127 team-games: exclude the no-plays and start-state-missing plays from EPA, impute only the turnover-type plays that have a valid state using the same-type reference mean (flagged as imputed), and never zero-fill. This is an estimate inside a fitted measure, so it belongs in the D4 contract with its own delta report.

### D3: Silver rebuild now or at the planned rebuild
- **Evidence:** the overtime harmonization drops out (item 8). What remains is the punt-return special-teams tag (issue 2) and the zero-PPA null handling (D2), and the V5 effect of both is realised only if V5 is rebuilt.
- **Recommendation:** bundle with D4 in one window rather than a Silver-only rebuild. **Critical path:** D2 then D4. I do not recommend a standalone Silver rebuild.

### D4: V5 measurement and rating rebuild (proposed "now"; not decided)
- **Evidence:** the rating-level movement from the independently corroborated recoveries is material: 18 teams above 0.05 overall (max 0.352), 13 teams above 5 ranks (max 36) (item 25), and an approximate bridge moves about 16 of 56 Week 5 margins by more than a point (item 18). The EPA zero-fill bias (D2, item 7) is a separate measured one-directional effect on a fitted measure (127 team-games, about -232 EPA).
- **Recommendation (revised again):** D4 is back to "proposed now", but **scoped to V1 (D1) plus the D2 policy**, not to R1. Its contract must include its own delta report against the served lineage and a decision on `non_offense_points` (item 27). Not a full rebuild on R1.
- **Tier 2 (not executed):** re-deriving the 2025 terminal table and the priors. The 2025 quarantine feeds the 2026 priors (item 13, A), touching 92 teams. Not separable cheaply from the 2026 delta; the poisoned-prior effect is unmeasured. Costed in `delta-findings.md`; a question for the contract.

### Criterion tension: the D4 flip criterion, stated explicitly
- **The criterion as written** (unified plan, Task 1.2): a fix that moves any team's `ppp` by more than 0.05 or any rank by more than 5 places sets D4 to "now".
- **What happened to it during the review:** on the unvalidated R1 evidence it fired strongly; on the CFBD-drives-corroborated subset (3 recoveries) it still fired on one team (max 0.111) and two ranks, so demoting D4 at that point contradicted the criterion without saying why; on the quarter-corroborated subset (8 recoveries) it fires clearly (items 24-25). The earlier demotion was an artifact of validating against a dirty source (drives), not a judgment that the criterion should be relaxed.
- **Options for the user to record:** (a) keep the criterion and write its bar down: it counts only independently corroborated movement (a recovery counts if a second source corroborates it), uncorroborated movement does not count either way, and corroborated movement below the bar goes to a small scoped contract rather than a full rebuild; (b) revise the bar now. **Recommendation: (a)**, with D4 scoped to V1. With the bar written, the criterion is met by 8 corroborated recoveries (18 teams above 0.05), so D4 stays proposed "now" at V1 scope; a future case with only 1-3 corroborated recoveries would go to the small-contract path instead of silently flipping.

### D5: 2025 matchup backfill
- **Recommendation:** defer. D4 will re-pin the ratings; backfilling 2025 matchup tables before that would have to be redone.

### D6: matchup flag
- **Status:** moot as originally framed. Commit `f0f537a` made the pages default-on and the user chose to leave them live (2026-10-03). The stale state is recorded in `known_issues.md`, and the batch covers the matchup data. D6 becomes: confirm the pages after the batch.

### D7: selection and grading (split)
| | Question | Evidence | Recommendation |
|---|---|---|---|
| D7a | `>` vs `>=` tie rule | 0 exact ties in weeks 0-5; the display now follows the backfill rule (away/under) | Pick one rule for selection, backfill and display; low priority |
| D7b | Stored line vs canonical line | The stored line is the best-quote sort output, not the snapshot median (issue 12); the side comes from the canonical line; 0 side flips | Store the canonical line (or record both) so the card, the grade and the snapshot agree |
| D7c | Side rewritten without `quote_id` / `price` in the backfill | 0 side/quote mismatches in weeks 0-4 (V); path only runs for replay runs | Guard the code; nothing to repair |
| D7d | No completion filter in the backfill | Every graded row is completed (V) | Add the filter; nothing to repair |
| D7e | Away best-quote sort | Active (item 15): 33 away picks use a line 0.82 points worse; 1 result in 215 changes | Fix the sort (lowest home line for away picks) for Week 6 onward; do not regrade frozen weeks |
| D7f | Publisher writes a default side for a null lean | Display fixed (item 6). With the "No Bet" rule removed, future runs have a null lean only without a line | Change the publisher so a null lean never gets a default selection; low urgency |

### D8: neutral-site home edge (separate model contract; sized here only)
- Six played games lean +5.4 points toward home vs the market (V, n=6); agent-reported sizing is +3 to +3.5 points (range 2 to 5.5). Oklahoma-Texas (Week 6) is the first neutral game to forecast. Needs a model contract (neutral term or intercept shrink) and a holdout test; nothing changes here.

### D9: pipeline gates (separate pipeline contract; sized here only)
- Make the score and box-score reconciliation run, with a test that fails when a configured check is skipped (issue 7).
- Log the unmatched Odds API event names (or record the gap) every week (issue 11).
- Fail the venue dry run when a scheduled game's venue has no city (issue 4).
- Audit quote prices: fail loudly or label when prices are all defaults (issue 8).
- Add a per-game points-identity check to the measurement build (issue 1).

## Scoreboard-correction proposal (for `docs/status.md`; not applied yet)

Graded results are immutable and unchanged. Proposed wording, once the user approves:
- **Official record stays the as-graded one:** weeks 0-4 spread 100-112-3, total 112-102-0, retrospective replay (not prospective evidence), with these footnotes:
  1. Graded against early lines (27-229 hours before kickoff) from one or two books (issue 11); not closing lines.
  2. On 33 away spread picks the stored line was 0.82 points worse on average than the best available quote (issue 12). On a best-line-for-each-side basis the spread record is 100-111-4; on the snapshot-median line it is 100-112-3.
  3. Every stored price is the -110 default; profit units are flat -110 (issue 8).
- The two most-weighted caveats for anyone reading "47.2% vs 52.4%": the line timing (footnote 1) and the data issues above, none of which is known to flip a side.

## Recommended order

1. User decisions: D1 direction, D2 policy, D3 and D4 timing, D7e/D7b (week 6 onward), and the scoreboard footnote.
2. Release the null-lean display fix (blocked on the user: `kill 69617`, `npm --prefix web run test:ui`, commit).
3. ~~Compare CFBD `drives` points with the ledger~~ and ~~check the Silver quarter line scores~~ **both done 2026-10-03 (items 20-26): drives is not a clean oracle; quarter line scores are, and corroborate 8 of the 11 recoveries.** No further corroboration-hunting is proposed.
4. Contracts: a V5-rebuild contract scoped to V1 plus the D2 policy (D4, D3, with the `non_offense_points` decision), neutral-site model (D8), pipeline gates (D9).
5. The single production batch from the [unified plan](01-unified-data-fix-and-matchup-rollout.md): team stats (including `ppa_per_play`), venue backfill (a fresh 2026 venue capture), and, if D4 proceeds, the V5 rebuild with matchup re-pinning.
6. Week 5 close after certified finals plus 24 hours: grade with `scripts/pipeline/backfill_v5_unconstrained_grades.py --week 5 --grades-only`; the card and the grade now use the same derived side.

## Limits of this review

- Agent-reported items (marked A) were not independently re-derived; the packet's recommendations that depend on them (D8 sizing, the 2025 carryover in D4) say so.
- The hand-check confirms aggregation, not its shared inputs (the written eligibility definition and Silver's `eckel` flag).
- Rating movements come from rebuilding the served measurements and ratings in memory; margin movements come from a proxy fit; totals are inconclusive.
- Tier 2 and the real forecast bridge were not run. The CFBD `drives` comparison and the quarter line-score check were run (items 20-27); they changed D1 and D4 twice, which is a reason to treat any single validator with caution.
