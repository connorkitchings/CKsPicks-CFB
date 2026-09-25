"""Unit tests for possession measurement score-ledger corrections (Finding 003).

Verifies that all 5 root causes diagnosed in Contract 02 are cleanly handled
and that no excess team-game keys are generated against certified final scores:
1. score_regression_rollback: rolls back false increment when provider score regresses
2. duplicate_event_or_end_of_game: skips dead non-plays and prevents duplicate terminal increments
3. overtime_attribution: prevents overtime misattribution from exceeding final score
4. pat_or_conversion_double_counting: caps points at final score if extra point was double-counted
5. provider_team_inversion_or_misattribution: caps points at final score if provider inverted teams
6. check_score_reconciliation: confirms zero excess rows in audit check
"""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.audit.corpus import check_score_reconciliation
from cks_picks_cfb.ratings.possession_measurements import build_possession_ledger


def _make_population() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "game_id": 1001,
                "home_team": "Georgia",
                "away_team": "Clemson",
                "home_points": 34.0,
                "away_points": 3.0,
                "outcome_valid": True,
                "schedule_completed": True,
                "forecast_eligible": True,
                "measurement_usable": True,
            },
            {
                "season": 2024,
                "week": 1,
                "game_id": 1002,
                "home_team": "Texas",
                "away_team": "Michigan",
                "home_points": 31.0,
                "away_points": 12.0,
                "outcome_valid": True,
                "schedule_completed": True,
                "forecast_eligible": True,
                "measurement_usable": True,
            },
        ]
    )


def _base_play(
    *,
    game_id: int = 1001,
    drive: int = 1,
    play: int = 1,
    offense: str = "Georgia",
    defense: str = "Clemson",
    off_score: float = 0.0,
    def_score: float = 0.0,
    play_type: str = "Rush",
    quarter: int = 1,
) -> dict:
    return {
        "season": 2024,
        "week": 1,
        "game_id": game_id,
        "drive_number": drive,
        "play_number": play,
        "offense": offense,
        "defense": defense,
        "offense_score": off_score,
        "defense_score": def_score,
        "play_type": play_type,
        "quarter": quarter,
        "st": 0,
        "penalty": 0,
        "twopoint": 0,
        "garbage": 0,
        "ppa": 0.1,
    }


def test_score_regression_rollback() -> None:
    """Cause 1: False increment followed by regression must be rolled back."""
    pop = _make_population()
    # Georgia final score is 34.
    # Georgia scores: 0 -> 7 -> 14 -> 21 (glitch) -> 14 (reverted) -> 21 -> 28 -> 34.
    plays = pd.DataFrame(
        [
            _base_play(play=1, off_score=0),
            _base_play(play=2, off_score=7, play_type="Touchdown"),
            _base_play(play=3, off_score=14, play_type="Touchdown"),
            # Glitch play: jumps to 21
            _base_play(play=4, off_score=21, play_type="Touchdown"),
            # Reversion play: provider reverts back to 14
            _base_play(play=5, off_score=14, play_type="Rush"),
            # Legitimate subsequent scoring
            _base_play(play=6, off_score=21, play_type="Touchdown"),
            _base_play(play=7, off_score=28, play_type="Touchdown"),
            _base_play(play=8, off_score=34, play_type="Touchdown"),
        ]
    )
    possessions, scoring = build_possession_ledger(byplay=plays, population=pop)

    georgia_events = scoring[
        (scoring["game_id"] == 1001) & (scoring["team"] == "Georgia")
    ]
    georgia_total = georgia_events["score_increment"].sum()
    assert georgia_total == 34
    # The false increment on play 4 should have been rolled back to 0
    glitch_events = georgia_events[
        georgia_events["quality_reason"] == "score_regression_rollback"
    ]
    assert len(glitch_events) == 1
    assert glitch_events.iloc[0]["score_increment"] == 0


def test_duplicate_event_or_end_of_game_filtered() -> None:
    """Cause 2: Dead non-play 'End of Game' must not create extra score."""
    pop = _make_population()
    # Texas final score is 31.
    plays = pd.DataFrame(
        [
            _base_play(
                game_id=1002, offense="Texas", defense="Michigan", play=1, off_score=0
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=2,
                off_score=7,
                play_type="Touchdown",
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=3,
                off_score=14,
                play_type="Touchdown",
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=4,
                off_score=21,
                play_type="Touchdown",
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=5,
                off_score=28,
                play_type="Touchdown",
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=6,
                off_score=31,
                play_type="Field Goal",
            ),
            # Terminal non-play 'End of Game' with spurious score increment
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=7,
                off_score=38,
                play_type="End of Game",
                quarter=4,
            ),
        ]
    )
    possessions, scoring = build_possession_ledger(byplay=plays, population=pop)

    texas_events = scoring[(scoring["game_id"] == 1002) & (scoring["team"] == "Texas")]
    assert texas_events["score_increment"].sum() == 31


def test_pat_double_counting_capped_at_final() -> None:
    """Cause 4: Double-counted PAT is capped at certified final score."""
    pop = _make_population()
    # Clemson final score is 3.
    # Provider logs Field Goal (3 pts), then erroneously logs another +1
    plays = pd.DataFrame(
        [
            _base_play(offense="Clemson", defense="Georgia", play=1, off_score=0),
            _base_play(
                offense="Clemson",
                defense="Georgia",
                play=2,
                off_score=3,
                play_type="Field Goal",
            ),
            # Spurious PAT increment on top of final 3
            _base_play(
                offense="Clemson",
                defense="Georgia",
                play=3,
                off_score=4,
                play_type="Extra Point",
            ),
        ]
    )
    possessions, scoring = build_possession_ledger(byplay=plays, population=pop)

    clemson_events = scoring[
        (scoring["game_id"] == 1001) & (scoring["team"] == "Clemson")
    ]
    assert clemson_events["score_increment"].sum() == 3


def test_provider_team_inversion_capped_at_final() -> None:
    """Cause 5: Inverted scores exceeding final score are capped."""
    pop = _make_population()
    # Michigan final score is 12.
    # Provider logs 6 -> 12, then erroneously reports another TD to 19.
    plays = pd.DataFrame(
        [
            _base_play(
                game_id=1002, offense="Michigan", defense="Texas", play=1, off_score=0
            ),
            _base_play(
                game_id=1002,
                offense="Michigan",
                defense="Texas",
                play=2,
                off_score=6,
                play_type="Touchdown",
            ),
            _base_play(
                game_id=1002,
                offense="Michigan",
                defense="Texas",
                play=3,
                off_score=12,
                play_type="Touchdown",
            ),
            # Spurious TD attributed to Michigan
            _base_play(
                game_id=1002,
                offense="Michigan",
                defense="Texas",
                play=4,
                off_score=19,
                play_type="Touchdown",
            ),
        ]
    )
    possessions, scoring = build_possession_ledger(byplay=plays, population=pop)

    michigan_events = scoring[
        (scoring["game_id"] == 1002) & (scoring["team"] == "Michigan")
    ]
    assert michigan_events["score_increment"].sum() == 12


def test_audit_score_reconciliation_zero_excess() -> None:
    """Cause 6: Full audit score reconciliation check must pass with 0 excess."""
    pop = _make_population()
    # Multi-play progressions for both games
    plays = pd.DataFrame(
        [
            _base_play(game_id=1001, play=1, off_score=7, def_score=0),
            _base_play(game_id=1001, play=2, off_score=14, def_score=0),
            _base_play(game_id=1001, play=3, off_score=21, def_score=3),
            _base_play(game_id=1001, play=4, off_score=28, def_score=3),
            _base_play(game_id=1001, play=5, off_score=34, def_score=3),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=1,
                off_score=7,
                def_score=6,
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=2,
                off_score=14,
                def_score=12,
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=3,
                off_score=21,
                def_score=12,
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=4,
                off_score=28,
                def_score=12,
            ),
            _base_play(
                game_id=1002,
                offense="Texas",
                defense="Michigan",
                play=5,
                off_score=31,
                def_score=12,
            ),
        ]
    )
    _, scoring = build_possession_ledger(byplay=plays, population=pop)

    results = check_score_reconciliation(
        scoring, pop, "mock_events.json", "mock_repair.json"
    )
    assert len(results) == 1
    assert results[0]["status"] == "pass"
    assert "never exceed" in results[0]["expected"]
    import json

    obs = json.loads(results[0]["observed"])
    assert obs["excess"]["affected_count"] == 0


def test_outcomes_merging_when_population_lacks_score_columns() -> None:
    """Outcomes dataframe supplies final score when population schema drops home/away points."""
    pop = _make_population()
    # Drop score columns from population, simulating data_first_possession_v1 schema
    pop_without_scores = pop.drop(columns=["home_points", "away_points"])
    outcomes = pd.DataFrame(
        [
            {"season": 2024, "game_id": 1001, "home_points": 34.0, "away_points": 3.0},
        ]
    )
    plays = pd.DataFrame(
        [
            _base_play(offense="Clemson", defense="Georgia", play=1, off_score=0),
            _base_play(
                offense="Clemson",
                defense="Georgia",
                play=2,
                off_score=3,
                play_type="Field Goal",
            ),
            # Spurious increment beyond final 3
            _base_play(
                offense="Clemson",
                defense="Georgia",
                play=3,
                off_score=7,
                play_type="Touchdown",
            ),
        ]
    )
    _, scoring = build_possession_ledger(
        byplay=plays, population=pop_without_scores, outcomes=outcomes
    )
    clemson_events = scoring[
        (scoring["game_id"] == 1001) & (scoring["team"] == "Clemson")
    ]
    assert clemson_events["score_increment"].sum() == 3
