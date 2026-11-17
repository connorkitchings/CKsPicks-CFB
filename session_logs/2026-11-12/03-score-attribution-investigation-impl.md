# Session: Score-attribution investigation implementation

## TL;DR

- **Worked On:** Contract 4, the read-only game-by-game investigation of the quarantined games and a specified repair for the running-score defect.
- **Outcome:** Per-game data file, report, analysis module, regeneration script with `--check`, and synthetic-sequence tests. All 56 inventory games were read from the raw plays; Bronze equals Silver in all of them, so every defect is in the provider feed (classes A 41, B 2, C 11, D 2, E 0). Rule R4 (read the score only on scoring plays, capped monotone fit) resolves 82 of the 86 stream-test failures in 2026 (80 match the quarter line scores) against 61 for the prior R1. Applied read-only to 2021 to 2025 it restores 61, 68, 42, 50 and 118 offense team-games with no change to any existing observation; no ratings were recomputed.
- **Plan Contract:** [`docs/plans/2026-11-12/04-score-attribution-investigation.md`](../../docs/plans/2026-11-12/04-score-attribution-investigation.md)
- **Approval / Status:** Owner approved implementation 2026-11-12. Implemented, uncommitted.
- **Blockers:** None. Rating-level movement and a play-text ledger (classes B and D) are not done.
- **Next:** Owner review; decide whether to open contracts for adopting R4 in the next model and for the play-text ledger.

**tags:** ["ratings-lab", "score-attribution", "offseason-2027"]

## Context and Decisions

- Data read (read-only, Preview data lake, checksum verified, credentials from the checkout environment, no values printed): the pinned 2026 revision `revision_manifest_w11_v2` Silver `schedule`, `finals`, `byplay`; the 11 Bronze CFBD plays captures behind the Silver `plays` version; the pinned 2021 to 2025 Silver `byplay` and `fbs_involved_games` from the persisted ratings-lab corpus. Cached under `~/cfb_ratings_lab_v6/output/score-attribution/` (never committed). No provider call, no write to any bucket, database or stored table.
- Inventory is 56 games: the 44 audit-ledger games, 11 exception-only games, and `401858279`, which the current builder quarantines with no exception (the contract's union is 55).
- A first historical pass rewrote every stream with a regression and changed hundreds of already observed rows, because the builder's rollback observes many regressing team-games. It was corrected to rewrite only team-games the stored measurements exclude; the committed results are from the corrected run.
- Rules are never applied to a team the builder accepts, and every rebuilt stream is asserted not to exceed the game final.

## Files Modified

- `src/cks_picks_cfb/ratings_lab/score_attribution.py`, `tests/ratings_lab/test_score_attribution.py`, `scripts/research/run_score_attribution_investigation.py` (new)
- `docs/modeling/score_attribution_investigation_2026.md`, `docs/modeling/evidence/score_attribution_games_2026.json` (generated)
- `mkdocs.yml`, `docs/plans/index.md`, `docs/plans/2026-11-12/04-score-attribution-investigation.md`, `docs/planning/offseason-2027-backlog.md`, `docs/data/known_issues.md` (pointer under item 1)

## Validation

See the final report of the session for the exact results of `pytest`, `ruff check`, `ruff format --check`, `git diff --check`, `mkdocs build --strict --quiet` and the script `--check`.
