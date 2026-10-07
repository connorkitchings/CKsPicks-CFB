# Stage 1: Week 5 corrected data finalization (Preview only)

- **Status:** Approved
- **Created:** 2026-10-07
- **Planner:** Sol
- **Approval source:** User approved this exact scope (Stage 1 only, release path decided afterwards) in the 2026-10-07 planning session; each Preview write step still needs the user's explicit go-ahead when reached.
- **Implementation log:** `session_logs/2026-10-07/07-stage1-implementation.md`
- **Commit policy:** User-run commits in batches (each push cancels running CI); one commit per task group.

## Goal

Finish the data work on the corrected lineage in Preview, with no Production or serving change: ingest Week 5, extend the corrected Silver, measurements and rating generation through Week 5, produce corrected team stats (as-of 1-5, as-of 6 as a candidate) and matchup data for Weeks 0-5, make the corrected builders the weekly path, and deliver a decision brief for choosing the release path (wait for the cutover, interim replay release, or display-only Week 6).

## Current state (verified 2026-10-07)

- Corrected foundation exists in Preview only: 6A (`rebuild/6a/6a-rebuild-20261004-r1`, Task 4 `6a-task4-r1`) and 6B (`rebuild/6b/6b-replay-20261005-r1`, root raw SHA-256 `6fb59797…`, build `eca6871`). Production serves the uncorrected lineage.
- 6B comparison, Weeks 0-5, 271 games: mean margin change 3.1 pts (max 15.2), mean total change 0.7, 27 spread and 13 total lean flips, 40 selection sides and 38 lines changed, 38 grade results changed; retrospective spread 128-139-4 becomes 130-136-5.
- Silver coverage: Production `byplay` `443019a9…` has plays for Weeks 0-4 only; Silver `game_outcomes` `d01d92ac…` has Week 5 finals; Silver `games` lists Weeks 0-15.
- The corrected 2026 rebuild is tied to Week 4: `silver_2026.py` re-derives "the certified Week 4 2026 Silver" and compares against the legacy Week 4 byplay; `states_2026.py` follows the Week 4 lock cutoff; `recon_foundation.py:118` uses `w < 5`; `scripts/pipeline/pin_6a_silver_parents.py` reads `SEASON_2026_SILVER_INPUT_SETS["w4"]`. That table (`scripts/research/run_data_first_repair_v2.py:99`) has entries `w0, w1, w2, w4` only; `tests/test_data_first_2026_extension.py:531` asserts that exact list. A repair run must match one approved set in full.
- The weekly ingest command is `ops prepare-week` (`ops/__main__.py:1727`): `ingest_season.py --entities games`, then `ingest_week.py` for plays and game stats of every completed week 0..N-1, Silver builds (games, outcomes, plays, team game stats, reconciliation), Gold, and a final `target_week_readiness` step that fails until the new rating generation is projected.

## Excluded

Any Production write; Contract 04 amendments; changes to the release controller or the kickoff-guarded scripts; Week 6 publishing; the neutral-site model; Docker CI parity.

## Tasks

### Task 0 - Verify the assumptions this contract rests on (read-only)
Confirm, with file:line evidence recorded in the implementation log: (a) what `prepare-week --week 6` writes and to where (Preview R2, Preview Neon ingestion tables) and whether its Gold step is required for this work; (b) every Week-4-specific binding in the corrected rebuild code (the four above plus any others, including the harness namespace allow-list in `rebuild/targets.py`); (c) how 6A pinned the 2026 raw inputs and what a Week 5 pin set must contain. Stop and amend this contract if any assumption below is false.

### Task 1 - Week 5 ingest and legacy-lineage Silver (Preview write; needs go-ahead)
`prepare-week --year 2026 --week 6 --as-of <ISO> --environment preview` through `scripts/ops/with_preview_env.sh`. Expect it to build Silver and then stop at `target_week_readiness` (unprojected ratings); that stop is not a defect. **Stop conditions:** Weeks 0-4 rows of the new `plays`, `byplay`, `game_outcomes` and `reconciled_team_game` versions must equal the pinned w4 versions' Weeks 0-4 rows (content comparison per week); any difference (for example CFBD retro-edits or enrichment changes) pauses for review.

### Task 2 - Approved input set `w5` and Repair-2026 w5
Add `w5` to `SEASON_2026_SILVER_INPUT_SETS` from the Task 1 versions after verifying coverage (271 completed games, plays for Weeks 0-5, scored finals matching the schedule, last kickoff + 6h inside the batch `as_of`); update the test list. Run the Repair-2026 extension for w5 with its independent verifier (`verify_data_first_repair_v3.py`).

### Task 3 - Week-parameterize the corrected rebuild
Generalize `silver_2026.py`, `states_2026.py`, `recon_foundation.py`, `pin_6a_silver_parents.py` and the plan config so the 2026 stages take the week/label instead of Week 4; allow a new rebuild namespace and run ID in the harness without weakening the serving-chain denylist. **Parity gate:** with `w4` pins the new code must reproduce the 6A and 6B outputs byte-for-byte (tests plus a Preview read-only comparison against the published 6A/6B objects).

### Task 4 - Corrected Silver, measurements and ratings through Week 5 (Preview write; needs go-ahead)
Preflight, build and verify each stage from a clean committed HEAD with the expected SHA, as the harness enforces; publish create-once to Preview R2 and the Preview catalog. Earlier rating-generation digests (pregame w0..w5, current post-w0..w4) must reproduce exactly; any drift stops work.

### Task 5 - Corrected team stats
`publish_team_stats.py` dry-run (never apply) for as-of 1-5 and as-of 6 candidate against the Task 4 Silver with all five inputs pinned; `--diff` against Production's current table and against Preview; signed `v5_team_stats_release_payload_v1` with an independent verifier. Before/after key sets must be identical and complete.

### Task 6 - Matchup data rebuild (dry-run and retained payloads)
Run `publish_matchup_data.py` in Preview as a dry run bound to the corrected rating and measurement manifests; keep the candidate payload and the previous Production payload; all reconciliation gates must pass.

### Task 7 - Prediction artifacts
Production-namespace prediction and scored artifacts for the six corrected runs, byte-verified against the 6B outputs; reproduce the 6B comparison numbers above from them.

### Task 8 - Code and pipelines (local, tests, CI green on the exact commit)
- Corrected builders as the weekly default (nullable PPA and the shared data semantics are currently opt-in).
- Week-parameterize the successor scripts and add `scripts/pipeline/build_v5_intended_update_source_lock.py`; test that Week 5 `p2` outputs reproduce byte-for-byte. Keep the three kickoff guards exactly as they are.
- D7f: stop `publish_to_db.py` (`:928`, `:982`) writing a default side for a null lean.
- Data-quality follow-ups 1 and 2 (wire the three skipped ingest checks; review the five unpinned datasets).
- Record, without building, decisions for #8 (prices) and #11 (closing-line capture).

### Task 9 - Decision brief
A short document with measured results and what each release option would now require, for the user's release-path decision.

## Testing strategy

Per task as written; plus Ruff, `make contracts-check`, the full Python suite and web checks if web files change, `git diff --check`, and checksummed evidence (`*.log` is git-ignored: use `git add -f` or a `.log.txt` name).

## Risks

- Weeks 0-4 drift when the harness is generalized or when `prepare-week` re-ingests earlier weeks (CFBD edits; enrichment fixes). The parity and stop gates exist for this.
- Preview R2 is the same physical bucket as production's; create-once keys and the namespace allow-list are the separation.
- The approved-inputs table is a safety control; extending it is a reviewed code change, not a config tweak.

## Definition of done

- [ ] Task 0 evidence recorded; no false assumption left.
- [ ] Week 5 ingested; Weeks 0-4 stability proven; `w5` set approved and repair verified.
- [ ] Corrected rebuild parameterized with byte-parity on Weeks 0-4.
- [ ] Corrected Silver, measurements, ratings through Week 5 published to Preview and verified; earlier digests unchanged.
- [ ] Corrected team stats and matchup candidate payloads built and verified.
- [ ] Production-namespace prediction artifacts verified against 6B.
- [ ] Code and pipeline tasks merged with CI green.
- [ ] Decision brief delivered; `docs/status.md` and the issue register updated; contract set to Implemented.

---

## Amendment 1 (2026-10-07, Task 0 results): corrections that do not change scope or architecture

- **No new namespace is needed.** `RUN_NAMESPACES = ("rebuild/6a/", "rebuild/6b/")` (`src/cks_picks_cfb/rebuild/plan.py:22`) and the harness allow-list in `targets.py` already permit a new run ID under `rebuild/6a/`. Task 3's "allow a new rebuild namespace" is dropped; a Week 5 Silver extension is a new plan file with a new `run_id` under `rebuild/6a/`. The existing 6A plan file stays untouched (a test pins its hash).
- **Complete list of Week-4 bindings Task 3 must generalize (with parity gate):** `silver_2026.py` (docstring and `:204` legacy Week 4 byplay comparison), `states_2026.py:249-264` (Week 4 lock cutoff), `recon_foundation.py:118` (`w < 5` against the lock's market sources), `recon_markets.py:283` (`w < 5`), `recon_grades.py:232` (a Week 3 special case for game 401856811's unlined total, to be replaced by lock-recorded gaps), `scripts/pipeline/pin_6a_silver_parents.py` (the `w4` set), the `SEASON_2026_SILVER_INPUT_SETS` table (`w0,w1,w2,w4`; `tests/test_data_first_2026_extension.py:531`), and the plan config's `cutoff_2026` and `source_lock_2026`.
- **The lock builder moves earlier.** The pinned `source_lock_2026` (`docs/plans/2026-09-29/v5-repair-2026-source-lock.json`) holds the Weeks 0-4 post-week cutoffs, market sources and the Week 5 `p2` run; a Week-5-complete corrected rebuild needs a lock extended with the post-Week-5 cutoff. So `scripts/pipeline/build_v5_intended_update_source_lock.py` becomes **Task 3B** (before Task 4), no longer a Task 8 item.
- **`prepare-week` step list** (`ops/__main__.py:1727-1935`): `ingest_season.py --entities games`; `ingest_week.py` for plays and game stats of every week 0..N-1; week policy; Silver builds `games`, `game_outcomes`, `plays`, `team_game_stats`; `build_team_game_dataset.py`; `combine_history_versions.py`; `build_temporal_matchups.py` and `build_regime_features.py` (V4-era Gold, unused by the corrected lineage but always run); `check_prepared_week.py` (the readiness step that fails until ratings are projected). It always re-ingests every completed week, which is why the Weeks 0-4 stability gate in Task 1 is mandatory.
- **Task order:** 1, 2, 3 and 3B (local code, tests), then 4.

## Amendment 2 (2026-10-07, during Task 1): work order and two findings

1. **Dependency finding: your core deliverables do not need Week 5 plays.** Team stats as-of N use games completed before week N, and matchup pages for Weeks 0-5 use ratings through Week 4. The corrected as-of 1-5 team stats, the rebuilt Weeks 0-5 matchup tables and the six corrected prediction runs can therefore all come from the already published 6A/6B foundation. Week 5 plays only matter for post-Week-5 products (as-of 6 stats, Week 6 matchups, a post-Week-5 rating generation). Work order: **Group A** Tasks 5-7 from the existing foundation; **Group B** Task 8 (code and pipelines); **Group C** Tasks 2, 3, 3B, 4 (the Week 5 extension). Task 1 (ingest) was approved separately and is running; it is needed for Group C.
2. **Missing builders (added to Group A).** The v2 controller only *validates* `v5_team_stats_release_payload_v1`; nothing in `src` or `scripts` builds it, its verifier, or the matchup before/after payloads (only test fixtures do). The 6A published-comparison stage rebuilt the five corrected tables in memory (`rebuild/published_comparison.py`) and stored only a diff report, not the tables. Group A therefore adds `scripts/pipeline/build_corrected_publication_payloads.py` and an independent verifier, reusing `published_comparison.season_stats_frame` and the matchup payload builder (`mp.build_payload`).
3. **Controller inconsistency (not changed under this contract; needs a user decision).** `src/cks_picks_cfb/ops/v5_batch_selection_v2.py:231-236` rejects a packet whose team-stat `source_versions` differ between the before and after payloads ("team-stats provenance changed across the packet"), and the test fixtures never change them. Corrected stats built from corrected Silver necessarily carry different `source_versions`, and Appendix B says to include the new versions there. So as written the controller would reject a legitimate corrected payload on **every** release path, the planned cutover included. The honest fix is an amendment letting provenance change when the verifier binds the after lineage; falsifying the field to pass is not acceptable. This goes in the Task 9 decision brief and in the release-path decision.

## Amendment 3 (2026-10-07): user decisions after Amendment 2

- **Approved:** Group A first (payload builders and verifier) while the Week 5 ingest finishes; then the Week 5 extension (Group C).
- **Approved and done:** the controller provenance fix, recorded as Contract 04 Amendment 6 and implemented in `v5_batch_selection_v2.py` with five new tests (they fail on the previous controller). The corrected payload's verifier must therefore emit the `provenance_change` binding described there; the builder in Group A writes honest corrected `source_versions` and never copies the old ones.

## Amendment 4 (2026-10-07): Task 1 outcome. Stop condition triggered; work halted for review

**Run:** `ops prepare-week --year 2026 --week 6 --as-of 2026-10-05T00:00:00Z --environment preview --pipeline-run-id stage1-w5-ingest-20261007`, 19:06:31Z to 19:18:24Z, Preview only. Raw ingest of Weeks 0-5 and the Silver builds `games` (`ddccd30e…`), `game_outcomes` (`e3e4cfab…`), `plays` (`46a62d34…`, 48,378 rows) and `team_game_stats` (`4701e2f3…`) completed. All are new immutable versions; the previously pinned versions are untouched and still readable.

**1. Weeks 0-4 are not byte-identical (the strict stop condition).** Row counts match (38,401). Exactly **71 rows in one game, 401856660 (Week 1, LSU)** differ from the pinned `plays` `eda5263c…`: 70 `ppa` values changed, and five consecutive plays of one drive (drive 14, plays 3-7) were re-sequenced (play text, type, down, distance, clock, `play_id`). Weeks 0, 2, 3 and 4 reuse their identical captures; only Week 1 has a new capture (`058e3d908f…` became `cb48168623…`). Cause: CFBD revised that game's play-by-play after the 2026-09-27 capture. Evidence: `stage1-evidence/task1-weeks0-4-plays-drift.json`. **All downstream work (Tasks 2-4) is halted until the user decides how to treat it.**

**2. The run then failed at `build_current_team_game`** (`build_team_game_dataset.py`): `ReconciliationError: Blocking source conflicts for games: [401871090]`. That is Southern Miss @ Troy, the Week 6 game that kicked off on 2026-10-07; the ingest's `--as-of` is an event-time label, not a capture-time filter, so the freshly captured `games` data marks it complete while its plays and stats (Week 6) were not ingested. As a result no new `byplay` or `reconciled_team_game` version exists yet.

**Options for finding 1 (user decision):**
- **A (recommended): keep the pinned Week 1 capture.** Build the Weeks 0-4 Silver from the original captures and add only Week 5 from the new one, recording CFBD's later edit as a known upstream revision that is deliberately not adopted. This keeps every earlier generation digest reproducible. It needs a build path that selects captures explicitly instead of "latest per week" (new code).
- **B: adopt CFBD's revised game.** Weeks 0-4 Silver changes for one game, so the published 6A/6B foundation would have to be re-derived for it and earlier rating-generation digests may change. Only worth it if the revision matters.
- **C: pause** until you want to revisit.
For finding 2 an explicit rule is needed for games that completed after the cutoff (exclude them from the reconcile, or ingest Week 6); either is a small code change plus a test.

## Amendment 5 (2026-10-07): Group A progress and a scope finding for Task 7

**Done (local, read-only against Preview R2 and Production):** controller provenance fix (Contract 04 Amendment 6); `rebuild/release_payloads.py` plus tests; `scripts/pipeline/build_corrected_publication_payloads.py` and `verify_corrected_publication_payloads.py`. The corrected as-of 1-5 team-stats payload (11,506 rows, same key set as Production) verifies, and its changes reproduce 6A Task 4's published comparison exactly: 1,328 value changes plus 263 rank-only changes (1,591 rows), all in the EPA/PPA family; nothing else differs. The real payloads and receipt pass the controller's binding check; a tampered binding is rejected. Evidence: `stage1-evidence/`.

**Finding for Task 7.** The 6B `served/week=N/` manifests (`evidence_class: retrospective_reconstruction`, no rating-manifest SHA, bundle SHA or forecast, serving and verifier chain) are not what the run authorization needs (`ops/v5_intended_update_release.py` requires the successor chain: rating manifest, forecast manifest, serving manifest, verifier, `evidence_class` `replay` or `pending`). So producing the six corrected runs in release form means re-expressing the corrected foundation in the successor artifact formats (rating manifest from the 6A states, bridge/bundle from the 6A refit, forecast, serving and verifier manifests per replay week). Task 7 grows from "copy and byte-verify" to a build task; its design belongs in the decision brief and probably a further amendment.

## Amendment 6 (2026-10-07): user decisions on the Task 1 stop; Option B adopted

**Decisions (user, in session):**
1. **Week 1 LSU revision: Option B.** Adopt all of the updated CFBD data and re-derive Weeks 0-5 on the updated foundation, with strict point-in-time boundaries and no future data in any earlier state. The published 6A/6B 2026 outputs that depend on game 401856660 become superseded evidence; nothing published is altered.
2. **Troy conflict: exclude games completed after the cutoff.** Implemented as `exclude_games_after_cutoff` (`src/cks_picks_cfb/data/reconciliation.py`), used by `scripts/pipeline/build_team_game_dataset.py` before the reconciliation: a game counts as available only if kickoff plus the six-hour availability buffer (the rule `states_2026.available_by` already uses) is at or before the cutoff; later games are marked not completed, no rows are dropped, and the excluded ids are printed. Six tests, including one showing the reconciliation blocks without the helper and a game inside the cutoff still blocks. Week 6 is not ingested.
3. **Controller fix committed standalone:** `e54a2e37` (three files).

**Re-run:** `prepare-week` pipeline-run `stage1-w5-ingest-20261007-r2`, same arguments, started 19:27:22Z (first attempt `...20261007` failed at the reconcile for Troy and is kept as the record).

**Consequences for the tasks:**
- **Task 2 is replaced.** Editing the approved-inputs table (`SEASON_2026_SILVER_INPUT_SETS`) and running the old-lineage Repair-2026 refresh were only needed for the dropped display-only Week 6. Instead `pin_6a_silver_parents.py` takes explicit `--byplay-version`, `--game-outcomes-version` and `--reconciled-team-game-version` and derives the parent set from that byplay's manifest, producing a new pin file for the Week 5 foundation. The safety table is not touched.
- **Task 3 stays as written** (week-parameterize `silver_2026.py`, `states_2026.py`, `recon_foundation.py`, `recon_markets.py`, `recon_grades.py`, the pin script and the plan config), with this parity gate instead of "Weeks 0-4 identical": a full rerun under a new run ID with the new pins must reproduce the published 6A **historical** (2015-2025) outputs byte-for-byte, and every 2026 difference must be attributable to the revised game.
- **Task 4** runs the full pipeline (a complete 6A rerun takes hours, not days: the baseline stage alone is about 22 minutes, the early stages about 49 minutes) and publishes create-once to Preview. It is followed by a **6B rerun** pointed at the new root, whose comparison against the served runs supersedes the earlier figures (27 spread and 13 total lean flips, 38 grade changes, spread record 130-136-5), which depended on the old Week 1 data.
- **New deliverable: attribution of the revised game.** A short report of exactly which teams' states, which later predictions and which grades move because of game 401856660, so the effect of adopting CFBD's revision is known rather than assumed.
- **Point-in-time statement.** The revised play-by-play is an improved record of a game that was already complete; it is used only for states after that game's availability time (kickoff plus six hours). No Week 5 or Week 6 data enters any earlier pregame state; the stability, leakage and cutoff checks in the existing stages stay in force.

## Amendment 7 (2026-10-07): Task 3 and 3B delivered as small, tested tools

- **Task 3B is `extend_rebuild_source_lock` (not the successor-chain lock builder).** `src/cks_picks_cfb/rebuild/lock_extension.py` (pure) and `scripts/pipeline/extend_rebuild_source_lock.py` (thin CLI). The rebuild stages read only `games`, `post_week_cutoffs` and `research_2026_prediction_keys.completed_games` from the lock, so the extension adds the next post-week cutoff and the new finals and refuses to change anything already recorded: a different final for a recorded game, a final not yet available at the new cutoff (kickoff plus six hours), a cutoff that does not follow the last one, non-contiguous weeks, or a lock that is already an extension. The base lock's own `game_rows_sha256` could not be reproduced from its content (derivation lost; only one successor-chain script cites it as provenance), so it is left untouched, cited as `base_game_rows_sha256`, and a new hash with a stated method is added. Seven tests.
- **Task 2 replacement delivered:** `scripts/pipeline/pin_6a_silver_parents.py --season-2026 --byplay-version … --game-outcomes-version … --reconciled-team-game-version … --source …` reads the parent set from the named byplay's manifest (exactly four datasets, never "latest"). The approved-inputs table is untouched. Three tests.
- **Task 3 delivered for the 2026 stages:** `silver_2026.py` now applies the same cutoff exclusion before its reconciliation (identical behavior for the original Week 4 pins, since no game after that cutoff was flagged complete or 6A would have blocked), and the Week-4-specific wording in `silver_2026.py` and `states_2026.py` is generic. The remaining Week-4 literals (`recon_foundation.py:118`, `recon_markets.py:283`, `recon_grades.py:232`) belong to the 6B reconstruction, which still covers Weeks 0-5, so they stay as they are.
- **Plan config:** `conf/rebuild/6a_w5_v1.yaml` (run `6a-rebuild-w5-20261007-r1`) is a copy of the pinned 6A plan with new run ID, cutoffs and two new pins (the Week 5 Silver parents file and the extended lock). It is generated once the re-run of `prepare-week` has produced the Silver versions.
