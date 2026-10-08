"""Window 1 selection rules: exact ties go away/under, null labels stay null."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "pipeline"))

import publish_to_db  # noqa: E402
import verify_v5_intended_update_serving as verifier  # noqa: E402


def _quotes(target: str, points: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [1] * len(points),
            "quote_id": [f"q{i}" for i in range(len(points))],
            "captured_at": ["2026-09-01T00:00:00Z"] * len(points),
            target: points,
        }
    )


def _row(
    target: str, *, prediction: float, canonical: float, selected: int, point: float
):
    spread = target == "spread"
    return pd.Series(
        {
            "game_id": 1,
            "start_date": "2026-09-05T00:00:00Z",
            "source_quote_ids": json.dumps(["q0", "q1"]),
            "canonical_spread_line" if spread else "canonical_total_line": canonical,
            "Spread Prediction" if spread else "Total Prediction": prediction,
            "spread_market_quote_id"
            if spread
            else "total_market_quote_id": f"q{selected}",
            "home_team_spread_line" if spread else "total_line": point,
            "spread_market_quote_price"
            if spread
            else "total_market_quote_price": -110.0,
            "Spread Bet" if spread else "Total Bet": "No Bet",
            "edge_spread" if spread else "edge_total": abs(
                prediction + point if spread else prediction - point
            ),
        }
    )


def test_verifier_exact_spread_tie_is_away_and_takes_lowest_line():
    # prediction + canonical == 0 is a tie -> Away -> lowest home-signed line (q0).
    row = _row("spread", prediction=-3.0, canonical=3.0, selected=0, point=2.5)
    verifier._verify_target(
        row, _quotes("spread", [2.5, 3.5]), target="spread", bet_threshold=1.0
    )
    wrong = _row("spread", prediction=-3.0, canonical=3.0, selected=1, point=3.5)
    with pytest.raises(ValueError):
        verifier._verify_target(
            wrong, _quotes("spread", [2.5, 3.5]), target="spread", bet_threshold=1.0
        )


def test_verifier_exact_total_tie_is_under_and_takes_highest_line():
    row = _row("total", prediction=50.0, canonical=50.0, selected=1, point=50.5)
    verifier._verify_target(
        row, _quotes("total", [49.5, 50.5]), target="total", bet_threshold=1.0
    )


def test_publisher_null_labels_do_not_synthesize_a_lean():
    row = pd.Series(
        {
            "Spread Bet": float("nan"),
            "Spread Prediction": -2.0,
            "home_team_spread_line": 7.0,
            "Total Bet": "",
            "Total Prediction": 55.0,
            "total_line": 44.5,
        }
    )
    assert publish_to_db._derive_lean(row)[0] is None
    assert publish_to_db._derive_total_lean(row)[0] is None


def test_publisher_exact_tie_fallback_is_away_under():
    row = pd.Series(
        {
            "Spread Prediction": -3.0,
            "home_team_spread_line": 3.0,
            "Total Prediction": 50.0,
            "total_line": 50.0,
        }
    )
    assert publish_to_db._derive_lean(row)[0] == "away"
    assert publish_to_db._derive_total_lean(row)[0] == "under"
