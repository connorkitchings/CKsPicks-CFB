# Week 7 transition review — October 11 preflight

This is an execution finding under the [approved Week 6 closeout contract](01-week6-closeout-and-transition-review.md), not approval to open Week 7, repair EPA serving data or activate corrected selections. The [repair completion matrix](../2026-10-08/02-repair-track-certification-and-closure.md#completion-matrix) remains authoritative. Selected run identities and scoreboard remain in [status](../../status.md).

## Verified closeout inputs

- Retained CFBD [observation](week6-closeout-evidence/20261011T140813Z/observation.json): all 58 games final at October 11 14:08:13Z. No source final timestamp is exposed. Without earlier retained evidence, recheck unchanged finals no earlier than **October 12 14:08:14Z (10:08:14 AM New York)**. Completion alone does not establish 24-hour stability.
- [Preview](week6-closeout-evidence/20261011T140813Z/preview-preflight-r2.json) and [Production](week6-closeout-evidence/20261011T140813Z/production-preflight-r2.json) have identical 58-game keys and team identities, 55 selected predictions, zero Week 6 finals/grades and no Week 7 selection. No active lease was found. Read-only and repeatable-read identity checks passed. The source-capture/outcome catalog query since October 10 returned no earlier registered observation; unregistered external evidence was not exhaustively inventoried.
- Actual finals-loader dry runs in [Preview](week6-closeout-evidence/20261011T140813Z/preview-week5-loader-dry-run.json) and [Production](week6-closeout-evidence/20261011T140813Z/production-week5-loader-dry-run.json): 56 unchanged Week 5 finals, zero inserts/conflicts/missing/nonfinal rows. The outcomes ref was read back from R2 and matched the tracked Week 5 pin exactly.
- Effective restricted-role [Preview grants](week6-closeout-evidence/20261011T140813Z/preview-effective-grants-and-ref.json) and [Production grants](week6-closeout-evidence/20261011T140813Z/production-effective-grants-and-ref.json): SELECT/INSERT/UPDATE available on the scoped serving tables, DELETE unavailable. Reversal of newly inserted finals/grades requires separately reviewed owner execution; do not assume the pipeline role can restore them by deletion.
- [Fresh line reconciliation](week6-closeout-evidence/20261011T140813Z/line-coverage-reconciliation.json): CFBD currently returns spread and total lines for 58/58 schedule IDs. Its lines response includes 46 extra non-FBS games, individually classified and excluded. These are post-kickoff diagnostic quotes, not admissible replacement quotes. No Odds API credits were spent; the three early-game exceptions remain disabled.
- [Live HTTP checks](week6-closeout-evidence/20261011T140813Z/live-checks.json): health, Results, Performance, Ratings and a Week 6 matchup returned 200; selected-week health agrees with current week and reports 55 predictions/lines, published/pending. This does not establish completed grades, visual correctness, deployed code SHA or Vercel environment-variable configuration.

## Three schedule discrepancies requiring disposition

Both databases hold the prior kickoff values below; the retained CFBD response has revised values. Keys, teams and week are unchanged. The Week 5 source lock contains none of these Week 6 IDs, so these differences are not historical lock-row revisions. They must be reconciled with refreshed Silver before new Week 6 rows are appended; no serving schedule update is authorized here.

| Game ID / matchup | Stored kickoff (UTC) | Fresh CFBD kickoff (UTC) |
|---|---|---|
| 401862797 — Rice at East Carolina | Oct 10 20:00 | Oct 10 17:00 |
| 401856827 — Kansas at Utah | Oct 11 02:15 | Oct 11 00:00 |
| 401856808 — Hawai'i at Arizona State | Oct 11 01:30 | Oct 11 02:30 |

All three are later than the display forecast cutoff and are separate from the three early-game market gaps. The strict schedule preflight remains failed pending disposition; no historical cutoff or market-quote admission was changed.

## Transition dependencies and recommended order

| Obligation / owner | Evidence and current disposition | Next bounded task / acceptance |
|---|---|---|
| Week 6 serving closeout — operator/user | Week 5 parity passes; Week 6 grades/finals remain zero; stability not yet established | Recheck retained finals after 24 hours, establish clean reviewed execution checkout, retain complete backups, then exact user-run Preview and Production finals/grades applies with independent readback. Never freeze/close Week 6. |
| Week 6 source-lock extension — engineer/Sol | [Structural reproduction](week6-closeout-evidence/20261011T140813Z/lock-extension-blocker.json): Week 5 lock has 271 rows and prior `extends`; existing helper rejects it and cannot append new game identities | User chose planning a bounded extender repair. Obtain approval for next-week append support preserving all existing rows/cutoffs/provenance, then test 271 + 58 = 329, full key coverage and refusal gates. No repair implementation performed. |
| Complete corrected Week 6 chain — engineer/operator | Stable Silver, pins, 6A/Task 4/frames-only 6B and replay audits remain unexecuted | Resume after stability and extender repair. Inspect downstream CLI defaults before real execution: `build_corrected_successor_lock.py` still supplies only Weeks 0–5 serving/config maps. The generic helper is week-aware, but CLI integration is not proven; resolve any material mismatch separately. |
| Historical EPA replacement — Sol/engineer/user | [Completed investigation](../2026-10-10/adjusted-row-investigation/decision-report.md): 95 explained stale keys plus 951 differing shared EPA rows; no remediation applied | Separate contract for whole historical EPA population/value/rank/cohort replacement and exact stale-key cleanup. Require complete pinned candidates, backups, drift guards, appropriate owner privileges, atomic apply, independent parity and rollback proof; preserve as-of-6 rows. |
| Scoring/full metric correctness — engineer | Identity repair/invariance complete; running-score and full metric certification remain open in the matrix | Explain residual source defects, preserve missingness/exclusions, independently verify affected metric populations and every admitted delta; unresolved values block dependent certification. |
| Quality 1 — engineer | Request inventory checks delivered in part; required ingestion inputs/enforcement not fully proven | Wire completeness, schema and unmatched-odds inputs before writes; retain failed captures; prove positive and refused requests. |
| Quality 2 — engineer | Ambiguity guards do not close five-family review | Pin/dispose outcomes, legacy markets, offseason context, schedule revisions and aliases; retain version inventories and refuse ambiguity. |
| Quality 3 — engineer | Missing Gold comparisons/Silver builder-emitted receipts remain tracked | Actual population, score/box/null comparisons, missing-column refusal and durable builder receipts. |
| Quality 4 — engineer/user | Required-check policy exists; reviewed enforcement proof remains incomplete | Review blocking policy and prove builder refusals without weakening warn/require-check or request-basis semantics. |
| Quality 5 — engineer/operator | Durable release-adjacent receipt/readback obligation open | Retain immutable R2 receipt URI/raw hash and independent readback under its approved write scope. Local evidence alone is insufficient. |
| Quality 6 — engineer/user | Legacy validator disposition remains open | Inventory consumers/recovery behavior and approve retained/retired disposition before changing code. |
| Descendant certification — engineer | B2 retention does not certify season statistics/matchup descendants | Full key/value/provenance certification of historical and current affected descendants, including the four identity-collision games. |
| 2025 matchup backfill — engineer/user/operator | Candidate certification and publication remain open | Certify complete historical candidate before cutover; publish exact certified bytes after corrected selection, Preview first, under approved historical-lineage scope. |
| Preview B2 approval — user/operator | Fresh approval still has first-live-week 5 | Owner-run alignment to 6 only before an authorized future rehearsal, then exact fresh readback. No UPDATE here. |
| Display-release verification — operator/user | Current health/HTTP evidence retained; configuration/deployed revision/visual and post-grade verification still incomplete | Independently verify remaining Task 6 evidence. Any required deployment has separate release authority. |
| Week 7 rehearsal/release — operator/user | No Week 7 selection; authentic Week 5 provenance retained; no real cutover apply/rollback proof in this session | Stay paused. Future explicit opening decision, fresh complete schedule/target coverage, exact packets, Preview apply/freeze/repin/owner rollback/reapply, then separate Production decision. |
| Deferred repository work — separate owner | Archive lifecycle/prune, physical plan moves, runbook merger and Production boundary refactor have separate gates | Do not combine with closeout; resume only under their separately approved scope. |

The later repair matrix and approved closeout contract govern current gates, even where older quality-contract text described the follow-ups as nonblocking. October 13 pivot/freeze deadlines are future constraints, not permission to override the user's Week 7 hold.

## Resume boundaries

The source observation can establish a baseline now; it is not certified Silver. Before any write, recheck source scores/IDs, stored state, code SHA and permissions and bind the actual new certified outcomes ref. Do not use today's preflight as a future backup or release receipt. The contract stays In Progress until both closeout tracks and all required review acceptance pass.
