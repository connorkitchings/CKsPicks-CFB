# Week 7 cutover run sheet (Weeks 0-6 corrected replays + pending Week 7)

- **Status:** Draft (run sheet under the [repair-track contract](../2026-10-08/02-repair-track-certification-and-closure.md), Amendments 3-5, and the [Stage 7B plan](../2026-10-06/02-stage7b-exact-release-and-cutover.md); it adds no authority of its own)
- **Created:** 2026-10-10
- **Rule:** every Preview write and every Production write is its own go-ahead. Preview first, always. Owner-role SQL is user-run. Dry run, then apply, then read-only readback.

## Clock (UTC)

| When | Event |
|---|---|
| Sun Oct 11 02:30 | Week 6 last kickoff |
| Sun Oct 11 evening | Code and harness checkpoint |
| Mon Oct 12 ~03:00 | Earliest certified Week 6 finals (24 h stable); later if any final moves |
| Tue Oct 13 14:00 | **Pivot gate:** Preview rehearsal (including rollback) not fully verified means abandon the cutover and run the standalone Week 7 fallback |
| Tue Oct 13 21:00 | Production cutover complete |
| Tue Oct 13 22:00 | Week 7 freeze deadline (first kickoff 23:00) |

## Packet design (Amendments 4-6, implemented; Preview rehearsal still to prove it)

1. **Advance mode.** Week 7 has no selection, so the selection packet is built with `advance: true` (before-state Weeks 0-6, `current_week` 6; after-state Weeks 0-7, `current_week` 7).
2. **Rollback needs the owner login** (it deletes the Week 7 `site_week_selections` row); under the pipeline role it fails closed.
3. **Bundle approval.** Carry the Production approval (first live week 6) as `registered_bundle` in the forward spec.
4. **Nothing protected.** Weeks 0-6 are all replaced and no other week is selected, so the spec has `protected_runs: {}`; apply fails closed if any other selection exists.
5. **Preview approval.** Preview's B2 approval has `first_live_week = 5` (Production: 6). Before the Preview rehearsal the user runs, as the Preview migrator login, `UPDATE v5_model_bundle_approvals SET first_live_week = 6 WHERE approval_id = 'preview-intended-update-a507d0c7cba5';`, otherwise the forward gate refuses the packet (Amendment 7).
6. **Rollback records.** Export the registered rows of the currently selected runs with `scripts/pipeline/export_v5_registered_releases.py --environment <env> --run 0=<id> ... --run 6=<id>` and paste them into `rollback.registered_authorizations` and `rollback.registered_bundles` (two bundles: Weeks 0-5 and Week 6). Both environments' rows were read on 2026-10-10 and match in shape.

## Monday sequence (after finals are stable)

Record each step's evidence in the session log. Stop on any Week 0-5 change that is not attributed.

1. **Week 6 finals and Silver refresh (Preview).** `ops prepare-week --year 2026 --week 7 --as-of <cutoff after the last Week 6 final> --environment preview --pipeline-run-id <id>` (pattern from Stage 1 Amendment 6). Check the Week 6 plays for provider-ID collisions: the `byplay_v1` builder fails closed on a collision, and the 2026 stages cannot run a v2 plan today, so a collision means stopping and wiring v2 first.
2. **Finals into `game_results` (Preview, then Production, user-run).** `scripts/pipeline/load_game_finals.py --year 2026 --week 6 --outcomes-ref-uri <game_outcomes_ref.json>`: dry run, then `--apply` (Production also `--confirm-production`). Then `backfill_v5_unconstrained_grades.py --week 6 --grades-only` on the display-only run (55 of 58 games; run it only after the policy fixes in the 2026-10-10 plan land: stored side, real policy label, read-back, week-specific backup). Week 6 then counts in the unified 2026 record (no freeze, ever). This closes Week 6 release Task 7. At the cutover the corrected Week 6 replay (all 58 games) replaces it in the counted record and is graded through `score_to_db.py --from-artifact --run-id`. Parity check first: the same loader on Week 5 must report 0 inserts and 0 conflicts.
3. **Pins and lock.**
   - `pin_6a_silver_parents.py --season-2026 --byplay-version … --game-outcomes-version … --reconciled-team-game-version … --source … --out conf/rebuild/silver_2026_parents_w6_v1.json` writes the Week 6 parents file.
   - `extend_rebuild_source_lock.py --outcomes-ref-uri … --new-cutoff <after Week 6 finals> --games-ref-uri … --out conf/rebuild/source_lock_2026_w6_v1.json` (accept any provider kickoff revision explicitly with `--accept-kickoff-revision`).
   - Week 6 market-sources lock: `scripts/pipeline/build_week_market_sources_lock.py --week 6 --as-of <forecast cutoff> --games-ref-uri … --market-quotes-ref-uri … --market-snapshots-ref-uri … --source-manifest <d2 manifest> --cutoff-source <d2 serving manifest> --expected-games 58 --out conf/rebuild/6b_source_refs_w6_v1.json --report <coverage report>`. It writes the source refs extended by Week 6 and lists the verified gaps (post-kickoff-only quotes: no selection, no grade); `derive_successor_lock` carries them into the lock. Dry run on the d2-era data: 58 games, 55 eligible, 3 gaps per target (401871051, 401871066, 401871090). Rerun on Monday's Silver versions and compare the gap list with this one; any newly eligible game needs a look before it is used. **Two Week 6 cutoffs:** the forecast `as_of` must be before 2026-10-07T00:00:00Z (the first Week 6 kickoff) so all 58 games are forecast without Week 6 results in the ratings, while the market lock's cutoff is the snapshot capture (2026-10-08T16:19Z or later). Record both; the audit checks that the forecast one is at or before the first kickoff. The three early games' CFBD lines (401871090 Southern Miss @ Troy, 401871051 Jacksonville State @ Kennesaw State, 401871066 New Mexico State @ FIU) are accepted only through the lock's accepted-late list (`cfbd_pregame_consensus_fetched_post_kickoff`) and only after the CFBD re-fetch comparison supports it; otherwise they stay ungraded verified gaps.
4. **6A and Task 4 through Week 6.** Copy `6a_w5_v1.yaml` and `6a_task4_w5_v1.yaml` to `_w6_`, new run IDs, cutoffs and the two new pins; run `make rebuild-6a OP=preflight|build|verify|publish` (about hours, not days).
5. **6B frames for Week 6.** Fill `docs/plans/2026-10-08/6b-w6-frames-plan-template.yaml` (`cutoff_2026`, the Task 4 receipt sha, root shas, the two w6 pins, `unserved_week_as_of` for Week 6 after Week 5's last kickoff and before Week 6's first, counts `{0: 8, 1: 43, 2: 49, 3: 57, 4: 58, 5: 56, 6: 58}`); the bundle stays `bundle_b2_w5_v1.json` (`a507d0c7…`, Amendment 3).
6. **Successor chain.** `build_corrected_successor_lock.py`, then `build_v5_intended_update_2026.py` and `verify_v5_intended_update_2026.py`, then `publish_v5_intended_update_ratings.py` (not `publish_v5_ratings.py`), then the Week 0-6 replay set with provider names, independently verified: `audit_corrected_replay_chain.py` (extended to Weeks 0-6) for byte integrity and **`audit_point_in_time_leakage.py`** for the point-in-time rules a-g; the signed receipt must pass for Weeks 0-6 before packets are built.
7. **Team stats as-of 7** and matchup data: `publish_team_stats.py --as-of-week 7` (dry run first), `verify_team_stats.py`; matchup publish happens after selection.
8. **Week 7 pending run.** Fresh market capture, reconcile the full FBS schedule against spread and total coverage (AGENTS.md session rule 6), then `build_corrected_live_lock.py --week 7`, `build_v5_intended_update_forecasts.py`, `build_v5_corrected_live_serving.py` (no `--display-only`), `verify_v5_corrected_live_serving.py`, `package_v5_corrected_live_run.py`.
9. **Preview rehearsal.** `stage_v5_artifacts.py`, `build_v5_cutover_packets.py` (authorization, selection, rollback, with `registered_bundle` and the passing `leakage_audit` receipt ref), `authorize_v5_intended_update_batch.py`, `select_v5_intended_update_batch.py --apply`, `freeze_week.py --week 7 --decision-ref …`, `publish_matchup_data.py --expect-payload-sha`, `verify_matchup_data.py`, the Week 6 to Week 7 `current_week` readback, then the rollback under the owner login and re-apply. All must pass before 14:00 Tuesday.
10. **Production** (user-run, by 21:00 Tuesday): stage artifacts, owner SQL for authorizations (the bundle approval already exists), apply the selection packet, freeze Week 7, repin matchups, verify, update `docs/status.md`.

## Fallback (pivot gate or any Tuesday slip)

Week 7 as a frozen standalone run on corrected ratings through Week 6: the same builds as steps 1-8, then the Week 6 publish chain (`seed_week_schedule.py`, `publish_game_venues.py --only-missing`, `publish_to_db.py --config conf/weekly_bets/v5_intended_update_2026.yaml --state published`, `select_public_run.py`, matchup publish), then `freeze_week.py --decision-ref` at least one hour before kickoff. It counts as prospective evidence, so a Week 8 cutover still validates. It needs a short contract before it runs.

## Not exercised yet

No Week 6 replay exists, so the serving verifier, packager and publisher have not seen a replay with declared spread gaps; no Week 6 6B run exists; the seven-week fixture does not use live-shaped finals; the v2 validator's Postgres integration path was not run this session.
