# Session: Ratings history replay — stopped per contract at Task 1

## TL;DR
- **Worked On:** Executed the user-authorized ratings-history replay contract (`docs/plans/2026-09-27/05-weekly-ratings-history-replay.md`) starting at Task 1.
- **Outcome:** STOPPED per the contract's own stop condition. Investigation proved neithercheap path works: (1) sealed repair pins exact W4 Silver versions in code, and (2) `as_of` is metadata-only downstream of repair — no stage filters by it, so w4-parents + earlier-cutoff builds would mislabel all 215 games. No R2/Neon writes were made.
- **Plan Contract:** `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` (Approved; Amendment 1 added then invalidated by Amendment 1a, both recorded in-plan).
- **Approval / Status:** Awaiting Sol-amendment decision. Live site and all serving state untouched.
- **Blockers:** Per-cutoff history requires new repairs from contemporary Silver + a sealed pin-table change (Contract 07 lineage change).
- **Next:** User picks: authorize the lineage-change amendment, defer weekly history, or drop it.

## Context and Decisions
- Mapped the full chain first: `run_data_first_repair_v2.py` → `run_data_first_possession_measurements.py` → `run_data_first_possession_rating_replay.py` → verifiers → `publish_v5_ratings.py` (frozen-candidate + verifier + parent guards, `ON CONFLICT DO NOTHING`, pipeline lease).
- Found contemporary validated Silver batches for all three cutoffs (08-31, 09-06, 09-13) — but row counts look off (W2 byplay 16k vs W0 126k rows), so coverage verification is required before any use.
- Tried the Amendment-1 shortcut honestly: measurements dry-run preflight at `as_of=2026-09-01` with the w4 repair PASSED — then population inspection showed 215 games (unfiltered), which forced the deeper read that invalidated the approach. The dry run wrote nothing (state `dry_run`, no `--apply`).
- Did not improvise around the pins: changing `SEASON_2026_SILVER_INPUTS` alters sealed Contract 07 lineage and exceeds Terra amendment authority.

## Work Completed
- Read-only investigation across repair/measurements/replay/projection code and Preview R2 + catalog evidence.
- One local dry-run preflight (no writes) that exposed the unfiltered-population fact.
- Plan file: approval recorded, Amendment 1 (path B) added, Amendment 1a (invalidation + stop) added.

## Files Modified
- `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` — approval + amendments (uncommitted)
- `docs/plans/index.md` — status to Approved/executing (uncommitted)
- `session_logs/2026-09-27/17-ratings-history-replay-stop.md` — this record (untracked)

## Validation
- [x] No R2 writes (only reads + one dry-run preflight, exit 0, `dry_run` state)
- [x] No Neon writes (only SELECT audits via restricted roles)
- [x] `git diff --check` clean
- [ ] CI for the pending commit (plan amendments + this log)

## Amendments and Blockers
Contract stop condition triggered (see Amendment 1a). Only decision-grade blocker is the lineage-change question.

## Handoff Notes
- **Resume at:** Commit the three files whenever convenient (docs-only), then answer the direction question. Nothing is half-built anywhere — no cleanup needed.
- **Watch out for:** Do NOT run measurements/replay `--apply` with w4 parents and an earlier `as_of`; the tooling will happily compute mislabeled history (projection guard is the only backstop).

**tags:** ["v5", "ratings", "history", "lineage", "contract-stop"]
