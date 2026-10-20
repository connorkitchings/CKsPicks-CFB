# 2026-10-20 — Week 8 line refresh: Preview and Production release

Market-only refresh of the Week 8 spreads and totals ahead of the first 23:00Z kickoff. Code and manifest commits on `dev`: `97d5b979` (`feat(pipeline): add market-only revision builder`) and `e94cf35a` (`chore(season): add Week 8 line-refresh revision manifest`).

## Outcome

- Active releases are now `production-season-2026-125158328e025fb89c96ce0d` and `preview-season-2026-125158328e025fb89c96ce0d`, replacing `…2cdf8916d915e21b3f25fa71`. Week 8 is 56/56 predicted and lined, data as of 2026-10-20T14:39:00Z.
- Activation readback SHA-256 on both databases: `43349ac3cb1e477be4541e23bcdb1179dd11b4c9aa00bb5ad999df67df8bc348`. Projection payload SHA-256: `eae0069973b97dc523d9af728ee090c0654e0f49b8492973c10f39c4082c799d`.

## Provider calls (Week 8 only)

- `ingest_week.py --year 2026 --week 8 --entities betting_lines`: 112 CFBD betting-line records.
- `fetch_odds_api_market_quotes.py --year 2026 --week 8 --confirm`: 404 Odds API quotes, ~2 credits. Last capture 14:33:30Z. The Odds API board also returned 98 events outside the Week 8 schedule, which were skipped.
- No schedule, plays or historical weeks were fetched.

## Revision and prepare

- `scripts/pipeline/build_market_revision.py` built `conf/season/2026/revision_manifest_w8_v3.json` from `w8_v2`. Only the market-quotes reference, `captured_at`, the Week 8 pre-week cutoff (2026-10-20T14:39:00Z) and `revision_id` (`season-2026-w8-preview-r3`) differ. Run it as a module (`uv run python -m scripts.pipeline.build_market_revision`); invoking the file directly fails with `No module named 'scripts'`.
- Coverage: 56/56 games with a spread and 56/56 with a total.
- `run_season.py prepare` passed all 32 checks. It was run from a clean detached worktree pinned to `e94cf35a` because another session had uncommitted files in the primary checkout, and `prepare` and `release` reject any dirty tree (including untracked files). `code_sha` equals that commit exactly.

## Verification

- Parity against `season-2026-2cdf8916d915e21b3f25fa71`: predictions (888), ratings (1,242) and completed-week grades (776) identical within 1e-9. Row counts differ only in `market_quotes` (1,693 to 1,695) and `market_snapshot_quotes` (3,369 to 3,374). Per-table hashes differ because they include release-ID columns.
- Preview reviewed by the owner before Production.
- Live Production: `/`, `/results`, `/ratings`, `/performance` and `/api/health` return 200; `/charts` returns 404. Health reports the new release, Week 8, 56/56 predicted and lined, data as of 2026-10-20T14:39:00Z.

## Rollback

Production rollback target: `production-season-2026-2cdf8916d915e21b3f25fa71` (owner-authorized only).
