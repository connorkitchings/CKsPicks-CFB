"""Grades-only backfill planning: stored side, real policy label, read-back, snapshots."""

from datetime import datetime, timezone

import pytest

from scripts.pipeline import backfill_v5_unconstrained_grades as bf


def _row(
    *,
    game_id=1,
    evidence="pending",
    home_line=-3.5,
    total_line=50.5,
    pred_spread=6.0,  # recomputed side would be home (6 - 3.5 > 0)
    pred_total=45.0,  # recomputed side would be under
    spread_lean="away",  # the stored side contradicts the recomputation
    total_lean="over",
    home_pts=20,
    away_pts=24,
    spread_grade=None,
    total_grade=None,
    pms_spread_side="away",
    pms_spread_point=-3.5,
    pms_total_side="over",
    pms_total_point=50.5,
    spread_policy="model_side_best_quote_v2",
    total_policy="model_side_best_quote_v2",
    spread_quote="q-s",
    total_quote="q-t",
):
    return (
        6, "run-6", game_id, "Home", "Away", home_line, total_line, pred_spread,
        pred_total, spread_lean, total_lean, "snap", home_pts, away_pts, spread_grade,
        total_grade, pms_spread_side, pms_spread_point, spread_quote, -110.0,
        pms_total_side, pms_total_point, total_quote, -110.0, evidence, spread_policy,
        total_policy,
    )  # fmt: skip


def test_grades_only_grades_the_stored_side_not_a_recomputed_one():
    plan = bf.plan_backfill([_row()], grades_only=True)
    by_target = {g["target"]: g for g in plan.grades}
    assert (
        by_target["spread"]["side"] == "away" and by_target["total"]["side"] == "over"
    )
    # away +3.5 with a 4-point loss margin: home lost 20-24 => away covers => win
    assert by_target["spread"]["result"] == "win"
    # 44 total points < 50.5 => the stored over loses
    assert by_target["total"]["result"] == "loss"
    assert plan.prediction_updates == [] and plan.pms_updates == []


def test_quote_backed_grades_carry_the_selections_policy_version():
    plan = bf.plan_backfill([_row()], grades_only=True)
    assert {g["grading_version"] for g in plan.grades} == {"model_side_best_quote_v2"}
    unquoted = bf.plan_backfill(
        [
            _row(
                spread_quote=None,
                total_quote=None,
                spread_policy=None,
                total_policy=None,
            )
        ],
        grades_only=True,
    )
    assert {g["grading_version"] for g in unquoted.grades} == {"frozen_line_v2"}
    assert bf.grading_version("q", None) == "model_side_best_quote_v1"


def test_existing_grades_are_never_planned_again():
    plan = bf.plan_backfill(
        [_row(spread_grade="win", total_grade="loss")], grades_only=True
    )
    assert plan.grades == []
    assert plan.tallies["spread"]["win"] == 1 and plan.tallies["total"]["loss"] == 1


def test_grades_only_never_invents_a_side():
    row = _row(
        spread_lean=None, total_lean=None, pms_spread_side=None, pms_total_side=None
    )
    plan = bf.plan_backfill([row], grades_only=True)
    assert plan.grades == []
    assert sorted(t for _g, t, _r in plan.unresolved) == ["spread", "total"]
    # Outside grades-only mode the side may be recomputed (the original behaviour).
    full = bf.plan_backfill([row], grades_only=False)
    assert {g["target"] for g in full.grades} == {"spread", "total"}


def test_replay_rewrite_mode_recomputes_and_plans_lean_updates():
    plan = bf.plan_backfill([_row(evidence="replay")], grades_only=False)
    by_target = {g["target"]: g for g in plan.grades}
    assert (
        by_target["spread"]["side"] == "home" and by_target["total"]["side"] == "under"
    )
    assert {tuple(sorted(u)) for u in plan.prediction_updates} == {
        ("game_id", "run_id", "spread_lean"),
        ("game_id", "run_id", "total_lean"),
    }
    assert {u["target"] for u in plan.pms_updates} == {"spread", "total"}
    # A non-replay run is never rewritten even outside grades-only mode.
    pending = bf.plan_backfill([_row(evidence="pending")], grades_only=False)
    assert pending.prediction_updates == [] and pending.pms_updates == []
    assert {g["side"] for g in pending.grades} == {"away", "over"}


def test_games_without_a_final_or_a_line_are_skipped():
    no_final = bf.plan_backfill([_row(home_pts=None, away_pts=None)], grades_only=True)
    assert no_final.grades == [] and no_final.unresolved == []
    no_line = bf.plan_backfill(
        [
            _row(
                pms_spread_point=None,
                home_line=None,
                pms_total_point=None,
                total_line=None,
            )
        ],
        grades_only=True,
    )
    assert no_line.grades == []


def _stored(record, **overrides):
    row = {
        "run_id": record["run_id"],
        "game_id": record["game_id"],
        "target": record["target"],
        "side": record["side"],
        "result": record["result"],
        "grading_version": record["grading_version"],
        "home_points": 20,
        "away_points": 24,
        "point": -3.5 if record["target"] == "spread" else 50.5,
        "selection_side": record["side"],
        "line": None,
    }
    row.update(overrides)
    return row


def test_readback_accepts_the_persisted_grades_and_flags_every_kind_of_drift():
    plan = bf.plan_backfill([_row()], grades_only=True)
    stored = [_stored(g) for g in plan.grades]
    assert bf.readback_mismatches(plan.grades, stored) == []

    wrong_result = [
        dict(r, result="loss") if r["target"] == "spread" else r for r in stored
    ]
    assert any(
        "inputs give" in p for p in bf.readback_mismatches(plan.grades, wrong_result)
    )

    other_side = [
        dict(r, selection_side="home") if r["target"] == "spread" else r for r in stored
    ]
    assert any(
        "selection side" in p for p in bf.readback_mismatches(plan.grades, other_side)
    )

    changed_label = [dict(r, grading_version="x") for r in stored]
    assert any(
        "differs from the planned" in p
        for p in bf.readback_mismatches(plan.grades, changed_label)
    )

    assert any(
        "not found" in p for p in bf.readback_mismatches(plan.grades, stored[:1])
    )

    moved_final = [dict(r, home_points=30) for r in stored]
    assert bf.readback_mismatches(plan.grades, moved_final)


def test_snapshot_files_are_unique_and_never_overwrite(tmp_path):
    now = datetime(2026, 10, 11, 4, 30, 5, tzinfo=timezone.utc)
    path = bf.snapshot_path(tmp_path, "preview", "week6", now)
    assert path.name == "preview_pre_grades_week6_20261011T043005Z.json"
    assert bf.snapshot_path(tmp_path, "production", "week6", now) != path
    path.write_text("{}")
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        bf.snapshot_path(tmp_path, "preview", "week6", now)
