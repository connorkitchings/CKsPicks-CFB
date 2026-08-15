from datetime import datetime, timezone

import pandas as pd
import pytest

from cks_picks_cfb.data.lake import capture_provider_records, require_dataset
from cks_picks_cfb.data.reconciliation import (
    ReconciliationError,
    reconcile_completed_games,
    require_reconciled,
)
from cks_picks_cfb.data.silver import (
    SilverValidationError,
    build_silver_version,
    normalize_games,
    normalize_legacy_market_references,
    normalize_market_quotes,
    normalize_plays,
    normalize_schedule_week_policy,
    normalize_team_game_stats,
)
from cks_picks_cfb.data.storage import LocalStorage


def test_silver_games_enforces_both_sides_are_fbs():
    games = normalize_games(
        [
            {
                "id": 1,
                "season": 2026,
                "week": 0,
                "start_date": "2026-08-22T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "home_classification": "fbs",
                "away_classification": "fbs",
            },
            {
                "id": 2,
                "season": 2026,
                "week": 0,
                "start_date": "2026-08-22T20:00:00Z",
                "home_team": "A",
                "away_team": "C",
                "home_classification": "fbs",
                "away_classification": "fcs",
            },
        ]
    )
    assert games["game_id"].tolist() == [1]
    assert games["week"].tolist() == [0]


def test_silver_plays_rejects_duplicates_and_unknown_games():
    games = pd.DataFrame([{"game_id": 1}])
    records = [
        {"id": "p1", "season": 2026, "week": 0, "game_id": 1},
        {"id": "p1", "season": 2026, "week": 0, "game_id": 1},
    ]
    with pytest.raises(SilverValidationError, match="duplicate"):
        normalize_plays(records, games=games)

    # Plays referencing non-FBS games are filtered, not fatal
    mixed = normalize_plays(
        [
            {"id": "p2", "season": 2026, "week": 0, "game_id": 1},
            {"id": "p3", "season": 2026, "week": 0, "game_id": 2},
        ],
        games=games,
    )
    assert mixed["game_id"].tolist() == [1]

    # But ALL-unknown plays still raise (complete data mismatch)
    with pytest.raises(SilverValidationError, match="unknown games"):
        normalize_plays(
            [{"id": "p4", "season": 2026, "week": 0, "game_id": 3}],
            games=games,
        )


def test_silver_version_requires_and_records_bronze_capture(tmp_path):
    storage = LocalStorage(tmp_path)
    now = datetime.now(timezone.utc)
    records = [
        {
            "id": 1,
            "season": 2026,
            "week": 0,
            "start_date": "2026-08-22T16:00:00Z",
            "home_team": "A",
            "away_team": "B",
            "home_classification": "fbs",
            "away_classification": "fbs",
        }
    ]
    capture = capture_provider_records(
        storage,
        provider="cfbd",
        entity="games",
        records=records,
        captured_at=now,
        effective_at=None,
        request={"week": 0},
    )
    _, manifest = build_silver_version(
        storage,
        dataset="games",
        records=records,
        source_captures=[capture],
        as_of=now,
        code_sha="code",
        config_sha="config",
    )
    assert manifest.source_capture_ids == (capture.capture_id,)


def test_reconciliation_blocks_team_or_score_conflicts():
    schedule = pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": 1,
                "home_team": "A",
                "away_team": "B",
                "home_points": 21,
                "away_points": 17,
                "completed": True,
            }
        ]
    )
    aggregate = pd.DataFrame(
        [
            {"game_id": 1, "team": "A", "points": 20},
            {"game_id": 1, "team": "B", "points": 17},
        ]
    )
    result = reconcile_completed_games(schedule, aggregate)
    assert result.iloc[0]["classification"] == "blocking_conflict"
    with pytest.raises(ReconciliationError, match=r"games: \[1\]"):
        require_reconciled(result)


def test_market_quotes_decode_captured_sdk_mapping_string():
    result = normalize_market_quotes(
        [
            {
                "game_id": 10,
                "week": 0,
                "line_data": (
                    "{'provider': 'Consensus', 'spread': -8.5, "
                    "'overUnder': 47.5}"
                ),
                "__capture_id": "capture-1",
                "__captured_at": "2026-08-15T14:53:00+00:00",
                "__capture_provider": "cfbd",
            }
        ]
    )

    assert result.iloc[0]["provider"] == "Consensus"
    assert result.iloc[0]["spread"] == -8.5
    assert result.iloc[0]["over_under"] == 47.5
    assert result.iloc[0]["total"] == 47.5


def test_team_game_stats_flatten_to_exact_team_game_rows():
    result = normalize_team_game_stats(
        [
            {
                "request_week": 0,
                "season": 2026,
                "provider_record": {
                    "id": 10,
                    "teams": [
                        {
                            "teamId": 1,
                            "team": "A",
                            "homeAway": "home",
                            "points": 21,
                            "stats": [{"category": "totalYards", "stat": "400"}],
                        },
                        {
                            "teamId": 2,
                            "team": "B",
                            "homeAway": "away",
                            "points": 17,
                            "stats": [{"category": "totalYards", "stat": "350"}],
                        },
                    ],
                },
            }
        ]
    )
    assert result[["game_id", "team"]].to_dict("records") == [
        {"game_id": 10, "team": "A"},
        {"game_id": 10, "team": "B"},
    ]
    assert result["total_yards"].tolist() == ["400", "350"]


def test_legacy_market_quote_requires_authentic_capture_timestamp():
    with pytest.raises(SilverValidationError, match="captured_at"):
        normalize_market_quotes(
            [
                {
                    "game_id": 1,
                    "provider": "Consensus",
                    "spread": -3.5,
                    "__captured_at": "2026-08-09T00:00:00Z",
                    "__capture_provider": "legacy_cfbd_export",
                }
            ]
        )


def _legacy_record(**overrides):
    record = {
        "year": 2021,
        "week": 1,
        "game_id": 12345,
        "provider": "Bovada",
        "spread": -7.0,
        "over_under": 48.5,
        "spread_open": -6.5,
        "over_under_open": 50.0,
        "formatted_spread": "Team A -7.0",
        "home_moneyline": -285.0,
        "away_moneyline": 230.0,
        "season_type": "regular",
        "__capture_id": "capture-abc",
        "__capture_provider": "legacy_cfbd_export",
        "__source_uri": "raw/betting_lines/year=2021/week=1/data.csv",
        "__source_sha256": "sha256-xyz",
    }
    record.update(overrides)
    return record


def test_legacy_market_references_stamps_quarantine_flags():
    frame = normalize_legacy_market_references([_legacy_record()])
    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["timestamp_status"] == "missing_authentic_timestamp"
    assert row["exact_replay_eligible"] is False or row["exact_replay_eligible"] == 0
    assert row["grading_eligible"] is False or row["grading_eligible"] == 0
    assert row["lean_eligible"] is False or row["lean_eligible"] == 0
    assert row["provider_week"] == 1
    assert row["source_capture_id"] == "capture-abc"
    assert row["source_uri"] == "raw/betting_lines/year=2021/week=1/data.csv"
    assert row["source_sha256"] == "sha256-xyz"
    assert row["spread"] == -7.0
    assert row["total"] == 48.5


def test_legacy_market_references_rejects_non_legacy_provider():
    with pytest.raises(SilverValidationError, match="legacy_cfbd_export"):
        normalize_legacy_market_references([_legacy_record(__capture_provider="cfbd")])


def test_legacy_market_references_rejects_authentic_timestamp():
    with pytest.raises(SilverValidationError, match="authentic"):
        normalize_legacy_market_references(
            [_legacy_record(captured_at="2021-09-04T18:00:00Z")]
        )


def test_legacy_market_references_requires_provenance():
    with pytest.raises(SilverValidationError, match="provenance"):
        normalize_legacy_market_references([_legacy_record(__source_uri=None)])


def test_legacy_market_references_skips_rows_without_spread_or_total():
    frame = normalize_legacy_market_references(
        [
            _legacy_record(spread=None, over_under=None),
            _legacy_record(spread=-3.5, over_under=51.0),
        ]
    )
    assert len(frame) == 1
    assert frame.iloc[0]["spread"] == -3.5


def test_require_dataset_rejects_wrong_dataset():
    from cks_picks_cfb.data.lake import DatasetRef

    ref = DatasetRef("legacy_market_references", "v1", "legacy_v1", "sha", "uri")
    with pytest.raises(ValueError, match="market_snapshots"):
        require_dataset(ref, "market_snapshots")


def test_normalize_games_preserves_provider_week_without_policy():
    games = normalize_games(
        [
            {
                "id": 1,
                "season": 2026,
                "week": 1,
                "start_date": "2026-08-29T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "home_classification": "fbs",
                "away_classification": "fbs",
            }
        ]
    )
    row = games.iloc[0]
    assert row["week"] == 1
    assert row["provider_week"] == 1


def test_normalize_games_applies_week_policy():
    games_records = [
        {
            "id": 1,
            "season": 2026,
            "week": 1,
            "start_date": "2026-08-29T16:00:00Z",
            "home_team": "A",
            "away_team": "B",
            "home_classification": "fbs",
            "away_classification": "fbs",
        },
        {
            "id": 2,
            "season": 2026,
            "week": 2,
            "start_date": "2026-09-05T16:00:00Z",
            "home_team": "C",
            "away_team": "D",
            "home_classification": "fbs",
            "away_classification": "fbs",
        },
    ]
    policy = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1,
                "provider_week": 1,
                "canonical_week": 0,
                "kickoff_utc": "2026-08-29T16:00:00Z",
            },
            {
                "season": 2026,
                "game_id": 2,
                "provider_week": 2,
                "canonical_week": 1,
                "kickoff_utc": "2026-09-05T16:00:00Z",
            },
        ]
    )
    games = normalize_games(games_records, week_policy=policy)
    assert games.iloc[0]["week"] == 0
    assert games.iloc[0]["provider_week"] == 1
    assert games.iloc[1]["week"] == 1
    assert games.iloc[1]["provider_week"] == 2


def test_normalize_games_rejects_incomplete_policy():
    games_records = [
        {
            "id": 1,
            "season": 2026,
            "week": 1,
            "start_date": "2026-08-29T16:00:00Z",
            "home_team": "A",
            "away_team": "B",
            "home_classification": "fbs",
            "away_classification": "fbs",
        },
        {
            "id": 2,
            "season": 2026,
            "week": 1,
            "start_date": "2026-08-29T19:00:00Z",
            "home_team": "C",
            "away_team": "D",
            "home_classification": "fbs",
            "away_classification": "fbs",
        },
    ]
    policy = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1,
                "provider_week": 1,
                "canonical_week": 0,
                "kickoff_utc": "2026-08-29T16:00:00Z",
            }
        ]
    )
    with pytest.raises(SilverValidationError, match="does not cover"):
        normalize_games(games_records, week_policy=policy)


def test_schedule_week_policy_validates_coverage():
    policy_rows = [
        {
            "season": 2026,
            "game_id": 1,
            "provider_week": 1,
            "canonical_week": 0,
            "kickoff_utc": "2026-08-29T16:00:00Z",
        }
    ]
    frame = normalize_schedule_week_policy(policy_rows)
    assert frame.iloc[0]["canonical_week"] == 0
