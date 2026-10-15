# Weekly Operational Runbook

> **The primary recurring operational guide for CFB Model V5.**
>
> Supersedes manual multi-stage patch pipelines. The single operational entry point for preparing, rehearsing, and activating atomic weekly releases is `scripts/pipeline/run_season.py`.

---

## Architecture Overview

1. **Chronological Season Engine (`run_season.py`)**:
   - Reconstructs the 2026 season from Week 0 through completed weeks using pre-week observations only.
   - Computes point-in-time ratings, predictions, lines, edges, and grades.
   - Enforces 22 strict verification rules (`season_verification_v2`).
2. **Fixed-Schema Atomic Releases (Migration 0025)**:
   - Staging is completely isolated from live serving.
   - Activation checks owner policy, expected prior release, candidate verification, and readback hash consistency.
   - Single atomic transaction switches release status and populates `season_release_*` tables.
   - Web application queries resolve through the active release context, ensuring 100% atomic cutover across all views.

---

## Weekly Cadence (Step-by-Step)

### 1. Ingest Completed Games and Market Lines

At the end of a week (Sunday/Monday):
```bash
# Ingest finals, drive, and play data for completed games
uv run python scripts/data/fetch_cfbd_data.py --season 2026 --week <COMPLETED_WEEK>

# Export/update cumulative market quotes
uv run python scripts/data/export_market_quotes.py --season 2026 --week <NEXT_WEEK>
```

Verify that all completed FBS games have scores, required play/drive streams, and reconciled totals.

---

### 2. Prepare the Season Candidate

Run `run_season.py prepare` to build the full candidate through the completed week and forecast the upcoming week:

```bash
CFB_STORAGE_BACKEND=r2 CFB_ARTIFACT_ENV=preview uv run python scripts/pipeline/run_season.py prepare \
  --model-manifest conf/season/2026/model_manifest_v1.json \
  --revision-manifest conf/season/2026/revision_manifest_w<NEXT_WEEK>_v1.json \
  --through-week <COMPLETED_WEEK> \
  --next-week <NEXT_WEEK> \
  --as-of "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output artifacts/season/2026/preview \
  --environment preview
```

*Note:* If mid-week games are included in the upcoming slate, pass `--reconstruct-next-week`.

The runner will:
- Recompute measurements, ratings, predictions, and grades.
- Execute the full verification suite (22 verification checks).
- Output the candidate artifact under `artifacts/season/2026/preview/<release_id>/`.
- Print the candidate manifest summary including `release_id` and `serving_projections` SHA-256.

---

### 3. Preview Rehearsal (Required Before Production)

Production release requires an independent read-only Preview rehearsal proof. Rehearse staging and activation in Preview first:

```bash
# Look up the current active release in Preview:
uv run python -c "
import os, psycopg; from dotenv import load_dotenv; load_dotenv()
with psycopg.connect(os.getenv('PREVIEW_DATABASE_URL')) as conn:
    with conn.cursor() as cur:
        cur.execute(\"SELECT release_id FROM season_releases WHERE environment = 'preview' AND status = 'active'\")
        print('Active preview release:', cur.fetchone())
"

# Execute Preview release activation:
CFB_STORAGE_BACKEND=r2 zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/run_season.py release \
  --environment preview \
  --expected-previous-release-id <ACTIVE_PREVIEW_RELEASE_ID> \
  --run-manifest artifacts/season/2026/preview/<release_id>/run-manifest.json \
  --projection-payload-sha256 <PROJECTION_PAYLOAD_SHA256>
```

Verify the local web app on Preview (`make web-local ENV=preview` or `http://localhost:3000`):
- `/` (Picks): Active week picks displayed with correct model margins and edges.
- `/results`: Completed weeks scored with final results.
- `/ratings`: Team ratings ranked accurately.
- `/performance`: Cumulative ATS record matches database grades.

---

### 4. Production Activation

Once Preview rehearsal is verified:

```bash
# Look up current active release in Production:
uv run python -c "
import os, psycopg; from dotenv import load_dotenv; load_dotenv()
with psycopg.connect(os.getenv('DATABASE_URL')) as conn:
    with conn.cursor() as cur:
        cur.execute(\"SELECT release_id FROM season_releases WHERE environment = 'production' AND status = 'active'\")
        print('Active production release:', cur.fetchone())
"

# Activate in Production (requires both pipeline roles):
zsh -c "
preview_pipe=\$(security find-generic-password -s 'ckspicks-cfb/preview-2026/pipeline-url' -a cks_preview_pipeline -w)
PREVIEW_DATABASE_URL=\"\$preview_pipe\" CFB_STORAGE_BACKEND=r2 zsh scripts/ops/with_production_pipeline_env.sh uv run python scripts/pipeline/run_season.py release \
  --environment production \
  --expected-previous-release-id <ACTIVE_PRODUCTION_RELEASE_ID> \
  --run-manifest artifacts/season/2026/preview/<release_id>/run-manifest.json \
  --projection-payload-sha256 <PROJECTION_PAYLOAD_SHA256>
"
```

---

### 5. Deployment and Verification

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
3. Update [`docs/status.md`](docs/status.md) with the active release ID, week state, and scoreboard.

---

## Rollback Procedure

If an activated release needs to be rolled back to a previous verified release:

```bash
# Rollback requires the owner credential and explicit decision reference:
CFB_STORAGE_BACKEND=r2 uv run python scripts/pipeline/run_season.py rollback \
  --environment production \
  --season 2026 \
  --release-id <TARGET_PRIOR_RELEASE_ID> \
  --expected-previous-release-id <CURRENT_ACTIVE_RELEASE_ID> \
  --owner-authorized \
  --decision-ref "emergency-rollback-<reason>"
```

The rollback atomically reactivates the prior release's projections without deleting any data.
