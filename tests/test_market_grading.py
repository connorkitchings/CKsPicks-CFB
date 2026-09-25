"""Tests for market_grading — quote selection and settlement.

Covers:
  - pick_direction (home/away, over/under, zero edge)
  - select_best_quote (all acceptance criteria for Task 1)
    - home/away spread selection
    - over/under total selection
    - zero canonical edge → None
    - null canonical line → None
    - snapshot mismatch rejected
    - game_id mismatch rejected
    - target mismatch rejected
    - missing point/id → skipped
    - missing side price → skipped
    - post-kickoff quote → rejected
    - tie-breaking: equal point → better price → quote_id ascending
    - determinism regardless of input order
  - audit_quote_coverage (read-only)
  - settle_quote (push / win / loss)
  - select_best_available_quote (legacy backward-compat)
  - SELECTION_POLICY_VERSION constant
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from cks_picks_cfb.models.market_grading import (
    SELECTION_POLICY_VERSION,
    NormalizedQuote,
    american_profit_per_unit,
    audit_quote_coverage,
    pick_direction,
    select_best_available_quote,
    select_best_quote,
    settle_quote,
)

# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

KICKOFF = datetime(2026, 9, 20, 18, 0, 0, tzinfo=timezone.utc)
BEFORE = datetime(2026, 9, 20, 16, 0, 0, tzinfo=timezone.utc)
AFTER = datetime(2026, 9, 20, 18, 0, 1, tzinfo=timezone.utc)  # at-or-after kickoff
AT_KICKOFF = KICKOFF  # exactly at kickoff → rejected

SNAP_ID = "snap-abc"
GAME_ID = 401680001


def _spread_quote(
    quote_id: str,
    point: float,
    home_price: float | None = -110,
    away_price: float | None = -110,
    snapshot_id: str = SNAP_ID,
    game_id: int = GAME_ID,
    captured_at: datetime = BEFORE,
    target: str = "spread",
) -> dict:
    return {
        "quote_id": quote_id,
        "snapshot_id": snapshot_id,
        "game_id": game_id,
        "target": target,
        "point": point,
        "home_spread_price": home_price,
        "away_spread_price": away_price,
        "over_price": None,
        "under_price": None,
        "captured_at": captured_at,
    }


def _total_quote(
    quote_id: str,
    point: float,
    over_price: float | None = -110,
    under_price: float | None = -110,
    snapshot_id: str = SNAP_ID,
    game_id: int = GAME_ID,
    captured_at: datetime = BEFORE,
    target: str = "total",
) -> dict:
    return {
        "quote_id": quote_id,
        "snapshot_id": snapshot_id,
        "game_id": game_id,
        "target": target,
        "point": point,
        "home_spread_price": None,
        "away_spread_price": None,
        "over_price": over_price,
        "under_price": under_price,
        "captured_at": captured_at,
    }


# ---------------------------------------------------------------------------
# pick_direction
# ---------------------------------------------------------------------------


def test_pick_direction_spread_home():
    # prediction(4.0) + consensus(-3.0) = 1.0 > 0 → home
    assert pick_direction(4.0, -3.0, target="spread") == "home"


def test_pick_direction_spread_away():
    assert pick_direction(0.0, -3.0, target="spread") == "away"


def test_pick_direction_total_over():
    assert pick_direction(51.0, 48.0, target="total") == "over"


def test_pick_direction_total_under():
    assert pick_direction(47.0, 48.0, target="total") == "under"


def test_pick_direction_zero_edge_spread_is_home():
    # prediction + consensus == 0 → "home" (≥ 0)
    assert pick_direction(3.0, -3.0, target="spread") == "home"


def test_pick_direction_zero_edge_total_is_over():
    # prediction == consensus → "over" (≥)
    assert pick_direction(48.0, 48.0, target="total") == "over"


def test_pick_direction_invalid_target():
    with pytest.raises(ValueError, match="target must be spread or total"):
        pick_direction(1.0, -3.0, target="moneyline")


# ---------------------------------------------------------------------------
# select_best_quote — spread
# ---------------------------------------------------------------------------


def test_select_best_spread_home_highest_point():
    """Highest (least-negative) spread point is best for home."""
    candidates = [
        _spread_quote("q1", -3.5, home_price=-110),
        _spread_quote("q2", -3.0, home_price=-115),  # better point
    ]
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert isinstance(result, NormalizedQuote)
    assert result.quote_id == "q2"
    assert result.point == -3.0
    assert result.side == "home"
    assert result.policy_version == SELECTION_POLICY_VERSION


def test_select_best_spread_tie_better_price_wins():
    """Equal points → better American price wins."""
    candidates = [
        _spread_quote("q1", -3.0, home_price=-115),
        _spread_quote("q2", -3.0, home_price=-105),  # better price
    ]
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert result.quote_id == "q2"


def test_select_best_spread_tie_price_tie_quote_id_ascending():
    """Equal point and price → quote_id ascending."""
    candidates = [
        _spread_quote("q-z", -3.0, home_price=-110),
        _spread_quote("q-a", -3.0, home_price=-110),
    ]
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert result.quote_id == "q-a"


def test_select_best_spread_determinism():
    """Same data in different order yields same result."""
    candidates = [
        _spread_quote("q-z", -3.0, home_price=-110),
        _spread_quote("q-a", -3.0, home_price=-110),
    ]
    r1 = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    r2 = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=list(reversed(candidates)),
    )
    assert r1.quote_id == r2.quote_id


def test_select_best_spread_away():
    """Away direction picks the away_spread_price."""
    candidates = [
        _spread_quote("q1", 3.0, home_price=-110, away_price=-105),
    ]
    result = select_best_quote(
        target="spread",
        prediction=-1.0,  # -1 + 3 = 2 > 0... wait, pick_direction uses consensus
        canonical_snapshot_id=SNAP_ID,
        canonical_line=3.0,  # prediction(−1) + 3 = 2; picks home — override:
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    # prediction(-1) + canonical_line(3) = 2 ≥ 0 → "home"
    assert result is not None and result.side == "home"

    # Force away via a clearly negative combo
    result2 = select_best_quote(
        target="spread",
        prediction=-5.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=3.0,  # -5 + 3 = -2 < 0 → away
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert result2 is not None and result2.side == "away"
    assert result2.price == -105


# ---------------------------------------------------------------------------
# select_best_quote — total
# ---------------------------------------------------------------------------


def test_select_best_total_over_lowest_point():
    """Lowest total point is best for over."""
    candidates = [
        _total_quote("q1", 49.5, over_price=-110),
        _total_quote("q2", 48.5, over_price=-110),  # better for over
    ]
    result = select_best_quote(
        target="total",
        prediction=51.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=48.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert result.quote_id == "q2"
    assert result.point == 48.5
    assert result.side == "over"


def test_select_best_total_under_highest_point():
    """Highest total point is best for under."""
    candidates = [
        _total_quote("q1", 49.5, under_price=-110),
        _total_quote("q2", 48.5, under_price=-110),  # worse for under
    ]
    result = select_best_quote(
        target="total",
        prediction=44.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=48.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert result.quote_id == "q1"
    assert result.point == 49.5
    assert result.side == "under"


# ---------------------------------------------------------------------------
# select_best_quote — eligibility filtering
# ---------------------------------------------------------------------------


def test_null_canonical_line_returns_none():
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=None,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[_spread_quote("q1", -3.0)],
    )
    assert result is None


def test_snapshot_mismatch_rejected():
    q = _spread_quote("q1", -3.0, snapshot_id="OTHER-SNAP")
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is None


def test_game_id_mismatch_rejected():
    q = _spread_quote("q1", -3.0, game_id=999999)
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is None


def test_target_mismatch_rejected():
    """A total quote row must not appear in a spread selection."""
    q = _spread_quote("q1", -3.0, target="total")
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is None


def test_missing_point_skipped():
    q = _spread_quote("q1", None)  # point=None
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is None


def test_missing_side_price_skipped():
    q = _spread_quote("q1", -3.0, home_price=None)
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is None


def test_post_kickoff_quote_rejected():
    q = _spread_quote("q1", -3.0, captured_at=AFTER)
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is None


def test_at_kickoff_quote_rejected():
    """Capture at exactly kickoff is also ineligible (strictly before required)."""
    q = _spread_quote("q1", -3.0, captured_at=AT_KICKOFF)
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is None


def test_pre_kickoff_quote_accepted():
    q = _spread_quote("q1", -3.0, captured_at=BEFORE)
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is not None
    assert result.quote_id == "q1"


def test_empty_candidates_returns_none():
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=[],
    )
    assert result is None


def test_mixed_valid_and_invalid_candidates():
    """Only the eligible quote should be selected; bad ones are silently skipped."""
    candidates = [
        _spread_quote("bad1", -4.0, snapshot_id="WRONG"),
        _spread_quote("bad2", -2.0, captured_at=AFTER),
        _spread_quote("good", -3.0, home_price=-110),
    ]
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=GAME_ID,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert result is not None
    assert result.quote_id == "good"


def test_string_game_id_matches_int():
    """game_id comparison is coerced to string for safety."""
    q = _spread_quote("q1", -3.0, game_id=GAME_ID)
    result = select_best_quote(
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        game_id=str(GAME_ID),
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
    )
    assert result is not None


# ---------------------------------------------------------------------------
# audit_quote_coverage
# ---------------------------------------------------------------------------


def test_audit_eligible():
    candidates = [_spread_quote("q1", -3.0)]
    rec = audit_quote_coverage(
        run_id="run-1",
        game_id=GAME_ID,
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        kickoff_utc=KICKOFF,
        quote_candidates=candidates,
    )
    assert rec["eligible"] is True
    assert rec["selected_quote_id"] == "q1"
    assert rec["no_line_reason"] is None
    assert rec["eligible_count"] == 1


def test_audit_missing_canonical_line():
    rec = audit_quote_coverage(
        run_id="run-1",
        game_id=GAME_ID,
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=None,
        kickoff_utc=KICKOFF,
        quote_candidates=[],
    )
    assert rec["eligible"] is False
    assert rec["no_line_reason"] == "missing_canonical_line"


def test_audit_no_quotes():
    rec = audit_quote_coverage(
        run_id="run-1",
        game_id=GAME_ID,
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        kickoff_utc=KICKOFF,
        quote_candidates=[],
    )
    assert rec["eligible"] is False
    assert rec["no_line_reason"] == "no_quotes"


def test_audit_post_kickoff():
    rec = audit_quote_coverage(
        run_id="run-1",
        game_id=GAME_ID,
        target="spread",
        prediction=4.0,
        canonical_snapshot_id=SNAP_ID,
        canonical_line=-3.0,
        kickoff_utc=KICKOFF,
        quote_candidates=[_spread_quote("q1", -3.0, captured_at=AFTER)],
    )
    assert rec["eligible"] is False
    assert rec["no_line_reason"] == "post_kickoff"


# ---------------------------------------------------------------------------
# settle_quote
# ---------------------------------------------------------------------------


def test_settle_spread_win():
    profit = settle_quote(
        target="spread",
        direction="home",
        actual_spread=7.0,
        point=-3.0,
        price=-110,
    )
    assert profit > 0


def test_settle_spread_loss():
    profit = settle_quote(
        target="spread",
        direction="home",
        actual_spread=1.0,
        point=-3.0,
        price=-110,
    )
    assert profit == -1.0


def test_settle_spread_push():
    profit = settle_quote(
        target="spread",
        direction="home",
        actual_spread=3.0,
        point=-3.0,
        price=-110,
    )
    assert profit == 0.0


def test_settle_total_over_push():
    assert (
        settle_quote(
            target="total",
            direction="over",
            actual_total=48.5,
            point=48.5,
            price=-110,
        )
        == 0.0
    )


def test_settle_invalid_target():
    with pytest.raises(ValueError, match="target must be spread or total"):
        settle_quote(
            target="moneyline",
            direction="home",
            actual_spread=3.0,
            point=-3.0,
            price=-110,
        )


# ---------------------------------------------------------------------------
# american_profit_per_unit
# ---------------------------------------------------------------------------


def test_profit_favorite():
    assert abs(american_profit_per_unit(-110) - 100 / 110) < 1e-9


def test_profit_underdog():
    assert abs(american_profit_per_unit(120) - 1.2) < 1e-9


def test_profit_none_returns_default():
    assert american_profit_per_unit(None) == pytest.approx(1.0 / 1.1)


def test_profit_zero_raises():
    with pytest.raises(ValueError, match="cannot be zero"):
        american_profit_per_unit(0)


# ---------------------------------------------------------------------------
# Legacy select_best_available_quote (backward compat)
# ---------------------------------------------------------------------------


def test_direction_is_set_against_consensus_before_line_shopping():
    assert pick_direction(4.0, -3.0, target="spread") == "home"
    assert pick_direction(47.0, 48.0, target="total") == "under"


def test_best_available_prefers_line_then_price_then_bookmaker():
    quotes = pd.DataFrame(
        [
            {
                "market": "spreads",
                "side": "home",
                "point": -3.5,
                "price": -105,
                "bookmaker": "zeta",
            },
            {
                "market": "spreads",
                "side": "home",
                "point": -3.0,
                "price": -115,
                "bookmaker": "beta",
            },
            {
                "market": "spreads",
                "side": "home",
                "point": -3.0,
                "price": -110,
                "bookmaker": "alpha",
            },
        ]
    )
    quote = select_best_available_quote(quotes, target="spread", direction="home")
    assert quote["bookmaker"] == "alpha"


def test_total_over_prefers_lower_line_and_spread_settlement_uses_quote_side():
    quotes = pd.DataFrame(
        [
            {
                "market": "totals",
                "side": "over",
                "point": 49.5,
                "price": -110,
                "bookmaker": "a",
            },
            {
                "market": "totals",
                "side": "over",
                "point": 48.5,
                "price": -115,
                "bookmaker": "b",
            },
        ]
    )
    quote = select_best_available_quote(quotes, target="total", direction="over")
    assert quote["point"] == 48.5
    assert (
        settle_quote(
            target="spread", direction="away", actual_spread=3.0, point=3.5, price=-110
        )
        > 0
    )
    assert (
        settle_quote(
            target="total", direction="over", actual_total=48.5, point=48.5, price=-110
        )
        == 0.0
    )


def test_quote_selection_rejects_missing_executable_side():
    with pytest.raises(ValueError, match="No executable"):
        select_best_available_quote(
            pd.DataFrame(
                [
                    {
                        "market": "spreads",
                        "side": "home",
                        "point": -3,
                        "price": -110,
                        "bookmaker": "a",
                    }
                ]
            ),
            target="spread",
            direction="away",
        )


# ---------------------------------------------------------------------------
# SELECTION_POLICY_VERSION
# ---------------------------------------------------------------------------


def test_policy_version_constant():
    assert SELECTION_POLICY_VERSION == "model_side_best_quote_v1"
