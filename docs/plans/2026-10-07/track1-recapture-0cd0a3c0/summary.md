# Track 1 recapture and Preview verification for candidate `0cd0a3c0`

Captured 2026-10-07 16:06-16:15Z. Read-only throughout: GET requests to the Preview, SELECTs in read-only transactions through the restricted wrappers, R2 HEAD, and a venue `--dry-run` (writes nothing to the database; one local quality receipt under git-ignored `artifacts/quality/`). Binding rule chosen by the user: the packet binds to the last code-changing commit `0cd0a3c0`; later docs-only commits do not change shipped files.

## 1. Deployment bound to the SHA

| Item | Value |
|---|---|
| GitHub deployment | `6913424276`, environment `Preview`, sha `0cd0a3c02240b77e82cf71e63552143180d23805`, status `success` ("Deployment has completed", 2026-10-07T15:00:40Z) |
| Preview URL | `https://c-ks-picks-8s2lcbd0y-connorkitchings-projects.vercel.app` |
| `dpl_` ID | `dpl_4QA4B4HxvHmUSDrhUCtvbMV6XJFd` (agent-run `vercel inspect`: target preview, Ready, created 2026-10-07 10:59:29 EDT; alias `c-ks-picks-cfb-git-dev-connorkitchings-projects.vercel.app`). Matches the suffix of the inspect URL GitHub reported. Saved in `vercel-inspect-preview.txt` |
| Deployment protection | None: unauthenticated requests return 200 |

## 2. Preview identity (partly verified)

- **Fixture mode is off (observed):** `/performance` shows 215 replay games and 56 prospective games and `/` shows a 271-game season record; the fixture has two games.
- **Vercel Preview variables (agent-run `vercel env ls preview`, names only):** `CFB_PUBLICATION_MODE=predictions`, `CFB_PUBLICATION_SEASON` (encrypted), `DATABASE_URL` (encrypted, created 54 days ago). **No `CFB_UI_TEST_MODE` variable exists for Preview, so fixture mode is unset (verified).** Saved in `vercel-env-ls-preview.txt`.
- **Restricted `cks_preview_web` login: reported, NOT verified by the agent; the user accepted it as an unverified report (2026-10-07) and directed that no secrets be pulled to disk.** The user's message states the Preview `DATABASE_URL` is bound to `cks_preview_web`. `vercel env ls` shows the value only as "Encrypted", so it cannot show which role the secret connects as, and Preview and Production data are identical, so the pages cannot show it either. Treat it as an unverified report until the role is read from the connection itself (for example in the Neon console).

## 3. Real-data routes (HTML text fetched with `curl`; saved in `preview-pages/`)

| Route | HTTP | Result against audit numbers |
|---|---|---|
| `/api/health` | 200 | `activeRun: null`, `selectedWeek: null`; consistent with `current_week` (2026, 6) and no active run |
| `/` | 200 | "Week 6 Picks Dropping Soon" hold screen; season record spread 128-139-4, total 137-132-1 = replay Weeks 0-4 (100-112-3, 112-102-0) plus Week 5 (28-27-1, 25-30-1) |
| `/results` | 200 | Week 5 28-27-1 / 25-30-1; season 100-112-3 / 112-102-0; "Showing 56 of 56 games" |
| `/performance` | 200 | Replay section: Weeks 0-4 only, 100-112-3 / 112-102-0, 215 and 214 graded. Separate prospective section: Week 5 only, 28-27-1 / 25-30-1, 56 graded each, every row labeled "Prospective · retrospectively attested (no contemporaneous receipt)". No latest-run fallback |
| `/ratings` | 200 | "Post-Week 4" ratings (215 games, weeks 0-4), as expected while Week 6 is unopened |
| `/matchup/401856819` | 200 | UCF at Houston loads with market Houston -12.0, model, final 17-27 and "Stats through Week 4"; no guarded/unavailable state appeared for this game |

Not checked: browser rendering, phone width, the share download, any matchup other than `401856819`, and whether a lineage-mismatch game shows the guarded state (none was sampled). The prospective-unavailable card was not exercised.

## 4. Recapture bound to `0cd0a3c0`

- **Candidate hashes:** `candidate-files-0cd0a3c0.json` hashes the committed blobs of 31 files (original Track 1 files, every `web/` file differing from `main`, and the CI/freeze batch). Of the original manifest's 6 entries, 5 are unchanged; `web/package.json` changed (test registration). The original `track1-evidence/candidate-files.json` is left untouched as history.
- **Serving fingerprints:** re-running `audit_b1_b4.py` and `audit_b5.py` in both environments gives no change against the 14:34Z capture (current week, selections and hashes, Week 5 grade hashes, registrations, ledger, grants, venues, team stats).
- **Pinned Production venue dry run:** same pins (games `31a337df6cf49f1578457ec6`, venues `b569d242e8c4c53b416bfe14`) and same content hashes; 271 games, 271 with city, 269 with state, 0 missing venue IDs, 0 absent games. Production `game_venues` now equals both the 12:56Z before-rows and proposed rows on the seven business columns (`venue_table_compare.py`), so the business diff is still empty. An apply would still rewrite `updated_at` on all 271 rows.
- **Refs:** `main` and `origin/main` are `562319aa`; the latest GitHub Production deployment is for that SHA with URL `c-ks-picks-32ixekgj0-connorkitchings-projects.vercel.app`, the packet's rollback target. The rollback deployment was re-read with `vercel inspect` (section 6).

## 5. Production registration provenance

R2 `LastModified` (`attestation-object-times.json`): Preview attestation 2026-10-07T03:10:11Z, Production attestation **2026-10-07T03:22:45Z** (2026-10-06 23:22:45 EDT), three seconds after the object's own `attested_at`. The commit `491774c1` (2026-10-06 23:20:11 EDT) still described the Production registration as a separate later gate, and the 10-06 wrap-up log reports reading the row back afterwards. So it was written about 2.5 minutes after that commit. **Operator, confirmed by the user in the first person (2026-10-07):** "I (Connor Kitchings) confirm that I manually executed the Week 5 Production prospective registration on October 6 at approximately 23:22 EDT following the Stage 7A validation pass," and asked that it be recorded as verified and authorized by them. This is the user's own statement; the agent did not independently verify the operator, and no other record corroborates it beyond the R2 write time (23:22:45 EDT), which is consistent with it. The database row has no creation timestamp.

## 6. Rollback target (agent-verified)

`vercel inspect` of `c-ks-picks-32ixekgj0-connorkitchings-projects.vercel.app`: `dpl_FiycAhixbCrDsZK638CVXtdq9XNM`, target production, Ready, created 2026-10-04 11:25:13 EDT (`vercel-inspect-rollback-target.txt`). This is the packet's rollback target, and GitHub's latest Production deployment is for `562319aa`.

## 7. Production after promotion (agent-verified, read-only, 16:25-16:40Z)

The user pushed `0cd0a3c0:main`; the agent verified afterwards:

- **Refs:** `origin/main` = `0cd0a3c02240b77e82cf71e63552143180d23805` exactly; PR #2 MERGED (merge commit `0cd0a3c0`); `origin/dev` = `8271bbdd` (two docs-only commits on top). GitHub Production deployment `6915148299` for sha `0cd0a3c0`.
- **Vercel:** `dpl_25cfxMwDLqXRkphiPQCvT9Db18sY`, target production, Ready, created 2026-10-07 12:24:38 EDT; aliases `c-ks-picks-cfb.vercel.app` and two others (`vercel-inspect-production-after-promotion.txt`). Rollback target `dpl_FiycAhixbCrDsZK638CVXtdq9XNM` retained.
- **Live routes** (`production-pages/`, GET only): `/api/health`, `/`, `/results`, `/performance`, `/ratings`, `/matchup/401856819` all return 200. Compared with the verified Preview text:
  - `/ratings`: identical.
  - `/`, `/results`, matchup header: only the "Run published" timestamps differ (different publish times for the same runs in the two databases).
  - `/performance`: the same 270 graded-pick records (214 replay, 56 prospective; `compare_performance_records.py`); only the list order and the freeze-evidence hash differ (Production `9f022418…`, Preview `9b3d04f3…`, as expected). Headline numbers are identical (replay 100-112-3 and 112-102-0; prospective Week 5 28-27-1 and 25-30-1).
  - `/matchup/401856819`: team-stat cells differ. PPA/play shows a dash on Production and some rates differ (for example explosive-play and 3rd/4th-down rates). This is the documented pre-fix Production team stats (no `ppa_per_play` metric; section 4 of the earlier audit), not a regression from the release.
- **Observation (not a defect found in the release):** the order of the graded-pick audit list differs between the two databases, so it appears to have no stable tie-break.
- **Not checked:** browser rendering, phone width, the share download, other matchups, a lineage-mismatch game.
