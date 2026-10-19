"""Team-game yardage (``charts_v2``): formulas, prepare recomputation, staging binding.

Formula expectations are hand-computed from small play fixtures, never by the
builder. Prepare recomputes the table from the pinned plays; staging only checks
structure and binds the prepare evidence, with no storage reads.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.charts.reconciliation import yardage_problems
from cks_picks_cfb.charts.team_game_stats import build_team_game_stats
from cks_picks_cfb.charts.team_game_yardage import (
    YARDAGE_COLUMNS,
    TeamGameYardageError,
    build_team_game_yardage,
)
from cks_picks_cfb.season import inputs as season_inputs
from cks_picks_cfb.season import projection_charts
from cks_picks_cfb.season import release as r
from cks_picks_cfb.season import verification as v
from cks_picks_cfb.season.manifest import canonical
from tests.season_candidates import candidate
from tests.season_fixtures import build_season
from tests.test_season_release import Database, stage
from tests.test_season_verification import MANIFEST, synthetic_payload

# --------------------------------------------------------------- formulas


def _play(game_id, offense, defense, yards, success, **flags):
    return {
        "season": 2026,
        "game_id": game_id,
        "offense": offense,
        "defense": defense,
        "yards_gained": yards,
        "success": success,
        "ppa": 0.1,
        "quarter": 1,
        "st": 0,
        "penalty": 0,
        "twopoint": 0,
        "garbage": 0,
        "play_type": "Rush",
        **flags,
    }


PLAYS = [
    # Game 10 (week 1), A offense: the 20-yard boundary, missing and non-finite
    # yardage, a missing success, a successful loss and excluded plays.
    _play(10, "A", "B", 19, 1),
    _play(10, "A", "B", 20, 0),
    _play(10, "A", "B", 21, 1),
    _play(10, "A", "B", None, 1),
    _play(10, "A", "B", np.inf, 1),
    _play(10, "A", "B", -3, 1),
    _play(10, "A", "B", 25, None),
    _play(10, "A", "B", 50, 1, garbage=1),
    _play(10, "A", "B", 40, 1, st=1, play_type="Punt"),
    _play(10, "A", "B", 30, 1, play_type="Punt Return"),
    # Game 10, B offense: no successes and no explosive plays.
    _play(10, "B", "A", 5, 0),
    _play(10, "B", "A", 12, 0),
    # Game 20 (week 2): only C has offensive plays (unequal exposures).
    _play(20, "C", "A", 20, 1),
    _play(20, "C", "A", 3, 1),
    # Game 30 (week 3): not completed before active week 3.
    _play(30, "A", "C", 80, 1),
]
#: (game, team) -> offense (yards_n, explosive_n, success_yards_n, success_yards_sum)
EXPECTED_OFFENSE = {
    (10, "A"): (5, 3, 3, 37.0),  # 19, 20, 21, -3, 25 | 20, 21, 25 | 19 + 21 - 3
    (10, "B"): (2, 0, 0, 0.0),
    (20, "A"): (0, 0, 0, 0.0),
    (20, "C"): (2, 1, 2, 23.0),
}
OPPONENT = {(10, "A"): "B", (10, "B"): "A", (20, "A"): "C", (20, "C"): "A"}


def _team_games(plays: pd.DataFrame) -> pd.DataFrame:
    games = pd.DataFrame(
        {
            "season": 2026,
            "week": [1, 2, 3],
            "game_id": [10, 20, 30],
            "home_team": ["A", "A", "A"],
            "away_team": ["B", "C", "C"],
        }
    )
    finals = pd.DataFrame(
        {
            "season": 2026,
            "game_id": [10, 20, 30],
            "home_points": [21, 7, 14],
            "away_points": [14, 10, 3],
        }
    )
    return build_team_game_stats(
        byplay=plays,
        games=games,
        finals=finals,
        fbs_teams={"A", "B", "C"},
        neutral_game_ids=(),
        season=2026,
        active_week=3,
    )


@pytest.fixture
def built():
    plays = pd.DataFrame(PLAYS)
    team_games = _team_games(plays)
    return team_games, build_team_game_yardage(byplay=plays, team_games=team_games)


def test_yardage_counts_equal_hand_computed_values(built):
    _, yardage = built
    fields = ("yards_n", "explosive_n", "success_yards_n", "success_yards_sum")
    rows = {(row.game_id, row.team): row for row in yardage.itertuples()}
    assert set(rows) == set(EXPECTED_OFFENSE)
    for key, offense in EXPECTED_OFFENSE.items():
        row = rows[key]
        defense = EXPECTED_OFFENSE[(key[0], OPPONENT[key])]
        assert tuple(getattr(row, f"off_{f}") for f in fields) == offense
        assert tuple(getattr(row, f"def_{f}") for f in fields) == defense


def test_key_set_equals_team_game_stats_and_later_weeks_are_excluded(built):
    team_games, yardage = built
    assert tuple(yardage.columns) == YARDAGE_COLUMNS
    keys = ["season", "game_id", "team"]
    assert yardage[keys].values.tolist() == team_games[keys].values.tolist()
    assert 30 not in set(yardage.game_id)


def test_yardage_matches_the_research_comparison_definitions(built):
    from cks_picks_cfb.data.play_filters import scrimmage_play_mask
    from scripts.research.compare_chart_explosiveness import measures

    _, yardage = built
    plays = pd.DataFrame(PLAYS)
    plays = plays[scrimmage_play_mask(plays) & plays.game_id.isin([10, 20])]
    for row in yardage.itertuples():
        group = plays[plays.game_id.eq(row.game_id) & plays.offense.eq(row.team)]
        research = measures(group)
        assert row.off_yards_n == research["yardage_n"]
        assert row.off_explosive_n == research["explosive_n"]
        assert row.off_success_yards_n == research["successful_yards_n"]
        assert row.off_success_yards_sum == research["successful_yards_sum"]


def test_no_completed_games_gives_an_empty_table_and_missing_yardage_is_refused():
    plays = pd.DataFrame(PLAYS)
    empty = build_team_game_yardage(byplay=plays, team_games=_team_games(plays)[:0])
    assert empty.empty and tuple(empty.columns) == YARDAGE_COLUMNS
    with pytest.raises(TeamGameYardageError, match="yards_gained"):
        build_team_game_yardage(
            byplay=plays.drop(columns="yards_gained"), team_games=_team_games(plays)
        )


# ------------------------------------------------- staging structural checks


def _yardage_row(payload, game_id, team):
    return next(
        row
        for row in payload["team_game_yardage"]
        if (row["game_id"], row["team"]) == (game_id, team)
    )


def _failed_projection_checks(payload) -> set[str]:
    checks = v.derive_checks(payload, MANIFEST)
    return {name for name, entry in checks.items() if not entry["passed"]}


def _broken_mirror(payload):
    _yardage_row(payload, 1, "A")["off_yards_n"] -= 1


def _missing_key(payload):
    payload["team_game_yardage"].remove(_yardage_row(payload, 1, "A"))


def _extra_key(payload):
    extra = {**_yardage_row(payload, 3, "C"), "game_id": 4}
    payload["team_game_yardage"].append(extra)


def _explosive_over_yards(payload):
    # Mirrored, so only the bound fails: A's offense in game 1 has 6 yardage plays.
    _yardage_row(payload, 1, "A")["off_explosive_n"] = 7
    _yardage_row(payload, 1, "B")["def_explosive_n"] = 7


def _success_yards_over_successes(payload):
    # B's offense in game 1 has 5 successes and 5 yardage plays.
    _yardage_row(payload, 1, "B")["off_success_yards_n"] = 6
    _yardage_row(payload, 1, "A")["def_success_yards_n"] = 6


STRUCTURAL_NEGATIVES = {
    "broken_mirror": _broken_mirror,
    "missing_key": _missing_key,
    "extra_key": _extra_key,
    "explosive_over_yards": _explosive_over_yards,
    "success_yards_over_successes": _success_yards_over_successes,
}


@pytest.mark.parametrize("fault", sorted(STRUCTURAL_NEGATIVES))
def test_structural_fault_fails_reconciliation_and_is_refused_at_staging(fault):
    payload = synthetic_payload()
    STRUCTURAL_NEGATIVES[fault](payload)
    assert _failed_projection_checks(payload) == {"team_chart_reconciliation"}
    with pytest.raises(ValueError):
        stage(Database(), sealed=candidate(edit_payload=STRUCTURAL_NEGATIVES[fault]))


def test_negative_success_yards_sum_is_accepted():
    def loss_on_success(payload):
        _yardage_row(payload, 2, "C")["off_success_yards_sum"] = -4.0
        _yardage_row(payload, 2, "D")["def_success_yards_sum"] = -4.0

    payload = synthetic_payload()
    loss_on_success(payload)
    assert _failed_projection_checks(payload) == set()
    db = Database()
    release_id = stage(db, sealed=candidate(edit_payload=loss_on_success))
    rows = db.projections[(release_id, "team_game_yardage")]
    assert {row["off_success_yards_sum"] for row in rows} >= {-4.0}


def test_charts_v1_payload_has_no_yardage_branch():
    payload = synthetic_payload()
    del payload["team_game_yardage"], payload["team_resume"]
    checks = v.derive_checks(payload, MANIFEST)
    assert all(entry["passed"] for entry in checks.values())
    assert "yardage_rows" not in checks["team_chart_reconciliation"]["observed"]


# ------------------------------------------- prepare recomputation (real plays)


@pytest.fixture(scope="module")
def season(tmp_path_factory):
    return build_season(tmp_path_factory.mktemp("season"))


@pytest.fixture(scope="module")
def charts(season):
    return projection_charts.build_charts(**season)


def _recompute(season, rows) -> dict:
    return v._run(
        v._chart_yardage_recomputed,
        "prepare",
        season["inputs"],
        season["revision"],
        {"team_game_yardage": rows},
        int(season["identity"]["active_week"]),
    )


def test_prepare_recomputation_passes_and_records_bound_evidence(season, charts):
    rows = charts["team_game_yardage"]
    entry = _recompute(season, rows)
    byplay = season["revision"]["inputs"]["byplay"]
    assert entry["passed"] is True
    assert entry["observed"] == {
        "byplay_uri": byplay["uri"],
        "byplay_sha256": byplay["sha256"],
        "projection_sha256": r.projection_check(rows)["sha256"],
        "rows": len(rows),
        "violations": 0,
        "examples": [],
    }


@pytest.mark.parametrize("field", ["explosive_n", "success_yards_n"])
def test_mirrored_wrong_count_passes_structure_but_fails_recomputation(
    season, charts, field
):
    """Both mirrored rows carry the same incorrect count within every bound."""
    rows = copy.deepcopy(charts["team_game_yardage"])
    stats = charts["team_game_stats"]
    stat = {(s["game_id"], s["team"]): s for s in stats}
    bound = {"explosive_n": "yards_n", "success_yards_n": None}[field]

    def room(row):
        limit = (
            row[f"off_{bound}"]
            if bound
            else min(
                row["off_yards_n"], stat[(row["game_id"], row["team"])]["off_success_n"]
            )
        )
        return row[f"off_{field}"] < limit

    target = next(row for row in rows if room(row))
    opponent = stat[(target["game_id"], target["team"])]["opponent"]
    mirror = next(
        row
        for row in rows
        if (row["game_id"], row["team"]) == (target["game_id"], opponent)
    )
    target[f"off_{field}"] += 1
    mirror[f"def_{field}"] += 1

    assert yardage_problems(rows, stats) == []
    entry = _recompute(season, rows)
    assert entry["passed"] is False
    assert any(field in example for example in entry["observed"]["examples"])


def test_prepare_recomputation_rejects_a_missing_row(season, charts):
    rows = charts["team_game_yardage"][1:]
    entry = _recompute(season, rows)
    assert entry["passed"] is False
    assert any("missing" in example for example in entry["observed"]["examples"])


# ------------------------------------------------------- staging binding


def _set_evidence(**values):
    def edit(report):
        report["checks"]["chart_yardage_recomputed"]["observed"].update(values)

    return edit


def _drop_prepare_entry(report):
    del report["checks"]["chart_yardage_recomputed"]


def _fail_prepare_entry(report):
    report["checks"]["chart_yardage_recomputed"]["passed"] = False


BINDING_NEGATIVES = {
    "missing_entry": (_drop_prepare_entry, "checks missing"),
    "failed_entry": (_fail_prepare_entry, "check failed"),
    "projection_sha": (_set_evidence(projection_sha256="0" * 64), "another payload"),
    "projection_rows": (_set_evidence(rows=1), "another payload"),
    "byplay_sha": (_set_evidence(byplay_sha256="0" * 64), "byplay"),
    "byplay_uri": (_set_evidence(byplay_uri="lake/silver/other.parquet"), "byplay"),
}


@pytest.mark.parametrize("fault", sorted(BINDING_NEGATIVES))
def test_staging_refuses_unbound_yardage_evidence(fault):
    edit, message = BINDING_NEGATIVES[fault]
    db = Database()
    with pytest.raises(r.SeasonReleaseError, match=message):
        stage(db, sealed=candidate(edit_report=edit))
    assert not db.rows and not db.projections


def test_staging_refuses_revision_bytes_other_than_the_run_pins():
    sealed = candidate()
    revision = json.loads(sealed["revision_raw"])
    revision["inputs"]["byplay"]["sha256"] = "0" * 64
    db = Database()
    with pytest.raises(r.SeasonReleaseError, match="revision manifest bytes"):
        stage(db, sealed={**sealed, "revision_raw": canonical(revision)})
    assert not db.rows


def test_staging_performs_no_storage_reads(monkeypatch):
    from cks_picks_cfb.data import storage

    def forbidden(*args, **kwargs):
        raise AssertionError("staging must not read storage")

    monkeypatch.setattr(storage, "get_storage", forbidden)
    for name in ("read_ref", "frame", "load_inputs"):
        monkeypatch.setattr(season_inputs, name, forbidden)
    monkeypatch.setattr(projection_charts, "build_yardage_rows", forbidden)
    monkeypatch.setattr(projection_charts, "build_charts", forbidden)

    db = Database()
    release_id = stage(db)
    assert db.projections[(release_id, "team_game_yardage")]
