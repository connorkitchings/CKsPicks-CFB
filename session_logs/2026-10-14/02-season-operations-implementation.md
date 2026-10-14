# Session: Season operations bridge implementation

## TL;DR
- **Worked On:** Starting the approved bridge and season-workflow replacement after full plan persistence.
- **Outcome:** Plan/documentation validation passed; fresh restricted Production readback and Preview r3 root/receipt verification passed. Five-stage Week 6 configuration preparation delegated.
- **Plan Contract:** docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md
- **Approval / Status:** Owner explicitly authorized implementation; contract In Progress.
- **Blockers:** Clean reviewed plan/configuration commits precede operational builds. Exact Production release and rollback gates remain.
- **Next:** Week 7 display-only forecast/serving build (fresh line capture first).

## TODO
- [x] Persist and validate full approved plan.
- [x] Switch primary checkout to dev and establish fresh isolated worktree.
- [x] Fresh restricted Production selection/final/grade readback.
- [x] Reverify published Preview Task 4 r3 root and receipt.
- [ ] Verify deployed Week 6 Results/Performance and deployed revision.
- [x] Prepare/review bridge configuration.
- [x] Commit reviewed plan and configuration before operational build — explicitly authorized by owner.
- [x] Build/verify/publish Week 6 frames.
- [x] Commit generated successor/live pins (`ee87c529`, fast-forwarded to dev; no push) and build/verify/publish corrected ratings to Preview.
- [x] Week 7 display-only forecast/serving build through package (Preview R2, run `2026w7-v5repair-20261014-w7`).
- [x] Preview authorization, schedule, venues, publish, select, bridge verifier, matchup publish/verify and rollback dry run for the Week 7 candidate; 4 games lacking a total line accepted by the owner.
- [x] Production display-only release of Week 7 (R1-R12, R14); R13 freeze prohibited and not run.
- [ ] Rollback apply (owner/migrator login, not run); grading after finals; corrected Weeks 0-6 replay cutover.
- [ ] Build Week 7 Preview candidate and complete exact Production gate.
- [ ] Implement season runner and canonical model/revision adapters.
- [ ] Implement atomic schema, readers and publisher.
- [ ] Consolidate and archive documentation safely.
- [ ] Complete migration/cutover and subsequent weekly-update proof.

## Context and Decisions
- Implementation follows the complete linked plan. No fresh-chat requirement is imposed.
- Old worktree was externally removed; no discarded local artifacts are assumed recoverable. Published immutable Preview evidence is intact.
- Primary dev is up to date with origin/dev; main was separately merged/pushed. Git identity does not prove deployed identity.
- Phase 1 keeps exact Production approval/user-run prerequisites; automatic releases begin only after Phase 2 policy installation.

## Work Completed
- Documentation build and diff check passed before bridge work.
- Read Production through cks_prod_pipeline in a read-only transaction. Current week remains 6. Selected Weeks 0–5 are scored; Week 6 is published/pending with 55 predictions. All 58 Week 6 finals exist; 110 grades match spread35-19-1 and total23-32.
- Read live health: status ok, active Week 6 display run, expected/predicted/lined55.
- Independently verified Preview r3 root raw SHA a85a210e9c88b3d22296bff0b37d74375f05a3eebb5dafda601ae26f2d201570 and signed payload.
- Independently verified receipt raw SHA c29300e0bdff295cc327d3313999bf10c790bff60e213f4ee1e6bdfc44850128 against the root object map, and signed embedded checksum779110347578c0ee5d9d9cb0ed496e9596ae283afac4c09e11bff26048538e35.
- Receipt confirms cutoff2026-10-11T15:00:00Z and selected design ppp__rho_0_60__exposure.
- Delegated only the new five-stage Week 6 configuration; no cloud mutation or commit authorized to worker.

- Live Production Performance HTML already includes Week 6 and exact cumulative spread163-158-5/total160-164-1. Week 6 totals match direct database readback; no redeployment needed merely to expose these grades. Results-page visual confirmation and exact deployed revision remain pending.
- Prepared and reviewed conf/rebuild/6b_w6_v1.yaml; raw SHA31c8ecdffaee6fa8c7e3995e3713595dcee2978bcda2f585298fe2c883fdf764, parsed plan SHA1219eddcfaf8fe1ea36c421905996ed20450fe8045016dd8b73a54c89d777728. Its 2026-10-05 pregame cutoff is strictly between last Week 5 kickoff and first Week 6 kickoff; final-input cutoff remains2026-10-11T15:00:00Z.

## Validation
- [x] git diff --check for initial plan/log persistence.
- [x] uv run --no-sync mkdocs build --quiet.
- [x] Restricted read-only Production identity and business-state query.
- [x] Fresh R2 hash/signed-payload readback.
- [x] New configuration parsing, four local input pins, template-policy/output-prefix preservation, 329-game counts and strict cutoff bounds.
- [ ] Required phase-level operational validation.

## Amendments and Blockers
- None to architecture or acceptance. Production serving writes, R2 publication, git commits and deployments have not been performed by this implementation session.

## Handoff Notes
- **Resume at:** Reviewed clean-commit gate then Week 6 frames.
- **Watch out for:** Distinguish root embedded checksum, raw root SHA, receipt embedded checksum and raw receipt SHA.

**tags:** ["pipeline", "operations", "implementation"]

Owner authorized the two local commits and fast-forward integration into dev with “Authorized. Let’s proceed”. No push or Production write is included.

## Week 6 frames operational evidence

- Owner-authorized commits: plan3647e052 and configuration57113245; fast-forwarded dev. Both clean before preflight/build. No push.
- A manual credential-name assertion used incorrect aliases and stopped before data access; corrected to repository StorageSettings, then preflight passed.
- Preflight embedded checksum c834bfc317e6d24d0d5bec395d546a33cb62cba66f192cda17e01d48edd88776.
- All five stages built; full verify passed, embedded checksum bea7e0e612778c9f07456576dff1c0f761c9abd3d9d46ee02f16e40dbee73505.
- Scoring events:329 completed games,3073 events,10528 observations. Application frames:8/43/49/57/58/56/58 =329 games.
- Designed publication dry run passed. Preview publication wrote42 objects plus root; identical retry wrote0 objects, root unchanged. No catalog registration required for this bridge's direct references.
- Independent readback verified every42 object hash, signed root and unchanged original6A root. Frames root raw SHA285030d15601bca22d337165bcb5e43e5f201c15966dfa5576133e92c1919365; embedded checksum b1cb5a2786319f8982a5fb95821fbfdb98d536e743f9366f0f79a42538077474.
- Generated successor_lock_w6_v1.json raw SHAb40438fe932ad6dd2c4cd12a9b81968c49188376e39f340283d671a627f5a0d3.
- Generated successor_lock_w7live_v1.json raw SHA1c68a4c0e94a7a58ade2133c4658c0e6a5bfea2c5c42f70eb6f3c05f9ffe3a3f.
- Independent pins/population check:329 historical +59 Week7 live-source games, unchanged completed-week cutoffs, exact published parent raw hashes. Forecast population will dynamically omit kicked-off games at actual build time.
- Focused successor/intended-update tests:26 passed; diff check passes. Newly generated pins await the separately reviewed clean-commit gate before rating execution.
- Parallel isolated workers implement season preparation, additive atomic-release schema and request-consistent web queries; they do not modify bridge checkout.

## Corrected ratings operational evidence (Preview only)
- Pins committed as `ee87c529` and fast-forwarded to `dev`; both trees clean; 68 focused tests passed (successor, intended-update seam/package, preview authorization).
- Kickoff pre-check: the passed first Week 7 kickoff is handled only with `--display-only` (forecast omits kicked-off games; serving `apply_window_open` uses the data-age window). Forecast, serving, verify and package must pass `--display-only` and run back to back; the run sheet's "no `--display-only`" is superseded by Amendment 16.
- Previous manifest for w6-r1: `corrected-w5-r1` read back from Preview R2, signed payload verified, raw SHA `855f4dd717bef1c16c91cdca69b240e9bc8fce0336457cb592696ac14c632437`. Weeks 0-5 generation hashes did not drift.
- `v5-intended-update-2026-corrected-w6-r1` (329 games): rating manifest raw SHA `ff99a4e0e8cf7bc6c0bef9a54b1abcfe97ef0c092a296343a9253fe0a57d81bd`; preflight identical to apply; verifier dry run max difference 8.9e-16, verifier receipt raw SHA `0fa5071d716cc709b369bcc7f92ed170b570aa1e10172f7166175bc2de39eb0a`; identical re-apply wrote nothing new and returned the same SHA.
- `v5-intended-update-2026-corrected-w7live-r1` (388 games = 329 + 59), previous manifest w6-r1 (R2 copy byte-identical to local, signed): rating manifest raw SHA `201711c79105419cd0e32fe5a995274c6dea5736aa1abe53e19a6d922bb64dfb`; pregame_w0..w6 and current_post_w0..w5 did not drift; verifier max difference 8.9e-16, receipt raw SHA `ae36af9fa5672e14d4a501f313368a79f6dee7c8ba4322d812c27018d72f2b9a`.
- `current_post_w6` states exist for all 138 teams (so every team in the 59 games); latest observation cutoff `2026-10-11T15:00:00Z`.
- Preview database `publish_v5_intended_update_ratings.py --apply`: inserted 1880 rows (966 current + 914 pregame) into `v5_rating_snapshots`, all carrying manifest SHA `201711c7...`; identical retry inserted 0, unchanged 1880. Rows for `ratings-v1`, `corrected-w6live-r1` and the replay runs remain present with single manifest SHAs. Production untouched.
- Operational note: the worktree has no `.env`; R2 steps used a Preview-only env file built from the primary checkout's `.env` (no Production R2/database variables), database steps used `scripts/ops/with_preview_env.sh`.

## Week 7 display-only candidate evidence (Preview only, 2026-10-14)
- Log commit `377d26b9` fast-forwarded to `dev`. Primary checkout still shows the pre-existing untracked `scratch/` directory; the worktree is clean.
- The `capture_data_first_phase2.py --kind pregame` command in the fallback run sheet captures schedule/returning-production/recruiting/coaching, not lines, so it was not applied. Lines come from `ingest_week.py --entities betting_lines` (run ID `<id>:betting_lines`) plus `fetch_odds_api_market_quotes.py --confirm` (run ID `<id>:market_quotes`), then `build_week_market_snapshot.py`. The first CFBD attempt with `--require-full-line-coverage` refused to write (3 FBS-vs-FCS games without lines: Charleston Southern @ Clemson, The Citadel @ Texas A&M, Elon @ Stanford; none are in the lock). Two attempts used wrong run-ID shapes; one Odds API request (about 2 credits) was spent and discarded. Final capture: pipeline ID `w7-lines-20261014-r3`, CFBD 118 records, Odds API 474 quotes (53 events; 41 board events skipped as unmatched to the Silver schedule).
- Schedule reconcile: API 62 games vs lock 59 (the 3 extras above); 2 already kicked off (401871067, 401871053) omitted; Silver/lock kickoff for 401858492 (Nebraska @ Oregon, lock 10-17T04:00Z vs live 10-18T03:00Z) and 401858494 (Wisconsin @ UCLA, lock 10-17T04:00Z vs live 10-17T23:30Z) are stale.
- Market snapshot ref `artifacts/research/data-first-football-v1/market/w7-20261014-r3/market_snapshots_ref.json`.
- Forecast (`--display-only --weeks 7`, `--live-as-of 2026-10-14T14:42:04Z`): 57 games, state candidate, pending, live. Serving manifest sha `5ca2e5cb27929d055aae2434908de42c4e5c9612935f085631b779c5b1d178ba` (57 games, 4 unlined: 401858492, 401858494, 401864523, 401866442 have a spread but no total in the snapshot, though CFBD lists totals). Verifier receipt `46d4d57e49864fcfebda5bec2b6e87be1d747c43cedc950d183ec035609d22bf`. Packet `012b9dde911bcaf7ae1d3cc4f0ba50f0e0c36787d4164b08f6234ff4da3785bd` (53 lined games); identical package retry wrote nothing new.
- No authorization, selection, database apply or Production write was made.

## Week 7 Preview rehearsal P1-P10 evidence (2026-10-14)
- Owner accepted the 4 unlined totals and supplied decision references. Authorization row `preview-2026w7-v5repair-20261014-w7-f460617dbb22` (record `717dbd96696295f042ab4d6ffac8db3e5e5f3a90c3eafe721818a994f79b5ac7`) is in `v5_intended_update_release_authorizations`, decision ref `preview-rehearsal-display-only-week7`.
- Schedule: seeded 59 week 7 rows from the lock (retry 0). Venues: Silver lacked three venue IDs; `conf/venue_supplement_2026_w7_v1.json` (commit `6dd45971`, values from the CFBD venues API: 3714 Fargodome, 3757 Hornet Stadium, 3647 Elliott T. Bowers Stadium) filled them; 59 `game_venues` rows upserted with city, retry 0.
- Publish: `publish_to_db.py` needed `--allow-partial-slate` (the 2 kicked-off games are scheduled but omitted); 57 predictions, 53 with both lines, state `published`, evidence class `pending`, `rating_manifest_sha256` `201711c7...`. `select_public_run.py` found the run already selected (reason on the row stays `validated V5 publication`).
- Bridge verifier: 11 gates ok, payload `f850ab26b6fe9adbf04ea76e80d6299d37b1ec3b8827dc0ce4bb270a9a8ea965`, written once, identical retry no write. Matchup publish (payload pinned) wrote `team_possession_stats` 1656, `team_possession_adjusted` 551, `team_rating_components` 512; `verify_matchup_data.py` VERIFIED, 0 differing rows.
- Readback: `current_week` (2026, 7, active run = the candidate); selection present; 59 games, all with a city; 1880 rating snapshot rows under one manifest SHA.
- Rollback dry run (`preview-rehearsal-proof`): would restore `current_week` to week 6 (`2026w6-v5repair-20261008-d2`) and deselect week 7; without a release receipt it keeps stats and snapshots. Per the script, the published `team_rating_components` rows block a rollback apply until the prior matchup payload is restored. Apply was not run.

## Week 7 Production release evidence (2026-10-14)
- Owner decision reference `production-display-only-week7`. R2: `stage_v5_artifacts.py --predictions-only` staged `predictions.csv` (`f460617d…`) and `manifest.json` to Production R2; dry-run receipt `b06b6e83…`, apply receipt `eb95958c…`, readback both objects `present`.
- R4: owner SQL inserted `production-2026w7-v5repair-20261014-w7-f460617dbb22`; read-only check as `cks_prod_pipeline` found exactly one row, no mismatched fields, Production approval `production-intended-update-a507d0c7cba5` live from week 6.
- R5-R11 were run by the owner (the Production publish commands were blocked for the assistant by the permission classifier): ratings 1,880 rows (`201711c7…`), as-of-7 team stats 3,036 rows, schedule 59, venues 59 with city, `publish_to_db.py --allow-partial-slate`, selection, matchup data (payload `f850ab26…`, verified, 0 differing rows).
- R12 readback as `cks_prod_pipeline`: `current_week` (2026, 7) active run = the candidate; selections 0-7 present and Weeks 0-6 unchanged; run `published`/`pending`, no freeze or score time, 57 predictions (57 spreads, 53 totals); 59 games and 59 venues with city; 1,880 rating snapshot rows under one manifest SHA with all earlier runs present; as-of 1-7 team stats present (as-of 4-7 at 3,036); one Production authorization row for Week 7. The live site shows Week 7 with 57 games, "Run published Oct 14, 12:07 PM ET".
- Rollback note: a rollback apply needs the owner login and, because Week 7 matchup rows reference the rating snapshots, the prior matchup payload restored first.
