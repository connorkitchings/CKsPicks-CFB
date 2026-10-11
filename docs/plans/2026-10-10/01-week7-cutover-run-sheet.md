# Week 7 cutover run sheet (Weeks 0-6 corrected replays + pending Week 7)

- **Status:** Draft (run sheet under the [repair-track contract](../2026-10-08/02-repair-track-certification-and-closure.md), Amendments 3–10, and the [Stage 7B plan](../2026-10-06/02-stage7b-exact-release-and-cutover.md); it adds no authority of its own)
- **Created:** 2026-10-10
- **Rule:** every Preview write and every Production write is its own go-ahead. Preview first, always. Owner-role SQL is user-run. Dry run, then apply, then read-only readback.

## Clock (UTC)

**October 11 execution hold:** [Week 6 closeout](../2026-10-11/01-week6-closeout-and-transition-review.md) pauses Week 7 opening, rehearsal, selection and automatic fallback until a new explicit user decision. The retained all-final observation is October 11 14:08:13Z; without earlier retained evidence, unchanged finals must be rechecked after October 12 14:08:13Z. See the [preflight and extender blocker](../2026-10-11/week7-transition-review.md). The former approximately October 12 03:00Z estimate was not verified final-time evidence; the approximately 06:30Z estimate is also unverified.

| When | Event |
|---|---|
| Sun Oct 11 02:30 | Week 6 last kickoff |
| Sun Oct 11 evening | Code and harness checkpoint |
| Mon Oct 12 14:08:14 or later | Recheck the retained October 11 finals observation after 24 h; earlier gate requires retained earlier evidence, and any score correction resets the affected clock |
| Tue Oct 13 14:00 | **Pivot gate:** Preview rehearsal (including owner-login rollback proof and readback) not fully verified bars cutover; pivot to the independently approved/certified standalone Week 7 fallback |
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
9. **Preview rehearsal.** `stage_v5_artifacts.py`, `build_v5_cutover_packets.py` (authorization, selection, rollback, with `registered_bundle` and the passing `leakage_audit` receipt ref), `authorize_v5_intended_update_batch.py`, `select_v5_intended_update_batch.py --apply`, `freeze_week.py --year 2026 --week 7 --decision-ref …`, `publish_matchup_data.py --expect-payload-sha`, `verify_matchup_data.py`, the Week 6 to Week 7 `current_week` readback, then the rollback under the owner login and re-apply. All must pass before 14:00 Tuesday.
10. **Production** (user-run, by 21:00 Tuesday): stage artifacts, owner SQL for authorizations (the bundle approval already exists), apply the selection packet, freeze Week 7, repin matchups, verify, update `docs/status.md`.

## Preparation record (before finals)

The [dependency cards](../2026-10-08/02-repair-track-certification-and-closure.md#dependency-and-execution-cards-2026-10-10-preparation) define available-now tasks, stable-final dependencies and post-selection publication. All boxes below are **unchecked execution requirements**, not recorded results. Unknown code SHA, runs, source roots, packet hashes, candidate hashes and decision references are `UNRESOLVED`; replace them only with verified evidence from the owning operation. Live run identities come from [Current Status](../../status.md), then fresh environment readback.

Certify the complete 2025 candidate before cutover; publish/verify those exact candidate bytes after corrected selection in each environment, Preview first. This is [Amendment 10](../2026-10-08/02-repair-track-certification-and-closure.md#amendment-10-2026-10-10-pre-finals-preparation-and-2025-backfill-sequencing). Full repair closure follows the serving verification; all other integrity prerequisites still precede cutover.

## Preview rehearsal checklist (Monday step 9)

| Check / operation | Required retained evidence | Stop condition |
|---|---|---|
| [ ] Confirm context before any data I/O | R2 backend and Preview credentials present without printing secrets; verified database/artifact identity, `session_user`/`current_user`, effective grants, migration ledger, lease and reviewed code SHA | Wrong backend/environment/role, unexpected schema/grants/lease or dirty/unreviewed apply code |
| [ ] Confirm Preview B2 approval | Execute the read-only query below; exactly one row with `first_live_week = 6` | Zero/multiple rows or another value; stop before packet validation. Owner alignment is separately user-run, followed by fresh readback |
| [ ] Export complete before-state and rollback registrations | All selected Weeks 0–6, `current_week`, protected/unlisted selections, revocations, Week 5 attestation, both bundles, registered authorization rows; exact business/provenance snapshots for stats/system stats/matchups | Missing or changed row, extra selection, altered Week 5 receipt or incomplete retained rollback payload |
| [ ] Certify all final inputs | Stable Week 6 finals; contiguous complete replay forecasts 0–6; eligible unstarted Week 7; passing audit for every selected run; both Week 6 cutoffs; declared gaps; stats/matchup payloads/verifiers; certified 2025 candidate; all other integrity receipts | Missing receipt, failed rule, unexplained descendant/key/value change, late quote without empirical acceptance, stale schedule/quote coverage or missed deadline |
| [ ] Build reviewed authorization/selection/rollback packets | Environment-bound spec, `advance: true`, exact before/after maps, registered bundle, empty protected map only with no extra selections, `leakage_audit`, payload references and verbatim prior registered rollback rows; raw hashes and before/after diff | Unknown field/hash, packet/manifest mismatch, incomplete keys or unreversible rollback |
| [ ] Review staging scope, then separately approved staging if needed | Packaged artifacts and storage readback; source/target namespaces explicit; pending/unscored run handled separately from scored replays | Unpackaged/missing bytes, same source/target used as a transfer, unreviewed receipt/hash or overwrite. Preview artifacts already resident are verified, not transferred to themselves |
| [ ] Prior user-run authorization | Exact authorization packet/code hashes, environment decision and registration receipts; pipeline only verifies existing approval rows | Missing/mismatched approval, revoked record or changed bound state |
| [ ] Selection dry run, then separately approved apply | Rechecked identities, lease, registered records and before-state; atomic selection/statistics/current-week receipt | Any guard failure or state drift; no partial apply/retry by assumption |
| [ ] Freeze eligible Week 7 under existing guarded route | Fresh quote set, one-hour deadline, exact decision reference and immutable freeze/provenance readback | Week 7 started, deadline passed, late quotes or missing authentic receipt; Week 6 never frozen/closed |
| [ ] Repin/verify 2026 matchup and query/cache state | Exact reviewed payload hash, chosen measurement manifest or paired 6A refs, Preview verifier and real optional-table reads; compatible lineage and bounded cache recovery | Wrong lineage, partial/null-key mismatch, unavailable/sharing guard failure or repin timeout |
| [ ] Read back all after-state | Selections/current week, statistics/system stats, Week 5 unchanged provenance, Week 7 freeze, approvals/revocations, matchup payload and actual web results | Fixture-only result, missing scoped table or any numerical/provenance mismatch |
| [ ] Prove owner-login rollback | Review safety/deadline and prior payload; restore prior matchup payload first, then guarded batch restore including removal of Week 7 selection under owner/migrator login; recomputed statistics/cache and exact before-state readback | Role cannot delete selection, state advanced, unsafe timing, changed prior inputs or incomplete restoration |
| [ ] Re-apply and verify | Repeat guarded state/authorization checks and permitted apply/freeze/repin route; idempotent handling of retained authentic freeze evidence; complete final readbacks | Any retained receipt/state conflict or missed timing gate |
| [ ] Verify post-selection 2025 publication in Preview | Separate approved write of the pre-certified candidate, full key/value/provenance parity, independent readback and idempotent retry; retain pre-write backup | Candidate changed, wrong selection, unexpected key or missing write approval. This requirement also precedes Production review |

**Mandatory approval preflight (read-only; not run during documentation preparation):**

```sql
SELECT first_live_week
FROM v5_model_bundle_approvals
WHERE approval_id = 'preview-intended-update-a507d0c7cba5';
```

An operator records the returned row and capture time. A prior note or intended UPDATE is not proof. If alignment is needed, the user performs the already documented owner-role UPDATE and the operator repeats this SELECT before continuing.

### CLI references checked against source

These are command shapes for later approved execution, not paste-ready instructions with invented identities. Use the verified environment wrapper/context and unique output/receipt paths. `UNRESOLVED` values must be replaced from actual reviewed artifacts before a command runs.

| Entry point | Verified arguments / context |
|---|---|
| `export_v5_registered_releases.py` | `--environment preview` or `production`, repeated `--run WEEK=RUN_ID`; read-only JSON output |
| `build_v5_cutover_packets.py` | Positional `authorization`, `selection` or `rollback`; `--spec <reviewed-json>` and `--out <new-path>`; `CFB_ARTIFACT_ENV` must equal spec environment. No `--environment` or `--apply` flag |
| `stage_v5_artifacts.py` | Explicit `--source preview --target production`, repeated `--run`, `--receipt`; default dry run. Approved apply adds `--apply --expected-receipt-sha256 <reviewed-hash> --expected-code-sha <reviewed-sha>`. Pending-only transfer uses `--predictions-only` and must not mix scored replays |
| `authorize_v5_intended_update_batch.py` | `--environment`, `--packet`, `--receipt`, `--expected-packet-sha256`, `--expected-code-sha`; default dry run, separately approved `--apply`; authorizer context/environment guards apply |
| `select_v5_intended_update_batch.py` | `--packet`, default dry run, separately approved `--apply`; environment is packet-bound and operator-context guarded, not a CLI `--environment` argument |
| `freeze_week.py` | `--year 2026 --week 7 --decision-ref <approved-ref>`; operation writes directly under verified environment context, has no dry-run/`--apply`/`--environment` option. Do not invoke it as a preflight check |
| `publish_matchup_data.py` | `--season --environment --weeks --rating-manifest-uri`; `--measurement-manifest-uri` or paired `--six-a-run-id`/`--six-a-root-sha256`; default dry run, separately approved `--apply --expect-payload-sha <reviewed-hash>` |
| `verify_matchup_data.py` | `--season --environment --weeks --rating-manifest-uri`; measurement URI or paired 6A refs. Historical 2025 candidate publication must satisfy its own approved historical-lineage contract; do not assume this intended-update-only publisher supports it |

## Production review checklist (Monday step 10 preparation)

**Hard pivot — Tuesday October 13, 14:00Z (10:00 AM New York).** If Preview rehearsal, including owner-login rollback proof, exact readback and required re-apply verification, is not fully verified by this time, the operator is barred from cutover and must immediately pivot to the standalone fallback below. No late "almost passed" rehearsal overrides the gate. The fallback retains its own approval, certification, coverage and freeze requirements; freeze by October 13 22:00Z (6:00 PM New York).

| Review item | Required evidence / decision |
|---|---|
| [ ] Exact proposal identity | Reviewed clean committed code SHA, environment, packet/rollback raw hashes, concrete cutover week and decision reference; all currently `UNRESOLVED` until generated/verified |
| [ ] Complete source certification | Contiguous replay range, eligible pending run, full passing leakage receipt, stable-final evidence, original freeze provenance, exact roots/bundle/stat/matchup refs, 2025 candidate certification and all remaining integrity receipts |
| [ ] Production before/after diff | Fresh selected runs/current week, complete statistic/provenance keys, system stats, prospective records, registered bundles/authorizations/revocations and matchup payloads; compare exact proposed scope |
| [ ] Complete Preview evidence | Apply, freeze, matchup/query/cache readback, owner rollback proof, exact restoration, re-apply verification and certified 2025 Preview publication readback; approve nothing from synthetic smoke alone |
| [ ] Rollback safety | Retained previous payloads, verbatim registered rows and both approvals; owner login available, compensation order reviewed, deadlines/state-advance rules verified |
| [ ] Gaps and deadlines | Fresh complete schedule/target coverage, capture time, missing IDs and next refresh; three early-game exceptions remain disabled without passing empirical proof; pivot/first-kickoff/one-hour-freeze boundaries rechecked |
| [ ] Separate exact user approval | Name actual Production authorization/selection packets and hashes, scope and apply decision. This preparation is not that approval; earlier Preview approval is not transferable |
| [ ] Fresh apply preflight | Recheck identity, grants, migrations, lease, revocations, source/packet bytes and all before-state. Drift invalidates dependent packet/approval; rebuild and review rather than edit signed bytes |
| [ ] Guarded release and readback | Reviewed staging, prior owner authorization, atomic selection/stat/current-week apply, guarded Week 7 freeze, 2026 matchup repin, cache/query readback; Production selection establishes the corrected-selection prerequisite |
| [ ] Post-selection 2025 publication and final closure | Publish only the certified candidate under separate applicable approval, then independently verify complete serving parity/idempotence. Update operational status from actual results; close repair only when every obligation passes |

**Unresolved fallback gate:** the standalone fallback still needs its own short approved contract and exact release decision. At pivot, prepare/run that path only within its approval and timing boundaries; missing fallback certification or approval means stop before publication/freeze. A scheduled pivot is not authorization to bypass an integrity gate.

## Fallback (pivot gate or any Tuesday slip)

Week 7 as a frozen standalone run on corrected ratings through Week 6: the same builds as steps 1-8, then the Week 6 publish chain (`seed_week_schedule.py`, `publish_game_venues.py --only-missing`, `publish_to_db.py --config conf/weekly_bets/v5_intended_update_2026.yaml --state published`, `select_public_run.py`, matchup publish), then `freeze_week.py --year 2026 --week 7 --decision-ref <approved-decision-ref>` at least one hour before kickoff. It counts as prospective evidence, so a Week 8 cutover still validates. It needs a short contract before it runs.

## Not exercised yet

No Week 6 replay exists, so the serving verifier, packager and publisher have not seen a replay with declared spread gaps; no Week 6 6B run exists; the seven-week fixture does not use live-shaped finals; the v2 validator's Postgres integration path was not run this session.
