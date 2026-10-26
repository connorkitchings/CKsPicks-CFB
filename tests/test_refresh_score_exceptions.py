"""Score exceptions are added only when the final equals the quarter line scores."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "refresh_score_exceptions", ROOT / "scripts/pipeline/refresh_score_exceptions.py"
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

EARLIER = (1, "Alpha")  # Week 1 game, already excepted


def games(*, week2_home_lines=(7, 7, 7, 7), week2_home_final=28):
    schedule = pd.DataFrame(
        [
            dict(
                game_id=1,
                week=1,
                home_team="Alpha",
                away_team="Beta",
                home_line_scores=[7, 0, 0, 0],
                away_line_scores=[0, 0, 0, 7],
            ),
            dict(
                game_id=2,
                week=2,
                home_team="Gamma",
                away_team="Delta",
                home_line_scores=list(week2_home_lines),
                away_line_scores=[3, 0, 0, 0],
            ),
        ]
    )
    finals = pd.DataFrame(
        [
            dict(season=2026, game_id=1, home_points=7, away_points=7),
            dict(season=2026, game_id=2, home_points=week2_home_final, away_points=3),
        ]
    )
    return schedule, finals


def events(rows):
    return pd.DataFrame(
        [
            dict(game_id=g, team=t, score_increment=s, quality_reason=q)
            for g, t, s, q in rows
        ]
    )


# Week 1 Alpha events 0 vs final 7 (excepted); Week 2 Gamma events 7 vs final 28.
BASE = [
    (1, "Alpha", 0, "impossible_score_increment"),
    (1, "Beta", 7, None),
    (2, "Gamma", 7, "score_regression_rollback"),
    (2, "Delta", 3, None),
]
EXISTING = {EARLIER: "Week 1 old reason"}


def run(rows=BASE, existing=EXISTING, **game_kwargs):
    completed, finals = games(**game_kwargs)
    found = tool.find_mismatches(completed, finals, events(rows))
    return tool.plan_refresh(found, existing, {1: 1, 2: 2}, 2)


def test_verified_mismatch_is_added_and_earlier_entry_kept():
    added, entries = run()

    assert [(a["game_id"], a["team"]) for a in added] == [(2, "Gamma")]
    assert added[0]["line_score_sum"] == 28 == added[0]["final"]
    assert "sum to 7, final is 28" in added[0]["reason"]
    assert "score_regression_rollback" in added[0]["reason"]
    assert entries[EARLIER] == "Week 1 old reason"
    assert set(entries) == {EARLIER, (2, "Gamma")}


def test_line_scores_that_do_not_sum_to_final_stop_naming_the_game():
    with pytest.raises(tool.RefreshError) as error:
        run(week2_home_lines=(7, 7, 7, 0))

    assert "game 2, team Gamma" in error.value.problems[0]


def test_missing_line_scores_stop():
    with pytest.raises(tool.RefreshError):
        run(week2_home_lines=())


def test_earlier_week_exception_that_is_no_longer_needed_stops():
    rows = [(1, "Alpha", 7, None)] + BASE[1:]  # Week 1 now reconciles

    with pytest.raises(tool.RefreshError) as error:
        run(rows)

    assert (
        "earlier-week exception no longer needed: game 1, team Alpha"
        in error.value.problems
    )


def test_new_mismatch_in_earlier_week_stops():
    with pytest.raises(tool.RefreshError) as error:
        run(existing={})

    assert "outside completed week 2: game 1, team Alpha" in error.value.problems[0]


def test_existing_completed_week_entry_keeps_its_reason():
    _, entries = run(existing={**EXISTING, (2, "Gamma"): "kept"})

    assert entries[(2, "Gamma")] == "kept"


def _setup(tmp_path, monkeypatch, **game_kwargs):
    exceptions = tmp_path / "exceptions.json"
    exceptions.write_bytes(tool.render_exceptions(EXISTING))
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    completed, finals = games(**game_kwargs)
    monkeypatch.setattr(
        tool, "load_completed", lambda *a: (completed, finals, events(BASE))
    )
    return exceptions, manifest


def _refresh(exceptions, manifest, dry_run=False):
    return tool.refresh(
        reader=None,
        revision_path=manifest,
        exceptions_path=exceptions,
        completed_week=2,
        dry_run=dry_run,
    )


def test_refresh_writes_nothing_when_unverified(tmp_path, monkeypatch):
    exceptions, manifest = _setup(tmp_path, monkeypatch, week2_home_lines=(1, 1, 1, 1))
    before = exceptions.read_bytes()

    with pytest.raises(tool.RefreshError):
        _refresh(exceptions, manifest)

    assert exceptions.read_bytes() == before and manifest.read_text() == "{}"


def test_refresh_writes_file_and_repins_manifest(tmp_path, monkeypatch):
    exceptions, manifest = _setup(tmp_path, monkeypatch)

    report = _refresh(exceptions, manifest)

    pin = json.loads(manifest.read_text())["score_reconciliation_exceptions"]
    assert pin["sha256"] == hashlib.sha256(exceptions.read_bytes()).hexdigest()
    assert report["exceptions_total"] == 2 and report["exceptions_changed"]


def test_dry_run_reports_but_writes_nothing(tmp_path, monkeypatch):
    exceptions, manifest = _setup(tmp_path, monkeypatch)
    before = exceptions.read_bytes()

    report = _refresh(exceptions, manifest, dry_run=True)

    assert report["added"] and exceptions.read_bytes() == before
    assert manifest.read_text() == "{}"
