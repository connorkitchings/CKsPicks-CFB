"""Unit tests for publish_to_db parsing logic (no DB connection required).

Covers the pure-Python pieces of scripts/pipeline/publish_to_db.py:
  - _derive_lean (spread side + edge)
  - _derive_total_lean (over/under + edge)
  - _safe_float (None / NaN / string coercion)
  - load_predictions (CSV parsing + derived columns)
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

# Make scripts/pipeline importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "pipeline"
sys.path.insert(0, str(SCRIPTS_DIR))

import publish_to_db  # noqa: E402

# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------


def test_safe_float_handles_none():
    assert publish_to_db._safe_float(None) is None


def test_safe_float_handles_nan():
    assert publish_to_db._safe_float(float("nan")) is None
    assert publish_to_db._safe_float(pd.NA) is None


def test_safe_float_handles_bad_string():
    assert publish_to_db._safe_float("not-a-number") is None


def test_safe_float_handles_valid():
    assert publish_to_db._safe_float(3.5) == 3.5
    assert publish_to_db._safe_float("4.25") == 4.25
    assert publish_to_db._safe_float(0) == 0.0


# ---------------------------------------------------------------------------
# _derive_lean
# ---------------------------------------------------------------------------


def test_derive_lean_home_favorite_covers():
    # Model: home wins by ~7 (-7). Vegas: home favored by 3 (-3).
    # bet = home if pred > -line: -7 > -(-3)=3? No  -> away.
    # Actually pred=-7 means home wins by 7; line=-3 means home favored by 3.
    # pred (-7) > -line (-(-3)=3) => -7 > 3 => False => away.
    # Edge = |pred + line| = |-7 + -3| = 10
    row = pd.Series({"Spread Prediction": -7.0, "home_team_spread_line": -3.0})
    lean, edge = publish_to_db._derive_lean(row)
    assert lean == "away"
    assert edge == pytest.approx(10.0)


def test_derive_lean_home_dog_model_likes_home():
    # Vegas: home is 14-pt dog (+14). Model: home only loses by ~3 (-3).
    # bet = home if pred > -line: -3 > -14 => True
    # Edge = |-3 + 14| = 11
    row = pd.Series({"Spread Prediction": -3.0, "home_team_spread_line": 14.0})
    lean, edge = publish_to_db._derive_lean(row)
    assert lean == "home"
    assert edge == pytest.approx(11.0)


def test_derive_lean_missing_line():
    row = pd.Series({"Spread Prediction": -3.0, "home_team_spread_line": None})
    lean, edge = publish_to_db._derive_lean(row)
    assert lean is None
    assert edge is None


def test_derive_lean_missing_pred():
    row = pd.Series({"Spread Prediction": None, "home_team_spread_line": 7.0})
    lean, edge = publish_to_db._derive_lean(row)
    assert lean is None
    assert edge is None


# ---------------------------------------------------------------------------
# _derive_total_lean
# ---------------------------------------------------------------------------


def test_derive_total_lean_over():
    # Model: 49.4. Line: 44.5. Over.
    row = pd.Series({"Total Prediction": 49.4, "total_line": 44.5})
    lean, edge = publish_to_db._derive_total_lean(row)
    assert lean == "over"
    assert edge == pytest.approx(4.9, abs=0.05)


def test_derive_total_lean_under():
    row = pd.Series({"Total Prediction": 40.0, "total_line": 52.5})
    lean, edge = publish_to_db._derive_total_lean(row)
    assert lean == "under"
    assert edge == pytest.approx(12.5)


def test_derive_total_lean_missing():
    row = pd.Series({"Total Prediction": None, "total_line": 50.0})
    lean, edge = publish_to_db._derive_total_lean(row)
    assert lean is None
    assert edge is None


# ---------------------------------------------------------------------------
# load_predictions (CSV)
# ---------------------------------------------------------------------------

SAMPLE_CSV = """game_id,Game,Spread Bet,home_team_spread_line,Spread Prediction,edge_spread,Spread Confidence,total_line,Total Prediction,edge_total,Total Bet,id,start_date,home_team,away_team,Date,Time,Home Team,Away Team,predicted_spread_std_dev,predicted_total_std_dev
401762868,Bowling Green @ Massachusetts,Home,14.166666666666666,-2.5687901540513085,11.597876512615358,High,44.5,49.429388690382034,4.929388690382034,Over,401762868,2025-11-25 16:30:00-05:00,Massachusetts,Bowling Green,2025-11-25,16:30:00,Massachusetts,Bowling Green,,
401762870,Team A @ Team B,Away,-7.5,-9.5,2.0,Low,55.5,51.0,4.5,Under,401762870,2025-11-26 12:00:00-05:00,Team B,Team A,2025-11-26,12:00:00,Team B,Team A,,
"""


def test_load_predictions_derives_columns(tmp_path):
    csv = tmp_path / "CFB_week14_bets.csv"
    csv.write_text(SAMPLE_CSV)

    df = publish_to_db.load_predictions(csv)

    assert len(df) == 2
    # Row 0: pred=-2.57, line=14.17 -> bet home, edge ~11.6
    assert df.loc[0, "spread_lean"] == "home"
    assert df.loc[0, "edge_spread"] == pytest.approx(11.6, abs=0.05)
    assert df.loc[0, "total_lean"] == "over"
    # Row 1: pred=-9.5, line=-7.5 -> bet away (pred=-9.5 > -line=7.5? No), edge=|-9.5 + -7.5|=17
    assert df.loc[1, "spread_lean"] == "away"
    assert df.loc[1, "edge_spread"] == pytest.approx(17.0)
    assert df.loc[1, "total_lean"] == "under"


def test_load_predictions_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        publish_to_db.load_predictions(tmp_path / "nope.csv")


def test_publish_rejects_invalid_manifest_before_database():
    df = publish_to_db.prepare_predictions(pd.read_csv(StringIO(SAMPLE_CSV)))
    with pytest.raises(ValueError, match="expected schedule"):
        publish_to_db.publish_week(
            df,
            "unused",
            season=2026,
            week=1,
            high_conf_threshold=8.0,
            source_config="config.yaml",
            system_name="system",
            model_id="model",
            update_current=True,
            run_manifest={
                "run_id": "run-1",
                "row_count": len(df),
                "expected_games": len(df) + 1,
                "predicted_games": len(df),
                "validation": {"all_predictions_present": True},
            },
        )


# ---------------------------------------------------------------------------
# _row_to_record
# ---------------------------------------------------------------------------


def test_row_to_record_high_confidence_flag():
    """high_confidence should be True when edge_spread >= threshold."""
    row = pd.Series(
        {
            "game_id": 123,
            "home_team": "HomeU",
            "away_team": "AwayU",
            "start_date_dt": pd.Timestamp("2026-09-05 12:00:00", tz="UTC"),
            "home_team_spread_line": 14.0,
            "total_line": 50.0,
            "Spread Prediction": -3.0,
            "Total Prediction": 55.0,
            "predicted_spread_std_dev": 1.2,
            "predicted_total_std_dev": 2.1,
            "spread_lean": "home",
            "total_lean": "over",
            "edge_spread": 11.0,  # >= default threshold of 8.0
            "edge_total": 5.0,
        }
    )
    rec = publish_to_db._row_to_record(
        row,
        season=2026,
        week=1,
        high_conf_threshold=8.0,
        source_config="conf/weekly_bets/v2_champion.yaml",
        system_name="Test Model",
        model_id="TEST-001",
    )
    assert rec["high_confidence"] is True
    assert rec["game_id"] == 123
    assert rec["season"] == 2026
    assert rec["spread_lean"] == "home"
    assert rec["predicted_spread"] == -3.0
    assert rec["model_id"] == "TEST-001"


def test_row_to_record_low_confidence_flag():
    row = pd.Series(
        {
            "game_id": 124,
            "home_team": "HomeU",
            "away_team": "AwayU",
            "start_date_dt": pd.Timestamp("2026-09-05 12:00:00", tz="UTC"),
            "home_team_spread_line": -3.0,
            "total_line": 50.0,
            "Spread Prediction": -3.5,
            "Total Prediction": 51.0,
            "predicted_spread_std_dev": None,
            "predicted_total_std_dev": None,
            "spread_lean": "away",
            "total_lean": "over",
            "edge_spread": 0.5,  # < threshold
            "edge_total": 1.0,
        }
    )
    rec = publish_to_db._row_to_record(
        row,
        season=2026,
        week=1,
        high_conf_threshold=8.0,
        source_config="conf/x.yaml",
        system_name="t",
        model_id="t",
    )
    assert rec["high_confidence"] is False
    assert rec["predicted_spread_std_dev"] is None


def test_row_to_record_honors_high_confidence_eligibility():
    row = pd.Series(
        {
            "game_id": 125,
            "home_team": "HomeU",
            "away_team": "AwayU",
            "start_date_dt": pd.Timestamp("2026-09-05 12:00:00", tz="UTC"),
            "home_team_spread_line": 14.0,
            "total_line": 50.0,
            "Spread Prediction": -3.0,
            "Total Prediction": 55.0,
            "spread_lean": "home",
            "total_lean": "over",
            "edge_spread": 11.0,
            "edge_total": 5.0,
            "high_confidence_eligible": False,
        }
    )
    rec = publish_to_db._row_to_record(
        row,
        season=2026,
        week=1,
        high_conf_threshold=8.0,
        source_config="conf/x.yaml",
        system_name="t",
        model_id="t",
    )
    assert rec["high_confidence"] is False


# ---------------------------------------------------------------------------
# Market quote persistence (plan 2026-09-03 market-line-retention)
# ---------------------------------------------------------------------------

SAMPLE_QUOTE_FRAME = pd.DataFrame(
    [
        {
            "quote_id": "q1",
            "game_id": 401762868,
            "provider": "consensus",
            "captured_at": "2026-08-28T18:00:00Z",
            "spread": -7.5,
            "total": pd.NA,
            "over_under": 55.5,
            "__capture_id": "cap-1",
            "source_event_id": pd.NA,
            "quote_updated_at": pd.NA,
        },
        {
            "quote_id": "q2",
            "game_id": 401762870,
            "provider": "draftkings",
            "captured_at": "2026-08-28T17:55:00Z",
            "spread": -7.0,
            "total": 56.0,
            "over_under": pd.NA,
            "__capture_id": "cap-2",
            "source_event_id": "evt-9",
            "quote_updated_at": "2026-08-28T17:50:00Z",
            "home_spread_price": -110,
            "over_price": -105,
        },
    ]
)


def test_quote_frame_to_records_coerces_columns():
    records = publish_to_db._quote_frame_to_records(SAMPLE_QUOTE_FRAME)
    assert len(records) == 2
    first, second = records
    # over_under falls back when total is absent
    assert first["total"] == 55.5
    assert first["source_capture_id"] == "cap-1"
    assert first["source_event_id"] is None
    assert first["quote_updated_at"] is None
    assert second["total"] == 56.0
    assert second["home_spread_price"] == -110.0
    assert second["over_price"] == -105.0
    assert second["source_event_id"] == "evt-9"
    assert second["quote_updated_at"] is not None


def test_quote_frame_to_records_rejects_missing_required():
    frame = SAMPLE_QUOTE_FRAME.drop(columns=["provider"])
    with pytest.raises(ValueError, match="missing columns"):
        publish_to_db._quote_frame_to_records(frame)


def test_quote_frame_to_records_rejects_duplicate_ids():
    frame = pd.concat([SAMPLE_QUOTE_FRAME, SAMPLE_QUOTE_FRAME], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate quote IDs"):
        publish_to_db._quote_frame_to_records(frame)


def test_quote_frame_to_records_rejects_missing_timestamp():
    frame = SAMPLE_QUOTE_FRAME.copy()
    frame.loc[0, "captured_at"] = None
    with pytest.raises(ValueError, match="captured_at"):
        publish_to_db._quote_frame_to_records(frame)


def test_quote_link_targets_attribution():
    spread_only = {"spread": -3.0, "total": None}
    total_only = {"spread": None, "total": 55.0}
    both = {"spread": -3.0, "total": 55.0}
    assert publish_to_db._quote_link_targets(spread_only) == ["spread"]
    assert publish_to_db._quote_link_targets(total_only) == ["total"]
    assert publish_to_db._quote_link_targets(both) == ["spread", "total"]


def test_market_quotes_ref_from_manifest():
    manifest = {
        "input_dataset_refs": [
            {"entity": "games", "dataset": "games", "uri": "a"},
            {
                "entity": "betting_lines_quotes",
                "dataset": "market_quotes",
                "version_id": "v1",
                "uri": "b",
            },
        ]
    }
    ref = publish_to_db._market_quotes_ref_from_manifest(manifest)
    assert ref is not None and ref["version_id"] == "v1"
    assert (
        publish_to_db._market_quotes_ref_from_manifest(
            {"input_dataset_refs": [{"dataset": "games"}]}
        )
        is None
    )
    assert publish_to_db._market_quotes_ref_from_manifest(None) is None


def test_publish_fails_closed_without_quotes_for_snapshot_run():
    df = publish_to_db.prepare_predictions(pd.read_csv(StringIO(SAMPLE_CSV)))
    df["market_snapshot_id"] = "snap-1"
    df["source_quote_ids"] = '["q1"]'
    df["market_captured_at"] = "2026-08-28T18:00:00Z"
    with pytest.raises(ValueError, match="market_quotes dataset"):
        publish_to_db.publish_week(
            df,
            "unused",
            season=2026,
            week=1,
            high_conf_threshold=8.0,
            source_config="config.yaml",
            system_name="system",
            model_id="model",
            update_current=True,
            market_quotes=None,
        )
