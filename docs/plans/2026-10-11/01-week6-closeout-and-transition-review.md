# Week 6 closeout and Week 7 transition review

- **Status:** In Progress
- **Created:** 2026-10-11
- **Planner:** Sol
- **Approval source:** User approved the proposed plan as written on 2026-10-11, requested persistence and a Terra handoff, then said “proceed” after switching out of Plan mode. User explicitly chose full 58-game replay certification as part of closeout. The clarification that both grading and reconstruction retain the verified finals-stability gate was stated before the final proceed.
- **Planning log:** `session_logs/2026-10-11/01-week6-closeout-planning.md`
- **Implementation log:** `session_logs/2026-10-11/02-week6-closeout-preflight.md`
- **Commit policy:** Separate plan commit; user controls all Git operations.

## Goal and acceptance

Finish grading the served Week 6 display run and independently certify the complete corrected 58-game replay in Preview. Review all remaining Week 7 transition obligations without opening Week 7 or activating corrected Production selections.

Track A is complete when certified stable finals are loaded and eligible stored sides/lines are graded in Preview and Production, independent grade and cumulative-record readbacks pass, retries make no additional changes, and outstanding display-release verification/configuration evidence is reconciled. The display run remains `published`/`pending`, with no fabricated freeze or close receipt.

Track B is complete when all 58 paired Week 6 forecasts and the corrected Weeks 0–6 chain have passing byte-integrity and point-in-time receipts, earlier-week changes are attributed, affected statistics/matchup candidates are independently certified, and immutable artifacts/receipts are retained in Preview. Missing admissible market lines are explicit ungraded gaps, not missing forecasts. Passing replay certification does not mean the wider repair contract is closed.

The transition review is complete when each remaining obligation has a verified disposition, dependency, next bounded task and acceptance evidence under the existing repair authority. Week 7 remains unopened in both environments throughout this contract.

## Baseline and constraints

- Inspected `dev` at `d22efb1a`, nine commits ahead of `origin/dev`, with pre-existing modified repair/run-sheet documents and untracked preparation, adjusted-row investigation code, tests, logs and evidence. Preserve all that work; do not stage, discard, stash, broad-format, commit, merge or push it. Applies require a reviewed, clean committed execution checkout; user-controlled commits must establish that baseline first.
- [Current Status](../../status.md) is the sole location for selected run identities, live week state and the scoreboard. Read it and freshly verify selections rather than copying run IDs into this contract.
- Fresh read-only CFBD query at 2026-10-11 13:46Z returned 58 games, all complete, latest kickoff 2026-10-11 02:30Z. The response exposes completion status but no final timestamp. This inspection was not an immutable capture or stabilization receipt.
- Fresh restricted-role, read-only database checks found identical serving state: current week 6; selected display run `published`/`pending`, 55 predictions, zero grades; 58 scheduled games, zero loaded results; no Week 6 prospective record; no Week 7 selection. Preview's exact B2 approval query still returned `first_live_week = 5`.
- Use R2 only; source/Preview credential presence was verified without exposing values. Never create repository-root `data/`. R2/catalog mutations are limited to reviewed immutable Preview inputs, artifacts and evidence. Production writes are limited to the reviewed Week 6 finals, grades and resulting statistics; no corrected replay selection, ratings republish, matchup repin, release authorization or Week 7 publication is included.
- Follow the [weekly operator](../../ops/v5_weekly_operator.md), [Week 6 display-release contract](../2026-10-09/02-week6-display-production-release.md), [repair completion matrix](../2026-10-08/02-repair-track-certification-and-closure.md#completion-matrix), [Week 7 run sheet](../2026-10-10/01-week7-cutover-run-sheet.md) and [record methodology](../../modeling/record_methodology.md). This contract narrows execution to closeout and review; it does not authorize later run-sheet opening/cutover steps.
- Both tracks require verified 24-hour finals stability. The run sheet's 03:00Z estimate and the user's approximately 06:30Z Monday estimate are not empirical proof. Find retained earlier final observations or establish a retained baseline and recheck unchanged scores after 24 hours; restart the affected stability clock if scores change. Do not infer completion time from kickoff.
- Preview before Production; dry run, reviewed user-run apply, independent readback. Owner-role SQL and exact release approvals remain separate. No schema/public API changes, model redesign, late-quote gate relaxation or betting changes are authorized.

## Ordered changes

### 1. Establish verified timing and execution inputs

Retain the complete 58-game schedule, final scores, capture time and raw checksums. Reconcile cancellations, score corrections, missing outcomes and schedule identity explicitly. Bind the 24-hour stability decision to retained observations. Correct the run-sheet timing estimate without rewriting historical evidence, and record the next permitted check.

Reverify environment/storage/database identities, restricted login/effective roles, grants, schema, leases, exact committed code and serving before-state. Record concrete immutable input URIs/hashes and new run identities only when generated and verified; no guessed hashes or approval records. The approved code already implements stored-side grading, policy labels, unique scoped backup filenames and grade readback; verify those paths instead of assuming the run sheet's older “fixes pending” note is current.

### 2. Track A: grade the served Week 6 record

1. Run `load_game_finals.py` in dry-run mode against the certified Week 5 outcomes in each target environment, requiring zero inserts and zero conflicts. Stop on mismatch.
2. Retain complete pre-write state sufficient to reverse Week 6 finals/grades and resultant system statistics, including existing grades, stored sides/lines/quote policies, selected runs and Week 5 provenance. Use unique environment/week-scoped backups and verify their bytes.
3. Reconcile certified Week 6 outcomes against all 58 scheduled games. Require complete finals and no stored-score conflicts. Dry-run the loader, then user-run Preview apply/readback followed by separately reviewed Production apply/readback; Production uses its restricted wrapper and confirmation flag.
4. Dry-run `backfill_v5_unconstrained_grades.py --year 2026 --week 6 --grades-only` against the selected 55-game run. Require zero prediction/market-selection updates, valid stored sides and real quote-policy labels; list every ungradable target. Then user-run Preview apply and independent readback, followed by the reviewed Production sequence.
5. Independently recompute target grades from final scores and stored sides/selected lines. Compare full keys, labels, counts and cumulative spread/total records. Verify Weeks 0–5 grades and selections, Week 5 authentic provenance, Week 6 run state/evidence class and absent freeze record remain unchanged. Re-run dry runs to prove idempotence.
6. Check real database-backed Results/Performance and Week 6 matchup pages, cache refresh and the remaining display-notice configuration evidence. Do not claim the locally implemented unified Performance page is deployed without checking the deployed revision. Any needed deployment is outside this contract and returns for a separate release decision.
7. Update only verified week/scoreboard facts in status and map completed Tasks 6–7 back to the display-release contract. Track A may complete while Track B remains blocked.

### 3. Track B: build and certify the corrected complete replay

Use only the closeout-related portions of run-sheet steps 1 and 3–7; stop before Week 7 generation, rehearsal or selection. A `prepare-week --week 7` data-refresh command may be used solely for post-Week-6 inputs after verifying it does not create/select a Week 7 forecast or advance serving state.

1. Refresh stable Week 6 Silver inputs in Preview, check provider play identities, pin parents and extend the source lock. Attribute every earlier-week delta. If a collision requires unsupported v2 wiring, stop and obtain a bounded amendment; do not downgrade the identity guard.
2. Extend the retained Week-5 6A and Task 4 plans through Week 6 with new immutable identities, exact cutoffs and pins; run preflight/build/independent verify/publish as permitted by the repair contract. Keep the approved B2 design/bundle and 2015–2019, 2021–2025 chronology; exclude 2020.
3. Instantiate the frames-only Week 6 6B template with actual roots, Task 4 receipt, parents, source references and expected weekly populations (8, 43, 49, 57, 58, 56, 58; cumulative 329). Do not invoke the legacy served-population grading stages on the unserved complete Week 6 replay.
4. Build the successor chain and corrected Weeks 0–6 replay candidates with provider names. Bind Week 6 forecast/state cutoff before its first kickoff (2026-10-07 00:00Z), separately from the market capture cutoff. Require 58 paired forecasts and no Week 6 outcomes in prediction inputs.
5. Rebuild/reconcile the Week 6 market-source lock against the complete schedule, separately for spread and total. Retain capture times, every missing ID and classification, and the next source check. New post-kickoff captures cannot create pregame provenance. The three early-game late-quote exceptions remain disabled absent a passing empirical admission receipt; retain them as ungraded gaps. Stop on unexplained changes to eligible quote coverage.
6. Package the replay candidates; run `audit_corrected_replay_chain.py --through-week 6` and the point-in-time audit over the exact Weeks 0–6 candidates. Retain signed, hash-bound receipts and missing-market declarations. Audit failure or unsupported real-data gap handling is a blocker, not permission to weaken coverage/cutoff gates.
7. Independently certify affected statistics and matchup candidates, including through-Week-6 descendants, using pinned corrected parents and full population/value/provenance comparisons. No public projection or repinning is included. If an unresolved scoring/metric repair blocks certification, record the concrete defect and return for the bounded repair scope.

### 4. Review remaining transition work without activation

Prepare one evidence-linked transition review beside this contract and reconcile the parent completion matrix. Order the recommendations as follows:

1. Historical EPA remediation: link the [completed investigation](../2026-10-10/adjusted-row-investigation/decision-report.md). All 95 stale keys are explained; 951 shared EPA rows also differ. Record a separate Sol execution-contract requirement for full certified historical EPA replacement, exact stale-key cleanup, complete before-state backups, atomic drift-guarded apply, independent readback and rollback proof. No deletion/replacement is authorized here; preserve later as-of-6 rows.
2. Resolve scoring/full-metric defects, the six quality follow-ups and affected historical/through-Week-5 descendant certification. Distinguish delivered tooling from required source/real-data evidence.
3. Certify the complete 2025 matchup candidate before cutover; its separate publication remains after corrected selection, Preview first, under the existing approved historical-lineage scope.
4. Record Preview B2 approval alignment as an owner-run prerequisite for a future rehearsal, followed by exact readback. Do not perform the UPDATE here. Track real Preview apply/rollback/re-apply proof, reviewed deployment revision and separate Production release decisions as still gated.
5. Keep physical archival, runbook consolidation and Production boundary refactor deferred. Record October 13 deadlines as future constraints; the Week 7 hold overrides automatic pivot/fallback execution. Opening requires a new explicit user decision and its approved operating scope.

## Validation

- Planning baseline: finals/backfill/leakage focused tests passed, 32 tests; these do not prove live finals loads, grades or replay certification.
- Track A: run focused `test_game_finals`, `test_backfill_grades` and `test_backfill_replay_grades` tests; cover missing/nonfinal/conflicting outcomes, stored-side and policy preservation, ungradable targets, existing grades, unique backups and idempotence. Retain real Preview/Production parity/readback evidence and complete pre/post invariant comparisons.
- Track B: run affected rebuild, 6B, replay-package and leakage tests. Cover 58 forecast keys, 329 cumulative keys, declared target gaps, first-kickoff boundary, future-outcome exclusion, earlier-week delta attribution, checksum failures and unsupported identity collisions. Real-data independent receipts remain mandatory.
- Run scoped Ruff checks for any touched Python, contracts checks if affected, and affected real-page/query verification. Broaden testing only for changed behavior or failures. No broad formatting of the dirty worktree.
- Run documentation-authority checks for changed authority maps, `uv run mkdocs build --quiet`, and `git diff --check`. Update status, contracts and session logs from actual results only. Leave parent repair In Progress while any obligation is unproven.

## Handoff/amendments

Sol persistence is documentation-only: save this approved contract and planning log, validate them, and hand off to a fresh Terra task. Do not execute finals loads, captures, reconstruction, SQL updates or implementation in the persistence session.

Terra starts with baseline reconciliation and retained finals-stability evidence, marks this contract In Progress, and records its implementation log. Existing exact user-run apply requirements remain intact; this approval is not a blanket release authorization. Finish available preflight/review work while timing dependencies are pending.

Mechanical amendments may continue only when scope, architecture, interfaces and acceptance stay unchanged. Material data defects, unsupported stage behavior, needed deployment, EPA cleanup, gate relaxation or any Week 7/cutover activation return for a separately approved scope. Never mark this contract Implemented while either closeout track or the transition review remains incomplete.

### October 11 execution checkpoint

[Preflight and transition review](week7-transition-review.md) retain an all-final baseline at 14:08:13Z and passing actual Week 5 loader parity in both environments. No operational writes: Week 6 still has zero finals/grades. Without earlier evidence, earliest unchanged-finals recheck is October 12 14:08:13Z; clean reviewed apply code remains required.

**Material Track B blocker:** the current extender rejects the already-extended Week 5 lock (271 rows) and cannot append the 58 new Week 6 identities. Three fresh provider kickoff differences are also retained for disposition. User chose planning a bounded extender repair that preserves all historical rows/cutoffs; that choice authorizes planning, not implementation or acceptance-gate changes. Track B is stopped at this dependency while unaffected read-only preflight/review proceeds. Week 7 remains paused.
