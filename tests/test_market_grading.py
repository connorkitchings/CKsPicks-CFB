import pandas as pd
import pytest

from cks_picks_cfb.models.market_grading import (
    pick_direction,
    select_best_available_quote,
    settle_quote,
)


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
