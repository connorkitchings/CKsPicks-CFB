# Phase 2: Data Storage Migration - Setup Guide

> **Goal:** Migrate ~15GB of CFB model data from external drive to Cloudflare R2 cloud storage

## Overview

This guide walks you through setting up cloud storage for the CFB model project, enabling data access without the external drive.

**Current State:**
- ✅ Storage abstraction layer created (`src/data/storage.py`)
- ✅ Migration script ready (`scripts/migration/migrate_to_cloud.py`)
- ✅ boto3 dependency installed
- ✅ External drive accessible with 15.3GB data (2.3GB raw + 13GB processed)

**Target State:**
- Data accessible from Cloudflare R2 bucket
- Project runs without external drive
- Dual-mode support (can switch between local/cloud)

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Cloudflare account (free tier works)
- [ ] External drive connected (for data source)
- [ ] ~15GB of R2 storage available
- [ ] 30-60 minutes for setup and migration

---

## Step 1: Create Cloudflare R2 Bucket (15 min)

### 1.1 Create Account (if needed)
1. Go to https://dash.cloudflare.com/sign-up
2. Sign up with email
3. Verify email address
4. Complete onboarding

### 1.2 Enable R2
1. In Cloudflare dashboard, go to **R2** in left sidebar
2. Click **Enable R2** or **Create Bucket**
3. Review pricing (first 10GB free)
4. Click **Agree & Enable**

### 1.3 Create Bucket
1. Click **Create Bucket**
2. Configure:
   - **Bucket Name:** `cfb-model-data` (must be unique)
   - **Location:** Auto (or choose closest region)
3. Click **Create Bucket**
4. ✅ Bucket created!

---

## Step 2: Create API Credentials (5 min)

### 2.1 Generate API Token
1. In R2 dashboard, click **Manage R2 API Tokens**
2. Click **Create API Token**
3. Configure:
   - **Token Name:** `cfb-model-migration`
   - **Permissions:**
     - ✅ Object Read & Write
     - ✅ Admin Read & Write (optional, for bucket management)
   - **TTL:** Never expire (or set expiration if preferred)
   - **Bucket:** `cfb-model-data` (restrict to specific bucket)
4. Click **Create API Token**

### 2.2 Save Credentials
You'll see three values - **SAVE THESE IMMEDIATELY** (shown only once):

```
Account ID: abc123...
Access Key ID: def456...
Secret Access Key: xyz789...
```

⚠️ **Important:** Store these securely. You won't be able to see them again.

---

## Step 3: Configure Local Environment (5 min)

### 3.1 Update .env File

Open `.env` and add the R2 configuration:

```bash
# Storage backend: Switch from 'local' to 'r2' when ready
CFB_STORAGE_BACKEND='local'  # Change to 'r2' after migration

# R2 Configuration
CFB_R2_BUCKET='cfb-model-data'
CFB_R2_ACCOUNT_ID='<your-account-id>'
CFB_R2_ACCESS_KEY='<your-access-key-id>'
CFB_R2_SECRET_KEY='<your-secret-access-key>'
CFB_R2_ENDPOINT='https://<your-account-id>.r2.cloudflarestorage.com'
```

Replace `<your-...>` values with credentials from Step 2.

### 3.2 Verify Configuration

Test that credentials work:

```bash
# Keep STORAGE_BACKEND='local' for now, we'll test cloud after migration
python -c "
import os
os.environ['CFB_STORAGE_BACKEND'] = 'r2'
from src.data.storage import get_storage
storage = get_storage()
print('✅ R2 connection successful!')
"
```

If you see "✅ R2 connection successful!", you're ready to migrate!

---

## Step 4: Data Inventory (5 min)

Let's see what we're migrating:

### 4.1 Check Data Size
```bash
du -sh "$CFB_MODEL_DATA_ROOT"/{raw,processed}
```

Expected output:
```
2.3G    raw/
13G     processed/
```

### 4.2 Count Files
```bash
find "$CFB_MODEL_DATA_ROOT" -type f | wc -l
```

Expected: ~500-1000 files

### 4.3 List Top-Level Structure
```bash
ls -lh "$CFB_MODEL_DATA_ROOT"
```

You should see directories like:
- `raw/` - API responses (plays, games, teams, etc.)
- `processed/` - Aggregated features (team_game, team_season, etc.)

---

## Step 5: Migration - Dry Run (5 min)

Before copying anything, do a dry run to verify what will be migrated:

### 5.1 Test Migration Script
```bash
python scripts/migration/migrate_to_cloud.py --dry-run
```

This will:
- ✅ Show which files would be copied
- ✅ Calculate total data size
- ✅ Check for any issues
- ❌ Not actually copy anything

Review the output. You should see:
- List of files to copy
- Total data size (should match Step 4)
- No errors

### 5.2 Dry Run with Filter (Optional)
If you want to test with just a subset:

```bash
# Dry run for raw data only
python scripts/migration/migrate_to_cloud.py --dry-run --include raw/

# Dry run for processed data only
python scripts/migration/migrate_to_cloud.py --dry-run --include processed/
```

---

## Step 6: Actual Migration (30-60 min)

Now for the real deal. This will take 30-60 minutes depending on internet speed.

### 6.1 Update Storage Backend

**IMPORTANT:** Switch to R2 backend before migration:

Edit `.env`:
```bash
CFB_STORAGE_BACKEND='r2'  # Changed from 'local'
```

### 6.2 Migrate Raw Data First
Start with the smaller dataset to test:

```bash
python scripts/migration/migrate_to_cloud.py --include raw/ -v
```

This will:
- Copy all files from `raw/` (~2.3GB)
- Show progress for each file
- Verify uploads

Expected time: ~10-15 minutes

### 6.3 Migrate Processed Data
Now copy the larger dataset:

```bash
python scripts/migration/migrate_to_cloud.py --include processed/ -v
```

This will:
- Copy all files from `processed/` (~13GB)
- Show progress for each file
- Verify uploads

Expected time: ~30-45 minutes

### 6.4 Verify Migration
Run a deterministic local-vs-cloud reconciliation:

```bash
PYTHONPATH=. uv run python scripts/migration/verify_cloud_sync.py
```

Expected output shape:

```text
raw: local=<N> cloud=<N> missing_in_cloud=0 extra_in_cloud=0
processed: local=<N> cloud=<N> missing_in_cloud=0 extra_in_cloud=0
```

Notes:
- The verifier compares canonical `.csv` and `.parquet` files.
- macOS metadata files (for example `._data.csv`) are ignored by default.
- Reconciliation artifacts are written to `/tmp/cfb_cloud_sync_verify`.

---

## Step 7: Test Cloud Access (5 min)

Verify you can read data from R2:

### 7.1 Test Storage Abstraction
```bash
PYTHONPATH=. uv run python -c "
from src.data.storage import get_storage
import pandas as pd

# Get storage instance (should use R2)
storage = get_storage()
print(f'✅ Using storage backend: {type(storage).__name__}')

# Test reading a file
try:
    # Try reading a sample file (adjust path as needed)
    files = storage.list_files('processed/')
    print(f'✅ Found {len(files)} files in processed/')

    # Try reading first parquet file
    parquet_files = [f for f in files if f.endswith('.parquet')]
    if parquet_files:
        df = storage.read_parquet(parquet_files[0])
        print(f'✅ Successfully read {parquet_files[0]} ({len(df)} rows)')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

Expected output:
```
✅ Using storage backend: R2Storage
✅ Found <many> files in processed/
✅ Successfully read <sample-file> (<row-count> rows)
```

### 7.2 Test Without External Drive
**This is the moment of truth!**

1. **Eject external drive** (or set `CFB_MODEL_DATA_ROOT` to invalid path)
2. Run health checks:
   ```bash
   make health
   ```
3. If all checks pass, migration is successful! 🎉

If health checks fail, check:
- `CFB_STORAGE_BACKEND` is set to 'r2' in `.env`
- R2 credentials are correct
- Files were uploaded successfully

---

## Step 8: Update REFACTORING_PLAN.md (2 min)

Mark Phase 2 as complete:

1. Open `REFACTORING_PLAN.md`
2. Update Phase 2 status from `⏸️ Blocked` to `✅ Complete`
3. Update checklist items:
   ```markdown
   - [x] Create S3/R2 bucket with versioning ✅
   - [x] Set up lifecycle policies ✅
   - [x] Create storage abstraction class ✅
   - [x] Copy all raw/ data to cloud ✅
   - [x] Copy all processed/ data to cloud ✅
   - [x] Test: Can read data without external drive ✅
   ```

---

## Rollback Instructions

If anything goes wrong, you can rollback:

### Rollback to Local Storage
1. Edit `.env`:
   ```bash
   CFB_STORAGE_BACKEND='local'
   ```
2. Reconnect external drive
3. Run `make health` to verify

All data is still on the external drive - nothing was deleted during migration.

### Delete Cloud Data (if needed)
If you want to start over:
1. Go to R2 dashboard
2. Select bucket
3. Click **Delete Bucket** (or delete individual objects)

---

## Cost Estimation

**Cloudflare R2 Pricing:**
- First 10 GB free
- Additional storage: $0.015/GB/month
- Egress: Free (no bandwidth charges!)

**For ~15GB data:**
- First 10GB: Free
- Remaining 5GB: $0.015 × 5 = $0.075/month
- **Total: ~$0.08/month** (essentially free!)

**Comparison to AWS S3:**
- Storage: $0.023/GB = $0.35/month
- Egress: $0.09/GB for first 10TB
- Much more expensive for data science workloads!

---

## Next Steps

After completing Phase 2:

1. ✅ Phase 2 complete - cloud storage operational
2. 📋 Move to Phase 6 - Integration & Validation
3. 🧪 Run full end-to-end tests with cloud data
4. 🚀 Ready to merge refactoring branch!

---

## Troubleshooting

### Issue: "boto3 not found"
**Solution:** Run `uv sync` to install dependencies

### Issue: "Invalid credentials"
**Solution:**
- Verify credentials in `.env` match Cloudflare dashboard
- Ensure no extra spaces or quotes
- Regenerate API token if needed

### Issue: "Bucket not found"
**Solution:**
- Check bucket name in `.env` matches Cloudflare dashboard
- Verify bucket is in same account as API token

### Issue: "Upload failed"
**Solution:**
- Check internet connection
- Verify API token has write permissions
- Check if file is corrupted locally

### Issue: "Health checks fail after migration"
**Solution:**
- Verify `CFB_STORAGE_BACKEND='r2'` in `.env`
- Test cloud access with Step 7.1
- Check if all files were uploaded successfully

---

## Session Log

Create a session log when complete:
```bash
touch session_logs/2026-02-13/06-refactor-phase-2.md
```

Document:
- ✅ What worked smoothly
- ⚠️ Any issues encountered
- 📊 Migration statistics (time, data size, file count)
- 🎯 Next steps

---

**Last Updated:** 2026-02-13
**Status:** Ready for execution
