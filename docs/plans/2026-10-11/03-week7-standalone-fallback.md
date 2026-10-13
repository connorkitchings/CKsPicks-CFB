# Week 7 standalone fallback (frozen Week 7 on corrected ratings through Week 6)

- **Status:** Draft, awaiting owner approval. It adds no authority of its own; it releases nothing until the owner gives it an exact release decision.
- **Created:** 2026-10-12 (command chain rewritten the same day after checking every script's argparse on `dev` at `f8848bfa`)
- **Governed by:** the [Week 7 cutover run sheet](../2026-10-10/01-week7-cutover-run-sheet.md), the [gate waiver contract](02-week7-cutover-gate-waiver-and-readiness.md) and the [repair-track contract](../2026-10-08/02-repair-track-certification-and-closure.md) Amendments 14 and 15.
- **Rule:** Preview first, always. Every Preview write and every Production write is its own go-ahead: dry run, then apply, then read-only readback. Owner-role SQL is user-run.

> **2026-10-13 note ([repair Amendment 16](../2026-10-08/02-repair-track-certification-and-closure.md#amendment-16--2026-10-13-week-7-ratings-decision-display-only-release-and-live-rating-provenance)).** Two parts of this document are superseded:
>
> - **Ratings input.** The owner decided Week 7 forecasts must use ratings corrected through Week 6. Option 2 below (post-Week-5 manifest `c83b1423…`, Week 6 left out) is withdrawn. Week 7 publication now waits for [Task 4 `6a-task4-w6-r2`](../2026-10-13/02-task4-verification-and-catalog-repair.md) and the 6B Week 6 frames to be built, verified and published, then the rest of the upstream chain (step 4 onward uses `6a-task4-w6-r2` in place of `6a-task4-w6-r1`).
> - **Freeze.** The first Week 7 kickoff (`401871067`, 23:00Z October 13) has passed, so a frozen Week 7 is impossible. Week 7 ships display-only: games kicked off before the run's `as_of` are omitted, the evidence class stays `pending`, and the run is never frozen. The command reference's "never `--display-only` here" notes no longer apply to Week 7. Step R13 and the optional Preview freeze rehearsal do not run; `freeze_week.py` refuses display-only runs and would mark a late run `missed`. "Why Week 7 cannot be skipped" and the Week 8 Advance-Mode prerequisite of a Week 7 freeze receipt need a separate disposition.
>
> The forecast builder in step 10 must also carry the live-rating provenance fix recorded in Amendment 16 (live predictions keep `current_teams` ratings with `#current:<current_teams_raw_sha256>/<team>` refs, checked by the serving verifier) before it is run for Week 7.

## When this applies

The run sheet's pivot gate is Tuesday 2026-10-13 14:00Z. If the Preview rehearsal of the Advance-Mode cutover, including the owner-login rollback proof and readback, is not fully verified by then, the Week 0–6 corrected-replay cutover is barred. Week 7 is then served on its own: a frozen Week 7 run whose ratings come from the corrected chain through Week 6, with Weeks 0–6 left as currently selected (Week 6 stays on the display-only run `2026w6-v5repair-20261008-d2`, see [Current Status](../../status.md)).

The owner has also approved taking this single-week route for Week 7 if the three missing Advance-Mode producers (finals-certification receipts, prospective-records payloads, R2 ref uploader) are not small; Advance Mode stays the route for Week 8.

If the Weeks 0–6 corrected replay set or its audit receipt is the part that failed, the fallback must not claim the corrected record. The Week 7 run is then labelled by what it actually rests on (see "Ratings input").

## Why Week 7 cannot be skipped

The Week 8 Advance-Mode selection requires Weeks 0..7 selected and `current_week` at 7, with a Week 7 freeze receipt. So a Week 7 run must exist, be selected and be frozen before its first kickoff even in the fallback. Week 6 is never frozen or closed.

## Clock (UTC)

| When | Event |
|---|---|
| Tue Oct 13 14:00 | Pivot gate (run sheet) |
| Tue Oct 13 ~20:00 | Target time for the Production `freeze_week.py` |
| Tue Oct 13 21:30 | Latest operational time for the Production freeze |
| Tue Oct 13 22:00 | Hard boundary: `freeze_week.py` compares the database clock with the run's earliest predicted kickoff minus one hour. At or after it, the run is marked `evidence_class = 'missed'`; that is irreversible and the run can never be frozen |
| Tue Oct 13 23:00 | First Week 7 kickoff |

## Ratings input

Choose exactly one, decided before building and recorded:

1. **Corrected ratings through Week 6 (default).** The upstream chain below completes and verifies through the Week 7 live rating manifest. Week 7 forecasts use it.
2. **Currently selected post-Week-5 corrected manifest (`c83b1423…`).** Only if option 1 did not complete in time. The Week 7 run must state that Week 6 results are not in its ratings; this is a larger quality compromise that needs its own explicit owner decision.

## Verified command reference

Checked against the argparse definitions and main bodies of each script. Defaults matter: some scripts write unless told otherwise.

| Script | Write default | Environment selection | Notes |
|---|---|---|---|
| `scripts/pipeline/rebuild_6a.py` | operation-specific | Preview R2 only | Positional `preflight\|build\|verify\|publish`, `--plan`, `--expected-code-sha` (required), `--stage`. `make rebuild-6a` does **not** pass `--plan`, so it runs the default `conf/rebuild/6a_v1.yaml`; call the script directly |
| `publish_team_stats.py` | **writes** | `--environment` | `--dry-run` and `--diff` for the dry run; `--as-of-week` or `--weeks`; Silver pins `--byplay-version --drives-version --games-version --game-outcomes-version --teams-version` |
| `verify_team_stats.py` | read-only | `--environment` | `--as-of-week` (required), `--season`, `--min-rho` |
| `capture_data_first_phase2.py` (`scripts/research/`) | `--mode dry-run\|apply` | `--environment` | `--kind pregame`, `--run-id`, `--max-requests` (required), `--expected-code-sha` |
| `build_corrected_live_lock.py` | local file | none | `--week` (required), `--out` (required); `--base-lock` and `--parents` default to the Week 5 files and must be passed |
| `build_v5_intended_update_2026.py` | `--apply` | R2 | `--run-id --expected-code-sha --source-lock --local-output` (required), `--previous-manifest`, `--preflight-evidence` |
| `verify_v5_intended_update_2026.py` | `--apply` | R2 | `--source-lock` (required), `--manifest-uri`, `--local-output` |
| `publish_v5_intended_update_ratings.py` | `--apply` | `--environment` | `--rating-manifest-uri` (required) |
| `build_v5_intended_update_forecasts.py` | `--apply` | R2 | `--release-tag --expected-code-sha --source-lock --local-output --bridge-source --rating-source` (required), `--live-as-of`, `--preflight-evidence`; never `--display-only` here |
| `build_v5_corrected_live_serving.py` | `--apply` | R2 | `--source-lock --release-tag --market-ref-uri --as-of --local-output` (required), `--expected-manifest-sha`, `--expected-code-sha`; never `--display-only` here. The run ID is `2026w7-v5repair-<release-tag>` |
| `verify_v5_corrected_live_serving.py` | `--apply` | R2 | `--source-lock --release-tag` (required), `--expected-receipt-sha`, `--expected-code-sha` |
| `package_v5_corrected_live_run.py` | `--apply` | R2 | `--source-lock --release-tag --bridge-uri --rating-uri` (required), `--expected-packet-sha`, `--expected-code-sha` |
| `authorize_v5_intended_update_preview.py` | `--apply` | Preview only | Legacy single-run mode: `--week --decision-ref --release-tag`; apply adds `--expected-record-sha --expected-code-sha`, needs a clean tree and the Preview **migrator** login |
| `seed_week_schedule.py` | `--apply` | `--environment` | `--source-lock --week` (required) |
| `publish_game_venues.py` | **writes** | `--environment` | `--dry-run` for the dry run; `--only-missing` never touches existing rows; `--supplement` for reviewed venue records |
| `publish_to_db.py` | **writes** (no dry run) | `DATABASE_URL` + `CFB_ARTIFACT_ENV` | No `--environment` flag. `--year --week --from-artifact --run-id --config --state`; `--allow-partial-slate` is not used for a frozen run |
| `select_public_run.py` | writes | `--environment` (`PREVIEW_DATABASE_URL` or `DATABASE_URL`) | `--year --week --run-id --reason` (all required) |
| `build_6a_bridge_verifier.py` | `--apply` | `--environment` | `--rating-manifest-uri --six-a-run-id --six-a-root-sha256` (required), `--weeks`, `--season` |
| `publish_matchup_data.py` | `--apply` | `--environment` | `--rating-manifest-uri` (required) plus either `--measurement-manifest-uri` or the pair `--six-a-run-id`/`--six-a-root-sha256`; `--weeks`; `--expect-payload-sha` |
| `verify_matchup_data.py` | read-only | `--environment` | Same rating, measurement/6A and `--weeks` flags as the publisher |
| `stage_v5_artifacts.py` | `--apply` | `--source`/`--target` (default preview → production) | `--run WEEK=RUN_ID` (repeatable), `--receipt` (required), `--predictions-only`; apply adds `--expected-receipt-sha256 --expected-code-sha` and needs a clean tree |
| `freeze_week.py` | **writes** (no dry run) | `DATABASE_URL` + `CFB_ARTIFACT_ENV` | `--year --week --decision-ref`, `--waiver`. Never run it as a check |
| `rollback_week_release.py` | — | — | **Being built in parallel; not on `dev` yet.** Its flags must be confirmed against its argparse before step P10 is approved |

**Roles and wrappers.** `zsh scripts/ops/with_preview_env.sh` sets `PREVIEW_DATABASE_URL` to the Preview pipeline login (`cks_preview_pipeline`), `DATABASE_URL` to the Preview **migrator** login and `CFB_ARTIFACT_ENV=preview`. V5 writes require both `session_user` and `current_user` to be the pipeline role, so the scripts that read `DATABASE_URL` (`publish_to_db.py`, `freeze_week.py`) must run in Preview with `DATABASE_URL` re-pointed at the pipeline URL inside the wrapper (form below). The Preview authorizer is the exception: it requires the migrator. `zsh scripts/ops/with_production_pipeline_env.sh` sets `DATABASE_URL` to `cks_prod_pipeline` and `CFB_ARTIFACT_ENV=production`. All commands below run from a clean committed tree with `PYTHONPATH=src:.`.

```bash
# Preview form for scripts that read DATABASE_URL (publish_to_db.py, freeze_week.py)
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh \
  zsh -c 'DATABASE_URL="$PREVIEW_DATABASE_URL" exec uv run python scripts/pipeline/<script>.py <args>'
```

## Upstream data chain (Preview R2 and catalog)

Each step is its own go-ahead. Record run IDs, root hashes and receipts in the session log as they are produced; nothing below is pre-filled.

1. **Week 6 6A rebuild: verify, then publish.** The build of `6a-rebuild-w6-20261012-r2` passed all 11 stages on 2026-10-12.
   ```bash
   uv run python scripts/pipeline/rebuild_6a.py verify  --plan conf/rebuild/6a_w6_v1.yaml --expected-code-sha $(git rev-parse HEAD)
   uv run python scripts/pipeline/rebuild_6a.py publish --plan conf/rebuild/6a_w6_v1.yaml --expected-code-sha $(git rev-parse HEAD)
   ```
   Then fill the published root-manifest hash into `conf/rebuild/6a_task4_w6_v1.yaml` and commit (the plan pins the published root).
2. **Task 4 through Week 6:** `rebuild_6a.py preflight|build|verify|publish --plan conf/rebuild/6a_task4_w6_v1.yaml --expected-code-sha $(git rev-parse HEAD)`. Record the receipt `manifest_sha256`.
3. **6B Week 6 frames:** fill `docs/plans/2026-10-08/6b-w6-frames-plan-template.yaml` into `conf/rebuild/` (Task 4 receipt sha, cutoff equal to Task 4's `cutoff_2026`, the Week 6 pins; keep `6b_source_refs_w5_v1.json` as the plan's refs), commit, then `rebuild_6a.py preflight|build|verify|publish --plan <6b w6 plan> --expected-code-sha $(git rev-parse HEAD)`.
4. **Successor lock through Week 6:** `build_corrected_successor_lock.py --base-lock conf/rebuild/source_lock_2026_w6_v1.json --refs conf/rebuild/6b_source_refs_w6_v1.json --parents conf/rebuild/silver_2026_parents_w6_v1.json --rebuild-run-id 6a-rebuild-w6-20261012-r2 --rebuild-root-sha256 <6A root> --task4-run-id 6a-task4-w6-r1 --task4-root-sha256 <Task 4 root> --task4-receipt-sha256 <Task 4 receipt> --replay-run-id <6B w6 run> --replay-root-sha256 <6B root> --week6-display-run-id 2026w6-v5repair-20261008-d2 --out conf/rebuild/successor_lock_w6_v1.json`. Every rebuild default points at Week 5 artifacts, so every one is passed explicitly. Commit the lock.
5. **Week 7 live lock:** `build_corrected_live_lock.py --week 7 --base-lock conf/rebuild/successor_lock_w6_v1.json --parents conf/rebuild/silver_2026_parents_w6_v1.json --out conf/rebuild/successor_lock_w7live_v1.json`. Commit the lock.
6. **Week 7 live rating:** `build_v5_intended_update_2026.py --run-id v5-intended-update-2026-corrected-w7live-r1 --expected-code-sha $(git rev-parse HEAD) --source-lock conf/rebuild/successor_lock_w7live_v1.json --local-output <scratch dir>` (preflight), review, then the same with `--apply --preflight-evidence <preflight file>`. Then `verify_v5_intended_update_2026.py --source-lock conf/rebuild/successor_lock_w7live_v1.json --manifest-uri <w7live rating manifest>` (dry run, then `--apply`).
7. **Ratings to Preview:** `with_preview_env.sh uv run python scripts/pipeline/publish_v5_intended_update_ratings.py --rating-manifest-uri <w7live rating manifest> --environment preview` (dry run, then `--apply`).
8. **Team stats as-of 7 (Preview):**
   ```bash
   PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/publish_team_stats.py \
     --season 2026 --as-of-week 7 --environment preview <five Silver --*-version pins from the Week 6 closeout> --dry-run --diff
   # apply: same command without --dry-run --diff
   PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/verify_team_stats.py \
     --season 2026 --as-of-week 7 --environment preview
   ```
   The dry run must show no change to as-of weeks 1–6.
9. **Fresh Week 7 market capture:** `capture_data_first_phase2.py --kind pregame --mode dry-run --run-id <id> --environment preview --season 2026 --max-requests <n> --expected-code-sha $(git rev-parse HEAD)`, then `--mode apply`. Reconcile all 59 FBS games separately for spread and total; record the capture time, missing game IDs and the next refresh (AGENTS.md session rule 6). The serving builder refuses an incomplete market, so a gap means a later capture, not a waiver.
10. **Forecasts, serving, verify, package** (same `--release-tag` throughout; the run ID becomes `2026w7-v5repair-<release-tag>`):
    - `build_v5_intended_update_forecasts.py --release-tag <tag> --expected-code-sha $(git rev-parse HEAD) --source-lock conf/rebuild/successor_lock_w7live_v1.json --local-output <dir> --bridge-source <B2 bridge-manifest URI> --rating-source <w7live rating manifest> --live-as-of <forecast time>` (preflight, then `--apply --preflight-evidence <file>`). The B2 bridge is `artifacts/research/data-first-football-v1/forecasts/intended-update/runs/v5-intended-update-corrected-w5-r1/bridge-manifest.json` unless the bundle changes.
    - `build_v5_corrected_live_serving.py --source-lock conf/rebuild/successor_lock_w7live_v1.json --release-tag <tag> --market-ref-uri <step 9 snapshots ref> --as-of <ISO time> --local-output <dir>` (dry run, then `--apply --expected-manifest-sha <sha> --expected-code-sha <sha>`).
    - `verify_v5_corrected_live_serving.py --source-lock conf/rebuild/successor_lock_w7live_v1.json --release-tag <tag>` (dry run, then `--apply --expected-receipt-sha <sha> --expected-code-sha <sha>`).
    - `package_v5_corrected_live_run.py --source-lock conf/rebuild/successor_lock_w7live_v1.json --release-tag <tag> --bridge-uri <B2 bridge> --rating-uri <w7live rating manifest>` (dry run, then `--apply --expected-packet-sha <sha> --expected-code-sha <sha>`).
    All three refuse once the first Week 7 game has started; build well before 22:00Z.
11. **Preview authorization:**
    ```bash
    PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/authorize_v5_intended_update_preview.py \
      --week 7 --release-tag <tag> --decision-ref preview-rehearsal-display-only-week6
    # apply with the printed record_sha256:
    #   ... --apply --expected-record-sha <record_sha256> --expected-code-sha $(git rev-parse HEAD)
    ```
    The decision reference is the one stored on the existing Preview B2 approval row. In this legacy single-run mode the authorizer re-reads that approval and requires `first_live_week = 5`; if the owner has already run the cutover's `UPDATE … SET first_live_week = 6` in Preview, this step fails closed and needs an owner decision (revert the row or use packet mode), not a workaround.

## Preview sequence

In the table, `with_preview_env.sh` is shorthand for `PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh`, and "pipeline-role form" is the `DATABASE_URL="$PREVIEW_DATABASE_URL"` form above.

| Step | Command (Preview) | Dry run → apply |
|---|---|---|
| P1 | Context check: R2 backend, Preview credentials present (never printed), role identities, grants, migration ledger, no active lease, clean committed SHA; before-state export of selections Weeks 0–6, `current_week` (2026, 6, d2), approvals and authorizations | read-only |
| P2 | `with_preview_env.sh uv run python scripts/pipeline/seed_week_schedule.py --source-lock conf/rebuild/successor_lock_w7live_v1.json --environment preview --week 7` | default dry run → `--apply` |
| P3 | `with_preview_env.sh uv run python scripts/pipeline/publish_game_venues.py --environment preview --only-missing` | `--dry-run` first (the command **writes** without it) → apply. A missing city fails the publish gate; fill gaps with a reviewed `--supplement` file |
| P4 | Pipeline-role form: `publish_to_db.py --year 2026 --week 7 --from-artifact --run-id <run_id> --config conf/weekly_bets/v5_intended_update_2026.yaml --state published` | No dry run exists. The release authorization (step 11), schedule (P2) and venue cities (P3) must already pass. One transaction: inserts the run and predictions, upserts the Week 7 `site_week_selections` row (reason `validated V5 publication`) and sets `current_week` from (2026, 6) to (2026, 7). Weeks 0–6 selections are not touched |
| P5 | `with_preview_env.sh uv run python scripts/pipeline/select_public_run.py --year 2026 --week 7 --run-id <run_id> --reason "<decision reason>" --environment preview` | Re-runs every selection guard. Because P4 already selected the run, it returns without writing (the stored reason stays `validated V5 publication`); a refusal here means stop |
| P6 | `with_preview_env.sh uv run python scripts/pipeline/build_6a_bridge_verifier.py --rating-manifest-uri <w7live rating manifest> --six-a-run-id 6a-rebuild-w6-20261012-r2 --six-a-root-sha256 <6A root> --season 2026 --weeks 7 --environment preview` | default dry run → `--apply` (write-once R2 object beside the rating manifest). Runs after P4 because its database gates require the rating manifest to be the site's selected source |
| P7 | `with_preview_env.sh uv run python scripts/pipeline/publish_matchup_data.py --season 2026 --weeks 7 --rating-manifest-uri <w7live rating manifest> --six-a-run-id 6a-rebuild-w6-20261012-r2 --six-a-root-sha256 <6A root> --environment preview` | default dry run (prints the payload sha) → `--apply --expect-payload-sha <sha>` |
| P8 | `verify_matchup_data.py` with the same `--season --weeks --rating-manifest-uri --six-a-run-id --six-a-root-sha256 --environment preview` | read-only; must report VERIFIED with 0 differing rows |
| P9 | Readback: `current_week` (2026, 7, run); Week 7 selection; Weeks 0–6 selections byte-equal to P1; run `published`/`pending`, predicted = expected = lined; ratings, as-of-7 stats and Week 7 matchups served; local site via `CFB_PUBLICATION_MODE=predictions zsh scripts/ops/run_web_local.sh preview` | read-only |
| P10 | Rollback proof under the Preview owner/migrator login: `rollback_week_release.py` (in progress; described as removing the unfrozen, published, pending Week 7 selection and restoring `current_week` to (2026, 6) with d2 active). Review its dry run first | dry run → apply, then readback equal to P1. The rollback only handles an unfrozen run, so it is proven before any freeze |
| P11 | Re-apply: the same P4 and P5 commands (the run row insert is `ON CONFLICT DO NOTHING`; the rerun proves the re-publish of an existing published run), then P8 and P9 again | as P4–P9 |

A Preview freeze is not part of the gate. If the owner wants the freeze guard rehearsed, it runs only after P11, in the pipeline-role form (`freeze_week.py --year 2026 --week 7 --decision-ref <ref>`), as its own go-ahead and before 22:00Z; after it the Preview run can no longer be rolled back by P10.

## Production sequence (user-run or explicitly instructed applies)

| Step | Command (Production) | Dry run → apply |
|---|---|---|
| R1 | Separate exact owner release decision naming the ratings input option, run ID, artifact sha, Preview evidence and the freeze decision reference | — |
| R2 | `uv run python scripts/pipeline/stage_v5_artifacts.py --run 7=<run_id> --receipt <receipt path> --predictions-only` (defaults `--source preview --target production`) | dry run → review receipt → `--apply --expected-receipt-sha256 <sha> --expected-code-sha <sha>` from a clean tree, then byte readback |
| R3 | If the Production catalog lacks the post-Week-6 Silver versions used by team stats: `promote_silver_versions.py --season 2026 --from preview --to production --datasets … --version …` | `--dry-run` → apply (user-run) |
| R4 | Owner SQL on the Production branch: one `v5_intended_update_release_authorizations` row for production/2026/7/run, with the fields of `authorization_record()` in `authorize_v5_intended_update_preview.py` but `environment = 'production'` and the Production-staged artifact URI and sha (ID pattern `production-<run_id>-<artifact sha first 12>`). The B2 bundle approval already exists in Production with `first_live_week = 6`, so no approval insert | user-run, then a read-only check as `cks_prod_pipeline` that exactly one row exists |
| R5 | `with_production_pipeline_env.sh uv run python scripts/pipeline/publish_v5_intended_update_ratings.py --rating-manifest-uri <w7live rating manifest> --environment production` | dry run → `--apply` |
| R6 | `with_production_pipeline_env.sh uv run python scripts/pipeline/publish_team_stats.py --season 2026 --as-of-week 7 --environment production <same Silver pins> --dry-run --diff`, apply, then `verify_team_stats.py --season 2026 --as-of-week 7 --environment production` | `--dry-run --diff` → apply → verify |
| R7 | `seed_week_schedule.py --source-lock conf/rebuild/successor_lock_w7live_v1.json --environment production --week 7` | dry run → `--apply` |
| R8 | `publish_game_venues.py --environment production --only-missing` | `--dry-run` → apply |
| R9 | `with_production_pipeline_env.sh uv run python scripts/pipeline/publish_to_db.py --year 2026 --week 7 --from-artifact --run-id <run_id> --config conf/weekly_bets/v5_intended_update_2026.yaml --state published` | no dry run; same effect as P4 |
| R10 | `select_public_run.py --year 2026 --week 7 --run-id <run_id> --reason "<decision reason>" --environment production` | guard re-check; no-op after R9 |
| R11 | `publish_matchup_data.py --season 2026 --weeks 7 --rating-manifest-uri <w7live> --six-a-run-id 6a-rebuild-w6-20261012-r2 --six-a-root-sha256 <6A root> --environment production`, then `verify_matchup_data.py` with the same flags | dry run → `--apply --expect-payload-sha <the Preview P7 sha>` → verify. The bridge verifier from P6 lives in the shared bucket and is reused |
| R12 | Readback as in P9 against Production, plus the live site | read-only |
| R13 | `with_production_pipeline_env.sh uv run python scripts/pipeline/freeze_week.py --year 2026 --week 7 --decision-ref <approved ref>` at about 20:00Z, no later than 21:30Z | No dry run. Requires predicted = expected and, without a recorded `--waiver`, lined = expected. Read back `state = 'frozen'`, `evidence_class = 'live'`, `frozen_at` and the freeze receipt |
| R14 | Update `docs/status.md` from actual results | — |

Every `R*` command runs as `PYTHONPATH=src:. zsh scripts/ops/with_production_pipeline_env.sh uv run python scripts/pipeline/<script>.py …` except R2 and R3 (storage and catalog tools run with plain `uv run`) and the owner SQL in R4. A Production rollback before R13 uses the same `rollback_week_release.py` under the Production owner login after its own go-ahead; after R13 the frozen run stays.

## What the fallback does not do

- It does not replace Weeks 0–6 with corrected replays, so the Performance record stays on the currently selected runs and Week 6's record stays the display-run grades (spread 35-19-1, total 23-32-0 on 55 games).
- It does not clear the waived integrity items (EPA replacement, quality follow-ups, scoring and descendant recertification, the 2025 matchup candidate).
- The cross-lineage banner on Weeks 0–5 matchup pages persists until a later corrected-replay cutover.

## Release decision

If the pivot gate trips, the owner issues a separate exact release decision naming: the ratings input option, the Week 7 run ID, the artifact and receipt hashes and the freeze decision reference. Nothing here is pre-authorized.

## Follow-up after the fallback

The corrected Weeks 0–6 replay cutover remains an open obligation. It runs as an Advance-Mode selection from the post-fallback state (Weeks 0–7 selected, `current_week` 7), which changes the before-state in the packet design.

## Not verified when this was written

- `rollback_week_release.py` does not exist on `dev` yet; P10 and the Production rollback depend on its final CLI and scope (for example, whether it also touches the Week 7 matchup rows).
- Re-publishing an existing published run (P11) has not been exercised; if `publish_to_db.py` refuses, stop and decide rather than deleting rows.
- The successor lock and live lock CLIs were checked by flags only; the Week 6 inputs (6B frames, Task 4 receipt) do not exist yet.
