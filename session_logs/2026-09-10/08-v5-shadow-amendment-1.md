# Session: v5 Shadow Contract Amendment 1 (Sol)

## TL;DR
- **Worked On:** Revised the stopped v5 shadow contract per Terra's material-conflict report.
- **Outcome:** Amendment 1 incorporated into `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` — corrected two-path build lineage, exact-builder parity gate, baked-in refs/cutoffs/argv. Status back to Draft, pending user re-approval for a fresh Terra run.
- **Plan Contract:** `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (Draft + Amendment 1)
- **Approval / Status:** Pending re-approval. Terra must not resume without it.
- **Blockers:** None for planning. Implementation blocked until re-approval.
- **Next:** User re-approves (or amends); then a fresh Terra task executes from Task 1 verification through Task 5.

## Context and Decisions
- Terra's stop was correct per implement-plan §3: my §2 "absent from R2" claim was wrong (I had listed the wrong dataset), and the prescribed assembler path could not reproduce W1/W2 bytes. No writes were issued; official record untouched — the workflow worked as designed.
- Sol spot-verified every load-bearing claim before amending: 8 `point_in_time_team_features` versions in R2 (incl. `6d6f4da2`/`bda6032a`, as_of = pinned cutoffs), `build_regime_features.py:107-172` two-stage build (LONG team_features → wide, baselines-conditional dataset/schema), W1 manifest parents matching Terra's report.
- Amendment preserves goal, scope, gates, stop rules, kill criterion, and no-serving-write constraints; only the reassembly mechanics changed. Still requires re-approval because the authorized mechanics changed.
- Preserved `M docs/ops/production_runbook.md` and `?? .opencode/` untouched.

## Work Completed
- Verified Terra's evidence (R2 team_features census, builder source lines, manifest parents).
- Rewrote contract §2 table (two build paths, all parents present), Task 1 (ref recovery, no rebuild), Task 2 (exact-builder parity + path-equivalence), Task 3 (W1/W2 v5 via equivalence cores), Task 4 (pinned publish cutoffs), Risks, and Amendments (Amendment 1 with reason/original/revised/impact).
- Updated `docs/plans/index.md` entry; this log.

## Files Modified
- `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` - Amendment 1, status Draft pending re-approval
- `docs/plans/index.md` - entry tracks amendment
- `session_logs/2026-09-10/08-v5-shadow-amendment-1.md` - this log

## Validation
- [x] Spot-verification queries + source reads recorded above
- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`
- [ ] User re-approval of the amended contract (pending)

## Amendments and Blockers
- Amendment 1 to the v5 shadow contract (see contract). No other blockers.

## Handoff Notes
- **Resume at:** User reviews Amendment 1; on re-approval, launch a fresh Terra task with the same copy-ready prompt against the amended path, executing from Task 1 verification through Task 5.
- **Watch out for:** Fresh task (do not resume Terra's stopped session); the stopped log `07-…` is evidence only.

**tags:** ["planning", "v5-shadow", "amendment", "sol"]
