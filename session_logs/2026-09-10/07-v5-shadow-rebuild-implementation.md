# Session: v5 Shadow Rebuild Implementation (Terra) — STOPPED on material conflict

## TL;DR
- **Worked On:** Terra implementation of `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (Approved via user go-ahead 2026-09-10).
- **Outcome:** STOPPED during reconciliation (skill §1.5/§3), before any implementation writes. A material contract assumption is false: W1/W2 "core" parents (`6d6f4da2`, `bda6032a`) are NOT absent from R2 — they exist as `point_in_time_team_features` versions — and Task 2's prescribed assembler reassembly cannot reproduce W1/W2 prod bytes (wrong build path + wrong row shape). No R2/DB writes were issued; official record untouched.
- **Plan Contract:** `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (now `In Progress — STOPPED`, awaiting Sol amendment)
- **Approval / Status:** Approved (user go-ahead 2026-09-10) → In Progress → STOPPED on material conflict.
- **Blockers:** Material conflict in Task 1/Task 2 assumptions (details below). Needs a Sol amendment; Terra did not unilaterally redesign.
- **Next:** Sol amends the contract (proposed amendment below), then a fresh Terra task executes the amended plan.

## Context and Decisions
- Followed `.agent/skills/implement-plan/SKILL.md`: authorized the exact Draft path (Approved, approval source recorded), marked In Progress, reconciled repo state vs contract before any code/R2/DB writes.
- Preserved unrelated worktree state: `M docs/ops/production_runbook.md` and `?? .opencode/` untouched. No git add/commit (user-controlled).
- Storage verified: `CFB_STORAGE_BACKEND='r2'` (from `.env`), R2 keys present (values never printed). Preview ops via `zsh scripts/ops/with_preview_env.sh`. Production Neon: read-only SELECTs only. No `./data/` writes (`data/` is gitignored pre-existing working output).
- All R2/DB verification was read-only (`exists`, manifest reads, SELECTs).

## Work Completed (reconciliation + Task 1 verification)

1. **Contract authorized:** Draft → Approved (approval source "user go-ahead 2026-09-10") → In Progress; `docs/plans/index.md` entry updated.
2. **Official record reconciled (matches contract §1):** prod `prediction_runs` 2026 = W0 `2026w0-55de0317120d` scored (+`2026w0-79ec2aebcb00` published), W1 `2026w1-b2c739321e5d` scored, W2 `2026w2-43b25511a100` frozen. Schema check confirms states are only preview/published/frozen/scored (no `superseded` — contract §4 confirmed).
3. **Prod refs recovered (for Tasks 1/4):** scored/frozen runs' `data_as_of` = original publish cutoffs: W0 `2026-08-20T13:19:14Z` (market `e3f984c4`; the published run used `07336aaa`), W1 `2026-09-03T05:00:00Z` (market `b273e83d`), W2 `2026-09-08T17:50:00Z` (market `459c80d0` + quotes `ede4a9a7`). Games `5dabf61a` all weeks. All market/games refs verified present in R2 with matching content SHAs.
4. **Regression-guard baselines (SELECTs only):** prod runs=50, preds=2377, grades=4476, `current_week`=2026w2 frozen; preview runs=19, preds=821, grades=1524, `current_week`=2025w16 replay. Unchanged after session (no writes issued).
5. **Tooling reconciled:** assembler flags confirmed (`--core-ref-uri` etc. are DatasetRef JSON ref-files, `--environment` required; catalog registration resolves to Preview DB under `--environment preview`); `build-features`/`build-baselines` go through `python -m cks_picks_cfb.ops` per Makefile.
6. **Build graph recovered from preview `ops.pipeline_steps`** (W1 prepare `c9b80bf1…`, W2 prepare `3eb4c566…`): `build_gold` = `build_regime_features.py --matchups-ref-uri …/temporal_matchups_ref.json --schedule-ref-uri …/schedule_2021_2026_ref.json --baselines-ref-uri artifacts/preview/refs/history/baselines-selection.json --as-of <pinned cutoff> --environment preview`. All intermediate refs still exist in R2 (W1 temporal `ef3380e0` + schedule `70aef191`; W2 temporal `ace30e9c` + schedule `9432081e`; baselines-selection → `0e6403e2`).

## Material conflict (why Terra stopped)

- **Expected (contract §2 + Task 1):** W1/W2 core parents `6d6f4da2`/`bda6032a` are "absent from R2" (checked under `point_in_time_matchups_core/`); Task 2 assumes the assembler (no preseason) reproduces prod bytes `2f7566f8…`/`64393952…` for all three weeks.
- **Actual:** `6d6f4da2d6d4b329cc322fbd` and `bda6032a9dc8041d500c0924` EXIST in R2 as `point_in_time_team_features` (team-side, LONG format: 8980 rows, `team` column, no baselines; as_of = pinned cutoffs; parents = the exact temporal/schedule versions above). W1/W2 prod matchups were built by `build_regime_features.py` WITH baselines (parents = team_features + baselines, schema `point_in_time_matchups_v3`), NOT by the assembler. Only W0 (`74ffdbbf`, parents = matchups_core `d1c5efd8` + baselines `ec13aef8`, schema v4) matches the assembler path.
- **Why it conflicts:** the assembler expects WIDE core (W0 core: 4491 rows, `home_*`/`away_*`, no `team`). Feeding LONG team_features as `--core-ref-uri` yields 2× rows and a different column set — `content_sha` (sha256 of the parquet record payload, `lake.py:614-615`) cannot match prod; the build would fail closed on `unique_game_keys` validation. Task 2's all-weeks stop rule would then stop the diagnostic for the wrong reason (wrong reassembly path, not untrustworthy lineage). Task 3 likewise has no valid wide `matchups_core` inputs for W1/W2.
- **Lineage itself looks trustworthy:** all corrected refs resolve with matching SHAs; cutoff audit passes (every input `as_of` ≤ first kickoff: W0 08-15/08-17/08-20T13:19 ≤ 08-29; W1 09-03T04:00/05:00 ≤ Thu-evening kickoff; W2 09-08 ≤ 09-11; baselines `0e6403e2` as_of 08-09; preseason `8c47f6d5` strict + eligible, as_of 08-17).

## Proposed amendment (for Sol — smallest change preserving intent)
- **Task 1:** correct the record — W1/W2 parents are `point_in_time_team_features` versions, both present; no core rebuild needed. W0 refs unchanged.
- **Task 2 (amended parity gate):**
  - W0 (unchanged): assembler, no preseason, core `d1c5efd8` + baselines `ec13aef8`, as-of `2026-08-15T14:42:00Z` → expect `1f32fc0f…`.
  - W1/W2 (exact-builder rerun): `build_regime_features.py` with the recorded original argv (only `--output-ref-uri` → shadow path), pinned as-of → expect `2f7566f8…` / `64393952…`.
  - Path-equivalence check enabling Task 3: `build_regime_features.py` WITHOUT `--baselines-ref-uri` (same inputs) → wide `matchups_core`; then assembler without preseason (new core + `0e6403e2`) → expect prod content SHA. Residual risk: feature code changed since build code_shas (`9f432b0`, `c19a4a4`; e.g. commits `52ab2b4`, `9f432b0` touched Gold/pipeline files) — the rerun itself resolves this.
- **Task 3:** W1/W2 v5 assembly uses the path-equivalence cores + `0e6403e2` + preseason `8c47f6d5`; W0 unchanged. All other tasks, stop rules, kill criterion, and no-serving-write constraints unchanged.

## Files Modified
- `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` - Draft → Approved → In Progress → STOPPED status + approval source + implementation log path (bookkeeping only; normative content untouched, no amendment appended)
- `docs/plans/index.md` - entry status tracks the stop (bookkeeping only)
- `session_logs/2026-09-10/07-v5-shadow-rebuild-implementation.md` - this log
- NOT touched: `docs/ops/production_runbook.md`, `.opencode/`, all source/scripts, R2, both databases

## Validation
- [x] Read-only verification of every Task-1 ref (exists + SHA + as_of + parents) recorded above
- [x] `prediction_runs`/`predictions`/`prediction_grades` counts identical before/after (only SELECTs issued); `current_week` untouched
- [x] `git diff --check` (clean — see below)
- [ ] Task 2–5 execution (blocked on Sol amendment)

## Amendments and Blockers
- Material conflict (above); no unilateral amendment per skill §3. Awaiting revised Sol contract.

## Handoff Notes
- **Resume at:** Sol amends the contract per the proposal (or revises otherwise); then a fresh Terra task executes the amended plan from Task 2. Original publish cutoffs for Task 4 are recovered above; original builder argv is recorded above.
- **Watch out for:** `--core-ref-uri` takes DatasetRef JSON ref-files (not manifests); W1/W2 v5 assembly needs wide cores that do not yet exist (path-equivalence step); never invoke publish/freeze/score-to-db; keep `M docs/ops/production_runbook.md` and `.opencode/` untouched; no git operations.

**tags:** ["v5-shadow", "diagnostic", "2026-season", "terra", "stopped", "material-conflict"]
