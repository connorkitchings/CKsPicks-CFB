"""Golden regression: v1 behaviour and v1 schema identities must never move.

Contract 2026-10-09/01 (Task 3.0, Task 4): provider-keyed play identity is added *beside* v1.
The digests below were recorded from the code at the Task 2 commit, before any ordering or
v2 change. A digest that changes means a v1 output changed; do not re-record it to make a
test pass without a decision that v1 evidence may differ.

The slate covers regulation scoring with extra points, a field goal, a score-regression
rollback, an interception, punts, an overtime field goal and a play with a missing period.
The producer and the independent verifier must agree on every frame.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.features.aggregations.drives import aggregate_drives
from cks_picks_cfb.features.aggregations.team_game import calculate_st_analytics_agg
from cks_picks_cfb.metrics import ledger as ml
from cks_picks_cfb.quality.silver import score_stream_regressions
from cks_picks_cfb.ratings import possession_measurements as pm
from cks_picks_cfb.ratings.possession_verification import reconstruct_measurements

SCHEMA_SHAS = {
    (
        "possession_ledger",
        "data_first_possession_possession_v1",
    ): "35caa81dc41152067747281074858b31c3e7c80be0c7f7e1032936e8176425ea",
    (
        "possession_scoring_event",
        "data_first_possession_scoring_event_v1",
    ): "2ebbcf8818cfad91fbdf9f683eb63c6f3267879dedfc5e1510cf07e4a6fe0e5d",
    (
        "possession_observation",
        "data_first_possession_observation_v1",
    ): "65737f647437881a993cb4ab9a4d026f2344ff9dde3294b6044973ac5932d877",
    (
        "football_possessions",
        "football_possessions_v1",
    ): "e6718225417a74b8d0062d8bdb2ef1714dc1dca220c89d27558d00dad0ddcb98",
    (
        "football_scoring_ledger",
        "football_scoring_ledger_v1",
    ): "1103d04fbdf771b3c06a59a29f453ed70c60b4f8d99cf0f08859c8f4c6b4f3e0",
    (
        "scoring_attribution_evidence",
        "scoring_attribution_evidence_v1",
    ): "00a2444286647302e22385f00e5f313ceee4b067ce545edf1db44ca559e66512",
    (
        "byplay",
        "byplay_v1",
    ): "daf7cbd977cb666606afaf28e7757125f954685fb0f550bb3a55020ff9772ae8",
    (
        "drives",
        "drives_v1",
    ): "a1400b6ad766272bb4b2644af3408f769753de2025d52e002bc8d1cc7e811473",
}
GOLDEN = {
    "possessions": "996a4abff43da253",
    "scoring_events": "c2015878a76e88bc",
    "observations": "42e64493fb736c17",
    "coverage": "f6ee6f4a90274dcb",
    "drives_v1": "980f338931806e02",
    "st_net_punt": "cc97f0945a227a48",
    "possessions_to_v1": "392a4bb2bd2b489d",
    "scoring_events_to_v1": "c55751f1e057f014",
}
GOLDEN_STREAM_REGRESSIONS = {
    "team_games": 4,
    "regressed": 2,
    "games_affected": 2,
    "fraction": 0.5,
}
FINALS = {
    (1001, "Georgia"): 34.0,
    (1001, "Clemson"): 3.0,
    (1002, "Texas"): 34.0,
    (1002, "Michigan"): 31.0,
}


def _play(game, drive, number, offense, defense, off_score, def_score, quarter=1, **kw):
    row = dict(
        season=2024,
        week=1,
        game_id=game,
        drive_number=drive,
        play_number=number,
        offense=offense,
        defense=defense,
        offense_score=off_score,
        defense_score=def_score,
        play_type="Rush",
        quarter=quarter,
        st=0,
        penalty=0,
        twopoint=0,
        garbage=0,
        ppa=0.1 * number,
        yards_gained=5,
        eckel=0,
        yards_to_goal=60.0 - 5 * number,
        scoring=0,
        turnover=0,
        st_punt=0,
        st_fg=0,
        kick_distance=np.nan,
        is_fg_made=0,
    )
    row.update(kw)
    return row


def slate() -> pd.DataFrame:
    g, c, t, m = "Georgia", "Clemson", "Texas", "Michigan"
    td = dict(play_type="Rushing Touchdown", scoring=1)
    xp = dict(play_type="Extra Point Good", st=1)
    fg = dict(play_type="Field Goal Good", st=1, st_fg=1, is_fg_made=1, scoring=1)
    punt = dict(play_type="Punt", st=1, st_punt=1)
    rows = [
        _play(1001, 1, 1, g, c, 0, 0),
        _play(1001, 1, 2, g, c, 6, 0, **td),
        _play(1001, 1, 3, g, c, 7, 0, **xp),
        _play(1001, 2, 1, c, g, 0, 7),
        _play(1001, 2, 2, c, g, 3, 7, kick_distance=38.0, **fg),
        _play(1001, 3, 1, g, c, 7, 3, 2),
        _play(1001, 3, 2, g, c, 14, 3, 2, play_type="Passing Touchdown", scoring=1),
        _play(1001, 3, 3, g, c, 21, 3, 2, play_type="Passing Touchdown"),
        _play(1001, 3, 4, g, c, 14, 3, 2),  # provider score regression
        _play(1001, 3, 5, g, c, 20, 3, 2, play_type="Passing Touchdown", scoring=1),
        _play(1001, 3, 6, g, c, 21, 3, 2, **xp),
        _play(1001, 4, 1, c, g, 3, 21, 3, **punt),
        _play(1001, 5, 1, g, c, 21, 3, 3, eckel=1, yards_to_goal=35.0),
        _play(1001, 5, 2, g, c, 27, 3, 3, **td),
        _play(1001, 6, 1, c, g, 3, 27, 4),
        _play(1001, 6, 2, c, g, 3, 34, 4, play_type="Interception", turnover=1),
        _play(1001, 7, 1, g, c, 34, 3, 4),
        _play(1002, 1, 1, t, m, 0, 0),
        _play(1002, 1, 2, t, m, 7, 0, **td),
        _play(1002, 1, 3, t, m, 7, 0, **xp),
        _play(1002, 2, 1, m, t, 0, 7),
        _play(1002, 2, 2, m, t, 0, 7, **punt),
        _play(1002, 3, 1, t, m, 10, 0, 2, kick_distance=45.0, **fg),
        _play(1002, 4, 1, m, t, 12, 10, 4, **td),
        _play(1002, 5, 1, t, m, 12, 31, 4),
        _play(1002, 8, 1, t, m, 31, 12, 5, kick_distance=30.0, **fg),  # overtime
        _play(1002, 9, 1, m, t, 12, 31, 0),  # missing period
    ]
    return pd.DataFrame(rows)


def population() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                season=2024,
                week=1,
                game_id=game,
                kickoff_utc=f"2024-09-01T{hour}:00:00Z",
                home_team=home,
                away_team=away,
                schedule_completed=True,
                outcome_valid=True,
                forecast_eligible=True,
                measurement_usable=True,
            )
            for game, hour, home, away in (
                (1001, "18", "Georgia", "Clemson"),
                (1002, "21", "Texas", "Michigan"),
            )
        ]
    )


def outcomes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(season=2024, game_id=1001, home_points=34.0, away_points=3.0),
            dict(season=2024, game_id=1002, home_points=34.0, away_points=31.0),
        ]
    )


def digest(frame: pd.DataFrame) -> str:
    ordered = frame.reset_index(drop=True)
    ordered = ordered[sorted(ordered.columns)]
    text = ordered.to_csv(
        index=False, na_rep="<NA>", float_format="%.12g", lineterminator="\n"
    )
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@pytest.fixture(scope="module")
def built():
    byplay, pop, out = slate(), population(), outcomes()
    producer = pm.build_measurements(byplay=byplay, population=pop, outcomes=out)
    verifier = reconstruct_measurements(byplay=byplay, outcomes=out, population=pop)
    drives = aggregate_drives(byplay.assign(quarter=byplay["quarter"].clip(lower=1)))
    return byplay, producer, verifier, drives


@pytest.mark.parametrize(
    "name", ["possessions", "scoring_events", "observations", "coverage"]
)
def test_producer_and_verifier_outputs_are_unchanged(built, name):
    _, producer, verifier, _ = built
    assert digest(getattr(producer, name)) == GOLDEN[name]
    assert digest(getattr(verifier, name)) == GOLDEN[name]


def test_drive_and_special_teams_aggregates_are_unchanged(built):
    byplay, _, _, drives = built
    assert digest(drives) == GOLDEN["drives_v1"]
    assert digest(calculate_st_analytics_agg(byplay, drives)) == GOLDEN["st_net_punt"]


def test_gold_conversions_are_unchanged(built):
    byplay, producer, _, drives = built
    versions = {"byplay": "v1"}
    possessions = ml.possessions_to_v1(
        producer.possessions, drives.assign(season=2024), source_versions=versions
    )
    assert digest(possessions) == GOLDEN["possessions_to_v1"]
    events = ml.scoring_events_to_v1(
        producer.scoring_events, byplay, finals=FINALS, source_versions=versions
    )
    assert digest(events) == GOLDEN["scoring_events_to_v1"]


def test_score_stream_check_is_unchanged(built):
    byplay = built[0]
    assert score_stream_regressions(byplay) == GOLDEN_STREAM_REGRESSIONS


@pytest.mark.parametrize(("dataset", "version"), sorted(SCHEMA_SHAS))
def test_v1_schema_identities_do_not_move(dataset, version):
    assert schema_for(dataset, version).sha256 == SCHEMA_SHAS[(dataset, version)]
