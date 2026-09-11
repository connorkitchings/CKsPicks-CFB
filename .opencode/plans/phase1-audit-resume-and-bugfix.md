# Phase 1 Evidence Audit — Resume Plan and Schedule-Concat Defect Fix

**Status:** Decision-complete, awaiting implementation session
**Created:** 2026-09-05 (session: Phase 1 resume)
**Governing contract:** `docs/plans/2026-09-05/01-data-and-evidence-audit.md` (In Progress, Amendment 1)

## 1. State at handoff

Completed this session (all under approved plan):

- `ruff format` applied to the three Phase 1 files; `ruff check`, focused tests
  (15/15), full suite (**688 passed, 2 skipped**), and `git diff --check` all green.
- Tooling committed by the user as `3ae875e`
  (`feat(research): add phase 1 data-first evidence audit tooling`).
- `resolve` stage executed against Preview:
  run `2026-09-05T1445Z-phase1-evidence-audit-v1`, state
  `resolved_with_blockers`, **21/21 roots resolved, 56 datasets, 4,825 source
  captures, 52 blockers — all `catalog registration missing` parent
  version_ids** discovered during lineage traversal. Sealed at
  `artifacts/research/data-first-football-v1/phase1/2026-09-05T1445Z-phase1-evidence-audit-v1/resolved-evidence-manifest.json`.
- `audit` stage attempted and **failed with a TypeError** before writing any
  artifact (traceback below). The v1 run directory contains only the resolved
  manifest; leave it in place as a superseded attempt.

## 2. Defect

`scripts/research/audit_data_first_evidence.py`, in `audit_evidence()`:

```
raw_games = pd.concat(games_parts, ignore_index=True)            # line ~762
raw_games = raw_games.rename(columns={"year": "season", "id": "game_id"})
raw_games["season"] = pd.to_numeric(raw_games["season"], errors="coerce")
```

CFBD games captures already carry canonical columns (`season` **and** `year`;
some payloads `game_id` **and** `id`). The blanket rename therefore produces
**duplicate `season` columns**, so `raw_games["season"]` returns a DataFrame
and `pd.to_numeric` raises
`TypeError: arg must be a list, tuple, 1-d array, or Series`.
The same collision risk exists for teams captures (`year`/`season`,
`school`/`team`) inside `_team_classification_lookup`.

A secondary `FutureWarning` (empty/all-NA concat entries) comes from
zero-row captures entering `games_parts`.

## 3. Exact patch

### 3.1 `scripts/research/audit_data_first_evidence.py`

**A.** Directly above the `for raw_capture in resolved["source_captures"]:` loop
(currently preceded by `games_parts: list[pd.DataFrame] = []` /
`teams_parts: list[pd.DataFrame] = []` / `capture_inventory: ...` around
line 702–704), insert:

```python
    def _canonical_columns(part: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
        rename: dict[str, str] = {}
        drop: list[str] = []
        for alias, canonical in aliases.items():
            has_alias = alias in part.columns
            has_canonical = canonical in part.columns
            if has_alias and not has_canonical:
                rename[alias] = canonical
            elif has_alias and has_canonical:
                drop.append(alias)
        return part.rename(columns=rename).drop(columns=drop)

    games_aliases = {"year": "season", "id": "game_id"}
    teams_aliases = {"year": "season", "school": "team"}
```

**B.** In the capture loop, replace the games/teams collection block:

```python
        if "games" in entity and "game_stats" not in entity:
            part = frame.copy()
            part["__captured_at"] = capture.captured_at
            games_parts.append(part)
        elif "teams" in entity:
            teams_parts.append(frame)
```

with:

```python
        if "games" in entity and "game_stats" not in entity:
            if not frame.empty:
                part = _canonical_columns(frame.copy(), games_aliases)
                part["__captured_at"] = capture.captured_at
                games_parts.append(part)
        elif "teams" in entity:
            if not frame.empty:
                teams_parts.append(_canonical_columns(frame, teams_aliases))
```

**C.** Replace the schedule assembly lines:

```python
        raw_games = pd.concat(games_parts, ignore_index=True)
        raw_games = raw_games.rename(columns={"year": "season", "id": "game_id"})
        raw_games["season"] = pd.to_numeric(raw_games["season"], errors="coerce")
```

with:

```python
        raw_games = pd.concat(games_parts, ignore_index=True)
        raw_games["season"] = pd.to_numeric(raw_games["season"], errors="coerce")
```

(`classify_schedule` keeps its own `_GAME_ALIASES` rename — it is a no-op for
already-canonical columns and still normalizes any remaining CFBD camelCase
fields such as `seasonType`/`start_date`.)

### 3.2 `tests/test_data_first_evidence_audit.py` — regression test

Append:

```python
def test_schedule_builder_survives_duplicate_alias_columns_and_empty_captures():
    from scripts.research.audit_data_first_evidence import _build_schedule_parts

    parts, teams = _build_schedule_parts(
        [
            {
                "entity": "games",
                "frame": pd.DataFrame(
                    [
                        {
                            "season": 2025,
                            "year": 2025,
                            "id": 7,
                            "game_id": 7,
                            "home_team": "Alpha",
                            "away_team": "Beta",
                            "home_classification": "fbs",
                            "away_classification": "fbs",
                            "completed": True,
                            "home_points": 10,
                            "away_points": 3,
                            "start_date": "2025-08-30T16:00:00Z",
                            "season_type": "regular",
                        }
                    ]
                ),
                "captured_at": pd.Timestamp("2025-08-01T00:00:00Z"),
            },
            {"entity": "games", "frame": pd.DataFrame(), "captured_at": pd.Timestamp("2025-08-02T00:00:00Z")},
            {
                "entity": "teams",
                "frame": pd.DataFrame([{"season": 2025, "year": 2025, "school": "Alpha", "team": "Alpha", "classification": "fbs"}]),
                "captured_at": pd.Timestamp("2025-08-01T00:00:00Z"),
            },
            {"entity": "plays", "frame": pd.DataFrame([{"game_id": [7]}]), "captured_at": pd.Timestamp("2025-08-01T00:00:00Z")},
        ]
    )
    raw_games = pd.concat(parts, ignore_index=True)
    assert isinstance(raw_games["season"], pd.Series)
    schedule, conflicts = classify_schedule(raw_games, pd.concat(teams, ignore_index=True))
    assert set(schedule["game_id"]) == {7}
    assert conflicts == []
```

This test requires **refactoring** the capture-collection loop into a
pure helper `_build_schedule_parts(captures) -> tuple[list[pd.DataFrame], list[pd.DataFrame]]`
inside `audit_data_first_evidence.py` (same normalization logic as §3.1 B,
but testable without R2/Neon). The `audit_evidence` loop then calls the
helper with `(capture.entity, frame, capture.captured_at)` tuples. Keep the
loop's issue-raising behavior (unreadable-source-capture) in `audit_evidence`;
the helper only receives successfully read frames. If the implementer prefers
the minimal §3.1 inline patch without the helper, then instead add a direct
unit test for `_canonical_columns` covering: alias-only rename, canonical-only
no-op, both-present drop, and empty frame pass-through, plus an integration
assertion that a duplicated-alias games frame passes through
`classify_schedule` after normalization.

## 4. Validation

1. `uv run ruff format` + `uv run ruff check` on both changed files.
2. `uv run pytest tests/test_data_first_evidence_audit.py -q` (16/16 with new test).
3. `uv run pytest -q` full suite (expect 689 passed, 2 skipped).
4. `git diff --check`.

## 5. Commit (user executes)

```
fix(research): normalize duplicate alias columns in phase1 schedule concat

- Prefer canonical season/game_id/team columns per capture before concat
- Skip empty captures to avoid all-NA concat coercion
- Add regression test for duplicate-alias captures
```

## 6. Re-execution runbook

The v1 resolved manifest is sealed against `3ae875e`; the audit stage
verifies `code_sha` equality, so after committing the fix, start a **new
run-id** under the new HEAD (do not reuse v1 — the sealed manifest bytes
would collide):

```bash
HEAD_SHA=$(git rev-parse HEAD)
RUN_ID=2026-09-05T<HHMM>Z-phase1-evidence-audit-v2

PYTHONPATH=.:src uv run python scripts/research/audit_data_first_evidence.py resolve \
  --environment preview \
  --run-id "$RUN_ID" \
  --as-of <UTC-now, e.g. 2026-09-05T16:30:00Z> \
  --expected-code-sha "$HEAD_SHA"

PYTHONPATH=.:src uv run python scripts/research/audit_data_first_evidence.py audit \
  --environment preview \
  --run-id "$RUN_ID" \
  --as-of <same timestamp> \
  --expected-code-sha "$HEAD_SHA" \
  --resolved-manifest-uri "artifacts/research/data-first-football-v1/phase1/$RUN_ID/resolved-evidence-manifest.json"
```

Expected outcome: state `complete_with_blockers` with the 9 artifacts
(dataset-inventory, lineage-edges, game-stage-coverage, exclusions,
issue-register, result-dispositions, hypothesis-error-map, source-comparison,
summary). Expected blocker families (by design): catalog-missing lineage
parents (52), postseason-capture-gap, silver FBS-FCS exclusions, reconstructed
timing evidence.

## 7. Phase 1 closure (after successful audit)

1. Review `summary.json` + `issue-register.json`; verify every blocker maps to
   a Phase 2 repair action.
2. Write `session_logs/2026-09-05/03-phase1-data-evidence-audit.md`
   (implementation log already referenced by the plan).
3. Update `docs/plans/2026-09-05/01-data-and-evidence-audit.md` status:
   `In Progress` → `Implemented` (or leave open if the user wants Phase 2
   scoping first).
4. Propose final commit for docs/log updates.

## 8. Constraints

- Preview-only; every stage read-only against Neon/R2 except the namespaced
  `artifacts/research/data-first-football-v1/phase1/<run-id>/` prefix.
- No production activation, no model refit, no subscription purchase.
- Preserve the superseded v1 run directory; immutable artifacts are never
  deleted or overwritten.
