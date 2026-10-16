# Weekly Operational Runbook

> **The primary recurring operational guide for CFB Model V5.**
>
> Supersedes manual multi-stage patch pipelines. The single operational entry point for preparing, rehearsing, and activating atomic weekly releases is `scripts/pipeline/run_season.py`. The legacy `make weekly`, `publish-week`, `freeze-week` and `close-week` targets are removed and exit with an error.

---

## Architecture Overview

1. **Chronological Season Engine (`run_season.py`)**:
   - Reconstructs the 2026 season from Week 0 through completed weeks using pre-week observations only.
   - Computes point-in-time ratings, predictions, lines, edges, and grades.
   - Enforces 23 strict verification rules (`season_verification_v2`).
2. **Fixed-Schema Atomic Releases (Migration 0025)**:
   - Staging is completely isolated from live serving.
   - Activation checks owner policy, expected prior release, candidate verification, and readback hash consistency.
   - Single atomic transaction switches release status and populates `season_release_*` tables.
   - Web application queries resolve through the active release context, ensuring 100% atomic cutover across all views.

---

## Environments

| | Preview | Production |
|---|---|---|
| Neon branch | `preview-2026` (durable 2026 Preview branch) | production branch (separate from `preview-2026`) |
| Pipeline login (stage + activate releases) | `cks_preview_pipeline` | `cks_prod_pipeline` |
| Owner/migrator login (migrations, rollback) | `cks_preview_migrator` | owner/migrator URL (see [Owner credential](#owner-credential)) |
| Web login (read-only, Vercel) | separate read-only web credential | `cks_prod_web` |
| Local wrapper | `zsh scripts/ops/with_preview_env.sh` | `zsh scripts/ops/with_production_pipeline_env.sh` (pipeline), `zsh scripts/ops/with_production_owner_env.sh` (owner) |
| `CFB_ARTIFACT_ENV` set by wrapper | `preview` | `production` |
| R2 credential set | `CFB_R2_PREVIEW_*` | `CFB_R2_*` |

- **Pipeline and owner credentials** live in the local macOS Keychain and are injected by the wrappers; never copy them into the repository, Vercel, shell history or logs. Vercel receives only the separate read-only web `DATABASE_URL`. `with_preview_env.sh` sets `PREVIEW_DATABASE_URL` (pipeline role) and `DATABASE_URL` (migrator role, for migrations only). Never use a pipeline or migrator connection in Vercel.
- **Roles (Migration 0025):** the pipeline group role (`cks_pipeline`) may `SELECT`/`INSERT` `season_releases` and the `season_release_*` projection tables and activates only through `activate_season_release()`; it cannot change `season_release_policies`. The web group role (`cks_web`) has `SELECT` only. Rollback refuses any login whose role ends in `_pipeline` or `_web` (`src/cks_picks_cfb/season/release.py`).
- **Chart tables (Migration 0026) and the `charts_v1` projection set.** Releases now carry three more projection tables (`team_season_roster`, `team_game_stats`, `team_adjusted_epa`) for the Charts page. **Apply `contracts/migrations/0026_team_chart_tables.sql` to Preview and then to Production, as the owner/migrator, before staging any release.** Staging now requires the `charts_v1` set and the `team_chart_reconciliation` verification check: a `core_v1` or partial candidate is refused, and staging fails with `projection schema missing` if 0026 is absent. Releases staged before 0026 keep their recorded `core_v1` set, so readback, activation and Production owner rollback of them still work (Preview has no supported rollback: recover Preview by preparing and releasing a new candidate, see [Rollback Procedure](#rollback-procedure)). The web app shows charts only for an active `charts_v1` release; until then `/charts` says charts arrive with the next weekly release. The pinned `teams` input must carry each team's `conference` (CFBD teams data). If the implementation merges before a weekly update but 0026 cannot be applied in time, stage that week's release from the pre-merge commit, still under the full clean-checkout, independent Preview rehearsal and owner-approved Production activation rules.
- **Object storage:** `CFB_ARTIFACT_ENV` selects the R2 credential set (`CFB_R2_PREVIEW_*` for `preview`, `CFB_R2_*` otherwise). Both sets currently name the same bucket, `cks-picks-cfb-preview`; immutable artifacts are checksummed and environment-neutral, and environment separation is by Neon branch. Any command run *without* a wrapper defaults to `CFB_ARTIFACT_ENV=production`, so every data command below runs under a wrapper.
- **Vercel:** the [site](https://c-ks-picks-cfb.vercel.app) (Root Directory `web/`) deploys from `main` and reads Production through `cks_prod_web`. `dev` is the working branch.
- **Run locally against an environment:** `make web-local ENV=preview` (or `ENV=production`).

---

## Weekly Cadence (Step-by-Step)

Placeholders: `<COMPLETED_WEEK>` is the week whose finals are in; `<NEXT_WEEK>` is `<COMPLETED_WEEK> + 1`, the week being forecast. Each `make season-*` target wraps the command shown next to it; `WEEK` in those targets is always `<NEXT_WEEK>`.

> **Clean tree, one commit.** `run_season.py prepare` refuses a dirty working tree, and `release` refuses unless `HEAD` is the exact commit the candidate was prepared from. Commit the revision manifest *before* prepare, and **do not commit anything between prepare and the last release** (Preview and Production). Session logs and `docs/status.md` updates wait until Step 4. Ignored outputs under `artifacts/season/` do not dirty the tree.

### 1. Capture Lines, Build the Revision, Prepare the Candidate

Run this after every completed-week game is final and before the first upcoming-week kickoff.

**1a. Choose the two cutoffs.** Both are UTC ISO-8601 timestamps that become part of the revision manifest:

- `POST_WEEK_CUTOFF`: the post-week cutoff of `<COMPLETED_WEEK>`, after its last game has finished and finals are posted. It is passed as the builder's `--as-of` (Silver as-of). Example: Week 6's was `2026-10-11T15:00:00Z` (Sunday morning), used to build the Week 7 manifest.
- `PRE_WEEK_CUTOFF`: the pre-week cutoff of `<NEXT_WEEK>`. It must be later than every line capture in 1b that should count, at least 6 hours after every earlier-week kickoff, and **strictly before the first `<NEXT_WEEK>` kickoff** (`season/prepare.py` refuses otherwise). Example: Week 7's was `2026-10-13T18:00:00Z`; Week 8's first kickoff is Tuesday `2026-10-20T23:00:00Z`, so `2026-10-20T18:00:00Z` works.

```bash
POST_WEEK_CUTOFF="<YYYY-MM-DDTHH:MM:SSZ>"
PRE_WEEK_CUTOFF="<YYYY-MM-DDTHH:MM:SSZ>"
RUN_ID="w<NEXT_WEEK>-revision-$(date -u +%Y%m%d%H%M)"   # fresh for every real build
```

**1b. Capture lines.** The builder includes every registered 2026 CFBD `betting_lines` and Odds API capture registered *before the builder runs*, so capture first. Run under the Preview wrapper:

```bash
# Completed-week CFBD lines (closing lines) and upcoming-week CFBD lines
CFB_STORAGE_BACKEND=r2 PYTHONPATH=.:src zsh scripts/ops/with_preview_env.sh \
  uv run python scripts/data/ingest_week.py --year 2026 --week <COMPLETED_WEEK> --entities betting_lines
CFB_STORAGE_BACKEND=r2 PYTHONPATH=.:src zsh scripts/ops/with_preview_env.sh \
  uv run python scripts/data/ingest_week.py --year 2026 --week <NEXT_WEEK> --entities betting_lines

# Upcoming-week Odds API quotes (paid: one request, ~2 credits; omit --confirm for the estimate only)
CFB_STORAGE_BACKEND=r2 PYTHONPATH=.:src zsh scripts/ops/with_preview_env.sh \
  uv run python scripts/data/fetch_odds_api_market_quotes.py --year 2026 --week <NEXT_WEEK> --confirm
```

The Odds API script must run under the wrapper. Without it, storage falls back to the Production credential set and the capture is registered through whatever `DATABASE_URL` is in `.env`. Betting lines alone need no `--request-inventory`.

Do not run `ingest_season.py --entities games`, `build_expected_request_inventory.py` or `ingest_week.py --entities plays` by hand. The builder's controller run does all three for Weeks 0 to `<COMPLETED_WEEK>`; see 1c.

**1c. Build the revision manifest.** `build_season_revision.py` does the following:

1. Runs the ops controller's `prepare-week` steps under `RUN_ID`, up to `build_team_game_stats`. That means: re-ingest the raw schedule, build a request inventory for each completed week, ingest `plays` and `game_stats` with `--request-inventory`, and build Silver `games`, `game_outcomes`, `plays` and `team_game_stats`.
2. Derives `byplay`, `drives` and `source_reconciliation` from that Silver.
3. Builds one content-addressed cumulative `market_quotes` version.
4. Writes `conf/season/2026/revision_manifest_w<NEXT_WEEK>_v1.json`.

`venues`, `teams` and `score_reconciliation_exceptions` are copied unchanged from `revision_manifest_w<COMPLETED_WEEK>_v1.json`.

```bash
make season-revision WEEK=<NEXT_WEEK> AS_OF="$POST_WEEK_CUTOFF" \
  PRE_WEEK_CUTOFF="$PRE_WEEK_CUTOFF" RUN_ID="$RUN_ID"
# = CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh \
#     uv run python scripts/pipeline/build_season_revision.py \
#       --season 2026 --week <NEXT_WEEK> --environment preview \
#       --as-of "$POST_WEEK_CUTOFF" --pre-week-cutoff "$PRE_WEEK_CUTOFF" \
#       --pipeline-run-id "$RUN_ID"
```

- **It refuses to overwrite** an existing `revision_manifest_w<NEXT_WEEK>_v1.json`. Delete any stale or template file for that week first, such as the hand-made Week 8 template that still carries Week 7 input hashes.
- **`DRY=1` (`--dry-run`) re-checks an existing run; it cannot preview a new one.** It fetches nothing and reads the Silver refs that `RUN_ID` already wrote under `artifacts/preview/pipeline-runs/<RUN_ID>/`, so it fails for a run ID that has not completed. It builds the derived and market versions in a temporary directory and prints the manifest. It uploads, registers and writes nothing, and ignores the overwrite rule.

Check that every completed FBS game has a score, the required play/drive streams and reconciled totals. The `source_reconciliation` build fails on blocking conflicts.

**1d. Refresh the score-reconciliation exceptions.** Prepare requires exact per-team-game score reconciliation. `conf/season/2026/score_reconciliation_exceptions.json` lists the only allowed mismatches as `game_id`, `team` and `reason`. An unlisted mismatch fails, and so does an **unused** exception, for example a game whose play-by-play was repaired. The manifest pins the file by SHA-256 under `score_reconciliation_exceptions`, and prepare fails with `input checksum changed` if the file differs. The builder only copies the previous manifest's entry, and the Week 7 manifest has none. So after each week's finals:

1. Edit the file to list exactly the team-games that do not reconcile through `<COMPLETED_WEEK>`. Add the new week's mismatches and remove any repaired game.
2. Pin it in the new manifest:
   ```bash
   uv run python -c "import hashlib, json, pathlib, sys; m = pathlib.Path(sys.argv[1]); e = 'conf/season/2026/score_reconciliation_exceptions.json'; d = json.loads(m.read_text()); d['score_reconciliation_exceptions'] = {'uri': e, 'sha256': hashlib.sha256(pathlib.Path(e).read_bytes()).hexdigest()}; m.write_text(json.dumps(d, indent=2) + '\n')" \
     conf/season/2026/revision_manifest_w<NEXT_WEEK>_v1.json
   ```
   Prepare's failure lists `score reconciliation differs: game G, team T` (add it) and `unused score reconciliation exception: game G, team T` (remove it). If prepare fails on either, edit the file, repeat this step, commit, and rerun prepare.

**1e. Commit.** Review the manifest, then commit it with the exceptions file so the tree is clean:

```bash
git add conf/season/2026/revision_manifest_w<NEXT_WEEK>_v1.json conf/season/2026/score_reconciliation_exceptions.json
git commit -m "chore(season): add Week <NEXT_WEEK> revision manifest"
git status --porcelain   # must print nothing
```

**1f. Prepare from the clean tree.** Use `PRE_WEEK_CUTOFF` as the run's `--as-of`. For the live upcoming week, the forecast cutoff is the run's `--as-of`. When that week is later reconstructed, its cutoff is the pinned `PRE_WEEK_CUTOFF`. Setting both to the same value makes the published forecast and the later reconstruction agree. `--as-of` cannot be in the future, so run prepare at or after `PRE_WEEK_CUTOFF` and before the first `<NEXT_WEEK>` kickoff:

```bash
make season-prepare WEEK=<NEXT_WEEK> AS_OF="$PRE_WEEK_CUTOFF"
# = CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh \
#     uv run python scripts/pipeline/run_season.py prepare \
#       --model-manifest conf/season/2026/model_manifest_v1.json \
#       --revision-manifest conf/season/2026/revision_manifest_w<NEXT_WEEK>_v1.json \
#       --through-week <COMPLETED_WEEK> --next-week <NEXT_WEEK> \
#       --as-of "$PRE_WEEK_CUTOFF" --output artifacts/season/2026/preview --environment preview
```

`--reconstruct-next-week` (`RECONSTRUCT=1`) is **not** part of the normal weekly run. Pass it only to reconstruct the upcoming week *after* its pre-week cutoff, for example once games have kicked off. It forecasts the full slate at the pinned `PRE_WEEK_CUTOFF` instead of `--as-of`; `--as-of` may then be the current time.

The runner will:
- Recompute measurements, ratings, predictions, and grades.
- Execute the full verification suite (23 verification checks).
- Output the candidate artifact under `artifacts/season/2026/preview/<RELEASE_ID>/`.
- Print the candidate manifest including `release_id` and the `serving_projections` SHA-256.

Read both values back from the retained output:

```bash
uv run python scripts/pipeline/run_season.py status --output artifacts/season/2026/preview
uv run python -c "import json, sys; m = json.load(open(sys.argv[1])); print(m['release_id'], m['output_refs']['serving_projections']['sha256'])" \
  artifacts/season/2026/preview/<RELEASE_ID>/run-manifest.json
```

> **Two forms of the release ID.** The local folder and run manifest use the bare ID (`season-2026-...`). The database stores it prefixed with the environment (`preview-season-2026-...`, `production-season-2026-...`). `run_season.py release`/`rollback` accept either form for `--release-id` and `--expected-previous-release-id`, prepend the environment to a bare ID, and reject an ID prefixed with the other environment. `make season-release RELEASE_ID=` also accepts either form.

---

### 2. Preview Release (Required Before Production)

Production release requires an independent read-only Preview rehearsal proof. Release in Preview first, from the same commit:

```bash
# Current active Preview release
zsh scripts/ops/with_preview_env.sh uv run python -c "
import os, psycopg
with psycopg.connect(os.environ['PREVIEW_DATABASE_URL']) as conn:
    print(conn.execute(\"SELECT release_id FROM season_releases WHERE environment = 'preview' AND status = 'active'\").fetchall())
"

# Stage and activate in Preview
make season-release ENV=preview RELEASE_ID=<RELEASE_ID> \
  PROJECTION_SHA=<PROJECTION_PAYLOAD_SHA256> EXPECTED_PREVIOUS=<ACTIVE_PREVIEW_RELEASE_ID>
# = CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh \
#     uv run python scripts/pipeline/run_season.py release --environment preview \
#       --expected-previous-release-id <ACTIVE_PREVIEW_RELEASE_ID> \
#       --run-manifest artifacts/season/2026/preview/<RELEASE_ID>/run-manifest.json \
#       --projection-payload-sha256 <PROJECTION_PAYLOAD_SHA256>
```

Verify the local web app on Preview (`make web-local ENV=preview`, then `http://localhost:3000`):
- `/` (Picks): Active week picks displayed with correct model margins and edges.
- `/results`: Completed weeks scored with final results.
- `/ratings`: Team ratings ranked accurately.
- `/performance`: Cumulative ATS record matches database grades.

---

### 3. Production Release

Once the Preview release is verified, still with no new commits:

```bash
# Current active Production release (read-only, pipeline role)
zsh scripts/ops/with_production_pipeline_env.sh uv run python -c "
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    print(conn.execute(\"SELECT release_id FROM season_releases WHERE environment = 'production' AND status = 'active'\").fetchall())
"

# Activate in Production: the Preview wrapper supplies the read-only Preview proof
# connection (PREVIEW_DATABASE_URL); the Production pipeline wrapper then sets
# DATABASE_URL and CFB_ARTIFACT_ENV=production.
make season-release ENV=production RELEASE_ID=<RELEASE_ID> \
  PROJECTION_SHA=<PROJECTION_PAYLOAD_SHA256> EXPECTED_PREVIOUS=<ACTIVE_PRODUCTION_RELEASE_ID>
# = CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh \
#     zsh scripts/ops/with_production_pipeline_env.sh \
#     uv run python scripts/pipeline/run_season.py release --environment production \
#       --expected-previous-release-id <ACTIVE_PRODUCTION_RELEASE_ID> \
#       --run-manifest artifacts/season/2026/preview/<RELEASE_ID>/run-manifest.json \
#       --projection-payload-sha256 <PROJECTION_PAYLOAD_SHA256>
```

Production activation is an owner decision.

---

### 4. Deployment and Verification

Commits are allowed again from here.

1. Fast-forward merge `dev` into `main` and push to trigger Vercel deployment:
   ```bash
   git checkout main && git merge dev --ff-only && git push origin main
   git checkout dev
   ```
2. Verify live production URLs:
   - `https://c-ks-picks-cfb.vercel.app/`
   - `https://c-ks-picks-cfb.vercel.app/results`
   - `https://c-ks-picks-cfb.vercel.app/ratings`
   - `https://c-ks-picks-cfb.vercel.app/performance`
   - `https://c-ks-picks-cfb.vercel.app/api/health`
3. Update [`docs/status.md`](../status.md) with the active release ID, week state, and scoreboard.

---

## Rollback Procedure

If an activated Production release needs to be rolled back to a previous verified release. Rollback needs the owner/migrator login (the pipeline and web roles are refused), explicit owner approval and a decision reference, and a clean committed tree:

```bash
make season-rollback RELEASE_ID=<TARGET_PRIOR_RELEASE_ID> \
  EXPECTED_PREVIOUS=<CURRENT_ACTIVE_RELEASE_ID> \
  DECISION_REF="emergency-rollback-<reason>" OWNER_AUTHORIZED=1
# = CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:. zsh scripts/ops/with_production_owner_env.sh \
#     uv run python scripts/pipeline/run_season.py rollback \
#       --environment production --season 2026 \
#       --release-id <TARGET_PRIOR_RELEASE_ID> \
#       --expected-previous-release-id <CURRENT_ACTIVE_RELEASE_ID> \
#       --owner-authorized --decision-ref "emergency-rollback-<reason>"
```

Both IDs may be bare (`season-2026-...`) or `production-`-prefixed. The rollback atomically reactivates the prior release's projections without deleting any data.

**Preview rollback is not supported by the tooling.** `run_season.py rollback --environment preview` connects through `PREVIEW_DATABASE_URL`. `with_preview_env.sh` sets that to the `cks_preview_pipeline` login, which `release.py` refuses for rollback. No wrapper or make target supplies a Preview owner login. The code accepts any login whose session and current role match, that holds `UPDATE` on `season_release_policies`, and whose role does not end in `_pipeline` or `_web`. A read-only check on 2026-10-16 showed that `cks_preview_migrator` holds that `UPDATE` grant (it is not a superuser), but no sanctioned wrapper or CLI path uses it for Preview, so it is not a supported recovery procedure. To change what Preview serves, prepare and release a new candidate instead.

### Owner credential

`scripts/ops/with_production_owner_env.sh` reads the Production owner/migrator URL from the macOS Keychain, exports `DATABASE_URL` and `CFB_ARTIFACT_ENV=production`, and never prints the URL. It exits non-zero if the item is missing or if the URL's login role ends in `_pipeline` or `_web`. The default item is service `ckspicks-cfb/production/owner-url`, account `cks_prod_owner`; override with `CFB_OWNER_KEYCHAIN_SERVICE` and `CFB_OWNER_KEYCHAIN_ACCOUNT`.

**Owner action (one time).** Create the item; `-w` as the last option makes `security` prompt for the URL without echoing it or writing it to shell history:

```bash
security add-generic-password -U \
  -s 'ckspicks-cfb/production/owner-url' -a cks_prod_owner -w
```

Check that it resolves (prints nothing secret):

```bash
zsh scripts/ops/with_production_owner_env.sh /usr/bin/true && echo "owner credential OK"
```
