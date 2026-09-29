"""Hand-computable gates for the intended V5 evidence update."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.ratings_lab.adjusted_game import CutoffAdjustment, four_pass_graph
from cks_picks_cfb.ratings_lab.contracts import Game, Observation, Rating
from cks_picks_cfb.ratings_lab.corpus import Corpus
from cks_picks_cfb.ratings_lab.replay import replay
from cks_picks_cfb.ratings_lab.updaters import (
    V5_GAME_AT_CUTOFF,
    V5_SINGLE_CUMULATIVE,
    V5_SNAPSHOT_STREAM,
)


def test_2026_cutoff_scale_uses_only_2025_terminal_values():
    terminal = pd.DataFrame(
        [
            {
                "season": 2025,
                "team": team,
                "measurement_id": "ppp",
                "unit_role": role,
                "adjusted_value": value,
                "primary_exposure": 8.0,
            }
            for role, values in (("offense", (1.0, 3.0)), ("defense", (2.0, 4.0)))
            for team, value in zip(("A", "B"), values, strict=True)
        ]
    )
    corpus = Corpus(
        pd.DataFrame(),
        pd.DataFrame(
            columns=[
                "measurement_id",
                "coverage_status",
                "denominator",
                "kickoff_utc",
                "season",
            ]
        ),
        pd.DataFrame(),
        terminal,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        {"measurement": {"sha256": "test"}},
        {},
    )
    provider = CutoffAdjustment(corpus, extra_scale_seasons=(2026,))
    assert provider.scales[("ppp", "offense", 2026)]["center"] == pytest.approx(2.0)
    assert provider.scales[("ppp", "offense", 2026)]["scale"] == pytest.approx(1.0)
    assert provider.scales[("ppp", "defense", 2026)]["center"] == pytest.approx(3.0)
    assert provider.scales[("ppp", "defense", 2026)]["sign"] == -1.0
    with pytest.raises(ValueError, match="extra scale season"):
        CutoffAdjustment(corpus, extra_scale_seasons=(2025,))


def _game(week: int) -> Game:
    kickoff = datetime(2025, 9, 1, tzinfo=timezone.utc) + timedelta(days=7 * (week - 1))
    return Game(2025, week, week, kickoff.isoformat(), "A", "B")


def _observation(
    game: Game,
    value: float,
    *,
    kind: str = "individual",
    contributors: tuple[int, ...] = (),
    exposure: float = 8.0,
) -> Observation:
    return Observation(
        game.season,
        game.week,
        game.game_id,
        "A",
        "offense",
        "ppp",
        value,
        exposure,
        (datetime.fromisoformat(game.kickoff_utc) + timedelta(hours=6)).isoformat(),
        "historically_reconstructed",
        kind,
        contributors,
    )


def test_three_game_effective_weights_and_single_shrink():
    prior = Rating(0.0, 1.0)
    games = [_game(week) for week in range(1, 4)]
    values = [1.0, 2.0, 4.0]
    cumulative = [sum(values[:index]) / index for index in range(1, 4)]
    stream = [_observation(game, value) for game, value in zip(games, cumulative)]
    repaired = [_observation(game, value) for game, value in zip(games, values)]
    control = _observation(
        games[-1],
        cumulative[-1],
        kind="cumulative",
        contributors=(1, 2, 3),
        exposure=24.0,
    )
    stream_state, _ = V5_SNAPSHOT_STREAM.estimate(prior, stream)
    repaired_state, repaired_note = V5_GAME_AT_CUTOFF.estimate(prior, repaired)
    control_state, _ = V5_SINGLE_CUMULATIVE.estimate(prior, [control])
    effective = [11 / 18, 5 / 18, 1 / 9]
    assert stream_state.mean == pytest.approx(
        0.75 * sum(w * v for w, v in zip(effective, values))
    )
    assert repaired_state.mean == pytest.approx(0.75 * sum(values) / 3)
    assert control_state.mean == pytest.approx(repaired_state.mean)
    assert control_state.variance == pytest.approx(0.25)
    assert repaired_note["prior_weight"] == pytest.approx(0.25)
    assert [part["game_id"] for part in repaired_note["evidence_contributions"]] == [
        1,
        2,
        3,
    ]
    carry = V5_GAME_AT_CUTOFF.initialize(Rating(2.0, 0.5), gap=2)
    assert carry.mean == pytest.approx(2.0 * 0.60**2)
    assert carry.variance == pytest.approx(0.60**4 * 0.5 + 1 - 0.60**4)
    with pytest.raises(ValueError, match="chronology"):
        Game(2020, 1, 99, games[0].kickoff_utc, "A", "B")


def test_four_pass_graph_preserves_cumulative_identity_and_sparse_context():
    rows = [
        SimpleNamespace(
            team="A",
            unit_role="offense",
            opponent="B",
            numerator=24.0,
            denominator=8.0,
            game_id=1,
        ),
        SimpleNamespace(
            team="B",
            unit_role="defense",
            opponent="A",
            numerator=16.0,
            denominator=8.0,
            game_id=1,
        ),
        SimpleNamespace(
            team="A",
            unit_role="offense",
            opponent="C",
            numerator=32.0,
            denominator=8.0,
            game_id=2,
        ),
        SimpleNamespace(
            team="C",
            unit_role="defense",
            opponent="A",
            numerator=8.0,
            denominator=8.0,
            game_id=2,
        ),
    ]
    graph = four_pass_graph(rows)
    adjusted_games = [
        row.numerator / row.denominator
        - (
            graph.opponent_values[(row.opponent, "defense")]
            - graph.opponent_centers["defense"]
        )
        for row in rows
        if row.team == "A"
    ]
    assert sum(adjusted_games) / 2 == pytest.approx(graph.adjusted[("A", "offense")])
    sparse = four_pass_graph(rows[:1])
    assert ("B", "defense") not in sparse.opponent_values
    assert sparse.adjusted[("A", "offense")] == 3.0


def test_cutoff_provider_cannot_inject_future_or_duplicate_game():
    games = [_game(1), _game(2), _game(3)]
    raw = [_observation(games[0], 1.0)]
    fixed = {
        (2025, team, role): Rating(0.0, 1.0)
        for team in ("A", "B")
        for role in ("offense", "defense")
    }

    def duplicate(game, team, role, observations):
        return (
            [raw[0], raw[0]]
            if game.week > 1 and team == "A" and role == "offense"
            else []
        )

    with pytest.raises(ValueError, match="duplicates"):
        replay(
            games,
            raw,
            design=V5_GAME_AT_CUTOFF,
            measurement_id="ppp",
            fixed_priors=fixed,
            cutoff_evidence=duplicate,
        )

    def future(game, team, role, observations):
        return (
            [_observation(games[-1], 4.0)] if team == "A" and role == "offense" else []
        )

    with pytest.raises(ValueError, match="chronology"):
        replay(
            games,
            raw,
            design=V5_GAME_AT_CUTOFF,
            measurement_id="ppp",
            fixed_priors=fixed,
            cutoff_evidence=future,
        )


def test_game_adjustment_uses_only_prior_week_and_six_hour_evidence():
    games = [_game(1), _game(2), _game(3), _game(4)]
    rows = []
    for game, points in zip(games, (16.0, 24.0, 80.0, 160.0), strict=True):
        for team, opponent, role, numerator in (
            ("A", "B", "offense", points),
            ("B", "A", "defense", 8.0),
        ):
            rows.append(
                {
                    "season": 2025,
                    "week": game.week,
                    "game_id": game.game_id,
                    "kickoff_utc": game.kickoff_utc,
                    "team": team,
                    "opponent": opponent,
                    "unit_role": role,
                    "measurement_id": "ppp",
                    "numerator": numerator,
                    "denominator": 8.0,
                    "raw_value": numerator / 8.0,
                    "coverage_status": "observed",
                    "missing_reason": None,
                }
            )
    population = pd.DataFrame(
        [
            {
                "season": game.season,
                "week": game.week,
                "game_id": game.game_id,
                "kickoff_utc": game.kickoff_utc,
                "home_team": "A",
                "away_team": "B",
                "forecast_eligible": True,
            }
            for game in games
        ]
    )
    terminal = pd.DataFrame(
        columns=[
            "season",
            "team",
            "measurement_id",
            "unit_role",
            "adjusted_value",
            "primary_exposure",
        ]
    )

    def corpus(records):
        return Corpus(
            population,
            pd.DataFrame(records),
            pd.DataFrame(),
            terminal,
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            {"measurement": {"sha256": "test"}},
            {},
        )

    base = CutoffAdjustment(corpus(rows))
    earlier = CutoffAdjustment(corpus(rows[:-2]))
    raw = [
        Observation(
            2025,
            game.week,
            game.game_id,
            "A",
            "offense",
            "ppp",
            points / 8.0,
            8.0,
            (datetime.fromisoformat(game.kickoff_utc) + timedelta(hours=6)).isoformat(),
            "historically_reconstructed",
        )
        for game, points in zip(games, (16.0, 24.0, 80.0, 160.0), strict=True)
    ]
    at_three = base.game_evidence(games[2], "A", "offense", raw)
    assert [item.game_id for item in at_three] == [1, 2]
    assert at_three == earlier.game_evidence(games[2], "A", "offense", raw)
    near_cutoff = games[2].kickoff_utc
    delayed_rows = rows.copy()
    delayed_rows[2] = {
        **delayed_rows[2],
        "kickoff_utc": (
            datetime.fromisoformat(near_cutoff) - timedelta(hours=3)
        ).isoformat(),
    }
    delayed_rows[3] = {**delayed_rows[3], "kickoff_utc": delayed_rows[2]["kickoff_utc"]}
    delayed = CutoffAdjustment(corpus(delayed_rows))
    delayed_raw = [
        raw[0],
        Observation(
            2025,
            2,
            2,
            "A",
            "offense",
            "ppp",
            3.0,
            8.0,
            (datetime.fromisoformat(near_cutoff) + timedelta(hours=3)).isoformat(),
            "historically_reconstructed",
        ),
    ]
    assert [
        item.game_id
        for item in delayed.game_evidence(games[2], "A", "offense", delayed_raw)
    ] == [1]


def test_sparse_opponent_uses_flagged_raw_ppp_and_missing_measurement_is_skipped():
    games = [_game(1), _game(2)]
    observations = pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": games[0].kickoff_utc,
                "team": "A",
                "opponent": "FCS-X",
                "unit_role": "offense",
                "measurement_id": "ppp",
                "numerator": 16.0,
                "denominator": 8.0,
                "raw_value": 2.0,
                "coverage_status": "observed",
            }
        ]
    )
    terminal = pd.DataFrame(
        columns=[
            "season",
            "team",
            "measurement_id",
            "unit_role",
            "adjusted_value",
            "primary_exposure",
        ]
    )
    corpus = Corpus(
        pd.DataFrame(),
        observations,
        pd.DataFrame(),
        terminal,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        {"measurement": {"sha256": "test"}},
        {},
    )
    adjuster = CutoffAdjustment(corpus)
    raw = _observation(games[0], value=2.0)
    result = adjuster.game_evidence(games[1], "A", "offense", [raw])
    assert len(result) == 1
    assert result[0].value == pytest.approx(2.0)
    assert result[0].missing_reason == "missing_opponent_context_raw_ppp"
    missing = Observation(
        2025,
        1,
        1,
        "A",
        "offense",
        "ppp",
        None,
        0.0,
        raw.available_utc,
        "historically_reconstructed",
        missing_reason="missing_measurement",
    )
    missing_result = adjuster.game_evidence(games[1], "A", "offense", [missing])
    assert len(missing_result) == 1
    assert missing_result[0].value is None
    assert missing_result[0].missing_reason == "missing_measurement"


def test_bye_preserves_rating_without_new_evidence():
    games = [_game(1), _game(3), _game(4)]
    source = _observation(games[0], 2.0)
    fixed = {
        (2025, team, role): Rating(0.0, 1.0)
        for team in ("A", "B")
        for role in ("offense", "defense")
    }
    states = replay(
        games,
        [source],
        design=V5_GAME_AT_CUTOFF,
        measurement_id="ppp",
        fixed_priors=fixed,
    )
    selected = [
        state for state in states if state.team == "A" and state.role == "offense"
    ]
    assert selected[0].rating.mean == 0.0
    assert selected[1].rating.mean == selected[2].rating.mean
    assert selected[1].evidence_game_ids == selected[2].evidence_game_ids == (1,)
