"""v2 grading uses the frozen selected side and point, never a recomputed lean."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "pipeline"))

import score_to_db  # noqa: E402


class _Cursor:
    def __init__(self, frozen: dict[str, tuple]):
        self.frozen = frozen
        self.grades: list[dict] = []
        self._row = None

    def execute(self, sql, params=None):
        if "FROM prediction_market_selections" in sql:
            self._row = self.frozen.get(params[2])
        else:
            self.grades.append(params)

    def fetchone(self):
        return self._row


def _scored(home: int, away: int) -> pd.Series:
    return pd.Series(
        {
            "game_id": 7,
            "home_points": home,
            "away_points": away,
            # A later recomputed lean that disagrees with the frozen record.
            "spread_lean": "home",
            "spread_result_norm": "win",
            "total_lean": "over",
            "total_result_norm": "win",
        }
    )


def _frozen(side, point, target):
    return (
        f"snap-{target}",
        f"q-{target}",
        side,
        point,
        -110.0,
        "model_side_best_quote_v2",
    )


def test_grades_follow_frozen_side_and_point():
    cur = _Cursor(
        {
            "spread": _frozen("away", 3.5, "spread"),
            "total": _frozen("under", 50.5, "total"),
        }
    )
    # Home wins 24-21: margin +3 plus frozen line 3.5 > 0 means home covers, so frozen away loses.
    score_to_db._upsert_run_grades(cur, _scored(24, 21), run_id="r1")
    by_target = {g["target"]: g for g in cur.grades}
    assert by_target["spread"]["result"] == "loss"
    assert by_target["spread"]["side"] == "away"
    assert by_target["spread"]["market_quote_id"] == "q-spread"
    assert by_target["total"]["result"] == "win"  # 45 < 50.5, frozen under


def test_exact_push_on_frozen_point():
    cur = _Cursor(
        {
            "spread": _frozen("home", -3.0, "spread"),
            "total": _frozen("over", 45.0, "total"),
        }
    )
    score_to_db._upsert_run_grades(cur, _scored(24, 21), run_id="r1")
    assert [g["result"] for g in cur.grades] == ["push", "push"]


def test_frozen_grading_requires_certified_scores():
    cur = _Cursor({"spread": _frozen("home", -3.0, "spread")})
    scored = _scored(24, 21)
    scored["home_points"] = None
    with pytest.raises(ValueError, match="certified actual scores"):
        score_to_db._upsert_run_grades(cur, scored, run_id="r1")
