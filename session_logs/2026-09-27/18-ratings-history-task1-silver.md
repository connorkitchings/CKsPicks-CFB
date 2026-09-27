# Session: Ratings history Task 1 — Silver verification complete

## TL;DR
- **Worked On:** Task 1 of the approved all-five ratings-history contract: verify contemporary Silver inputs for post-W0/W1/W2 cutoffs.
- **Outcome:** Complete. All three cutoffs have clean, 2026-only, validated Silver batches with exact week sets and scored finals matching schedule IDs (8 / 51 / 100 games). Final pin values (version + content SHA + URI + schema) recorded in Amendment 2. Two traps found and resolved: same-`as_of` historical partitions (rejected) and 48 phantom outcomes in one W1 build (rejected).
- **Plan Contract:** `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` (Amendment 2 approved; Task 1 done, pins finalized).
- **Approval / Status:** No R2/Neon writes (reads only). Sealed code/config edits NOT yet made — that is the next implementation step after the planning commit.
- **Blockers:** None for Task 1. Next needs user commit, then sealed-change implementation.
- **Next:** Commit planning state → implement pin table + 3 configs + 3 bundles → per-cutoff repair/measurements/replay chain.

## Context and Decisions
- First attempt picked wrong versions (latest `as_of` ignoring season partitions — landed on 2025/2018/2019 data). Lesson encoded: always filter `partitions.seasons` for 2026.
- Multiple same-`as_of` rebuilds exist with different SHAs. Rule applied: earliest-created validated build, then content-verified (completed sets must equal across candidates or be explicable).
- W2 "anomaly" resolved: 16,479 byplay rows = 100 games cumulative, consistent (~165 plays/game). The larger rows first compared were other seasons' partitions.
- W1 `6b7d011c` outcomes (48 phantom completed rows for game_ids absent from the schedule) and multi-season grains rejected in favor of exact-match `eac8749a`.
- Generation cutoffs set to the batch `as_of` instants (evidence-exact): W0 2026-09-03T04:00Z, W1 2026-09-08T15:35Z, W2 2026-09-13T18:18:22Z. All clear last-kickoff + 6h.

## Verified pin table (all `validated`, 2026-only)
| Cutoff | Games | Outcomes | Byplay | Team games | Completed |
|---|---|---|---|---|---|
| W0 09-03 04:00 | `df578991` | `8c7271c1` | `cf817b49` | `afa0b238` | 8 (w0) |
| W1 09-08 15:35 | `a64e5e6b` | `eac8749a` | `886a189e` | `6b0f9c71` | 51 (w0–w1) |
| W2 09-13 18:18 | `931180a9` | `d822f1fa` | `447e11b7` | `69fd8ca5` | 100 (w0–w2) |
Full SHAs/URIs/schemas in Amendment 2. Expected config populations: 8/51/100 (rows = forecast_eligible; all completed have scores).

## Files Modified
- `docs/plans/2026-09-27/05-weekly-ratings-history-replay.md` — Amendment 2 revised to verified pins/cutoffs/counts
- `docs/plans/index.md` — status line (unchanged this session)
- `session_logs/2026-09-27/18-ratings-history-task1-silver.md` — this record

## Validation
- [x] Read-only: R2 parquet reads + catalog queries via Preview roles; zero writes
- [x] Week sets exact ({0}, {0,1}, {0,1,2}); schedule↔outcome ID equality; scores present; 2026-only seasons
- [x] `git diff --check` (to confirm at commit)
- [ ] User commit of planning state
- [ ] Sealed-change implementation + full chain (Tasks 2–4)

## Amendments and Blockers
None beyond Amendment 2. No new ingestion was needed — contrary to the Amendment 1a fear, contemporary inputs exist.

## Handoff Notes
- **Resume at:** Commit the plan + index + both session logs (17, 18); then implement sealed changes (pin table, 3 configs + SEALED_CONFIGS registration).
- **Watch out for:** `prepare_week_run` in new bundles is carried-not-validated — set an explicit historical marker. Never substitute Silver versions beyond the pinned list without a new amendment. Keep W3/W4 reruns compare-only.

**tags:** ["v5", "ratings", "history", "silver", "verification", "task1"]
