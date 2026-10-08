"""The serving verifier re-derives selections and grades under best-quote v2.

Agreement tests run the production row builder on synthetic slates and require the
independent verifier to accept every row; tamper tests require it to refuse a changed
quote, edge, bet label, confidence or snapshot identity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "pipeline"))

import verify_v5_intended_update_serving as verifier  # noqa: E402

from cks_picks_cfb.data.market_integrity import SNAPSHOT_POLICY  # noqa: E402
from cks_picks_cfb.inference.weekly import calculate_edges_and_leans  # noqa: E402

KICKOFF = "2026-09-05T20:00:00Z"
CUTOFF = pd.Timestamp("2026-09-04T12:00:00Z")


def _quotes(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "game_id",
            "quote_id",
            "captured_at",
            "spread",
            "total",
            "home_spread_price",
            "away_spread_price",
            "over_price",
            "under_price",
            "provider",
        ],
    )


def _q(qid, *, spread=None, total=None, at="2026-09-03T00:00:00Z", game=1, **prices):
    return (
        game,
        qid,
        at,
        spread,
        total,
        prices.get("home"),
        prices.get("away"),
        prices.get("over"),
        prices.get("under"),
        "book",
    )


def _rows(quotes, *, spread_pred, total_pred, canonical_spread, canonical_total, ids):
    features = pd.DataFrame(
        [
            {
                "id": 1,
                "home_team": "H",
                "away_team": "A",
                "start_date": KICKOFF,
                "home_team_spread_line": canonical_spread,
                "total_line": canonical_total,
                "market_snapshot_id": "stored",
                "source_quote_ids": json.dumps(ids),
                "market_captured_at": "2026-09-03T00:00:00Z",
                "spread_selection_rule": "provider_median",
                "total_selection_rule": "provider_median",
                "spread_provider_count": 2,
                "total_provider_count": 2,
                "home_current_season_games": 3,
                "away_current_season_games": 3,
                "prediction_regime": "established",
            }
        ]
    )
    predictions = pd.DataFrame(
        {
            "predicted_spread": [spread_pred],
            "predicted_total": [total_pred],
            "spread_model_version": ["v"],
            "total_model_version": ["v"],
            "high_confidence_eligible": [False],
        }
    )
    return calculate_edges_and_leans(
        predictions,
        features,
        spread_threshold=0.0,
        spread_threshold_high=8.0,
        total_threshold=0.0,
        run_id="r",
        market_quotes=quotes,
        forecast_cutoff=CUTOFF.to_pydatetime(),
    ).iloc[0]


def _verify_both(row, quotes, **kw):
    for target in ("spread", "total"):
        verifier._verify_target(
            row, quotes, target=target, high_threshold=8.0, cutoff=CUTOFF, **kw
        )


SCENARIOS = {
    "home side takes the highest line": dict(
        quotes=[_q("a", spread=-2.5, total=50.0), _q("b", spread=-1.5, total=51.0)],
        spread_pred=4.0,
        total_pred=55.0,
        canonical_spread=-2.0,
        canonical_total=50.5,
    ),
    "away side takes the lowest line": dict(
        quotes=[_q("a", spread=-2.5, total=50.0), _q("b", spread=-1.5, total=51.0)],
        spread_pred=-4.0,
        total_pred=45.0,
        canonical_spread=-2.0,
        canonical_total=50.5,
    ),
    "exact ties go away and under": dict(
        quotes=[_q("a", spread=3.0, total=50.0), _q("b", spread=2.5, total=50.5)],
        spread_pred=-3.0,
        total_pred=50.0,
        canonical_spread=3.0,
        canonical_total=50.0,
    ),
    "a better price breaks an equal-line tie": dict(
        quotes=[
            _q("a", spread=-2.0, total=50.0, home=-115.0, over=-105.0),
            _q("b", spread=-2.0, total=50.0, home=-105.0, over=-115.0),
        ],
        spread_pred=4.0,
        total_pred=55.0,
        canonical_spread=-2.0,
        canonical_total=50.0,
    ),
    "a quote after the cutoff or at kickoff is not eligible": dict(
        quotes=[
            _q("a", spread=-2.0, total=50.0),
            _q("late", spread=-1.0, total=49.0, at="2026-09-04T13:00:00Z"),
            _q("kick", spread=-0.5, total=48.0, at=KICKOFF),
        ],
        spread_pred=4.0,
        total_pred=55.0,
        canonical_spread=-2.0,
        canonical_total=50.0,
    ),
    "an unlined game has no selection": dict(
        quotes=[_q("a", spread=-2.0, total=50.0)],
        spread_pred=4.0,
        total_pred=55.0,
        canonical_spread=float("nan"),
        canonical_total=float("nan"),
    ),
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_verifier_accepts_what_the_builder_selects(name):
    spec = dict(SCENARIOS[name])
    quotes = _quotes(spec.pop("quotes"))
    ids = list(quotes.quote_id)
    row = _rows(quotes, ids=ids, **spec)
    _verify_both(row, quotes)


def _good():
    spec = SCENARIOS["home side takes the highest line"]
    quotes = _quotes(spec["quotes"])
    row = _rows(
        quotes,
        ids=list(quotes.quote_id),
        **{k: v for k, v in spec.items() if k != "quotes"},
    )
    return row, quotes


@pytest.mark.parametrize(
    "change",
    [
        {"spread_market_quote_id": "a"},
        {"home_team_spread_line": -2.5},
        {"spread_market_quote_price": -105.0},
        {"edge_spread": 99.0},
        {"Spread Bet": "Away"},
        {"Spread Bet": "No Bet"},
        {"Spread Confidence": "High"},
    ],
)
def test_a_changed_spread_selection_is_refused(change):
    row, quotes = _good()
    for key, value in change.items():
        row[key] = value
    with pytest.raises(ValueError):
        _verify_both(row, quotes)


def test_a_total_selection_that_ignores_the_best_line_is_refused():
    row, quotes = _good()
    # The over/under direction here is Over, whose best line is the lowest (quote a).
    row["total_market_quote_id"], row["total_line"] = "b", 51.0
    with pytest.raises(ValueError):
        _verify_both(row, quotes)


def test_the_retired_one_point_rule_is_only_applied_when_asked():
    spec = dict(SCENARIOS["exact ties go away and under"])
    quotes = _quotes(spec.pop("quotes"))
    row = _rows(quotes, ids=list(quotes.quote_id), **spec)
    verifier._verify_target(row, quotes, target="spread", cutoff=CUTOFF)
    with pytest.raises(ValueError, match="threshold"):
        verifier._verify_target(
            row, quotes, target="spread", cutoff=CUTOFF, bet_threshold=1.0
        )


def test_the_snapshot_identity_is_recomputed_from_the_stored_snapshot():
    snapshot = pd.Series(
        {
            "spread_line": -2.0,
            "total_line": 50.5,
            "market_captured_at": "2026-09-03T00:00:00+00:00",
            "source_quote_ids": json.dumps(["a", "b"]),
            "spread_selection_rule": "provider_median",
            "total_selection_rule": "provider_median",
            "spread_provider_count": 2,
            "total_provider_count": 2,
        }
    )
    quotes = _quotes(
        [_q("a", spread=-2.0, total=50.5), _q("b", spread=-2.0, total=50.5)]
    )
    row = _rows(
        quotes,
        ids=["a", "b"],
        spread_pred=4.0,
        total_pred=55.0,
        canonical_spread=-2.0,
        canonical_total=50.5,
    )
    assert verifier.expected_snapshot_id(snapshot, 1) == row["market_snapshot_id"]
    assert SNAPSHOT_POLICY == "canonical_snapshot_v2"
    changed = snapshot.copy()
    changed["spread_provider_count"] = 3
    assert verifier.expected_snapshot_id(changed, 1) != row["market_snapshot_id"]


def test_label_thresholds_follow_the_config_defaults():
    assert verifier.label_thresholds(
        {"spread_edge_threshold": 0.0, "total_edge_threshold": 0.0}
    ) == {"spread_bet": 0.0, "spread_high": 0.0, "total_bet": 0.0, "total_grade": 0.0}
    config = {
        "spread_edge_threshold": 1.0,
        "spread_edge_threshold_high_conf": 8.0,
        "total_lean_threshold": 0.5,
        "total_edge_threshold": 1.5,
    }
    assert verifier.label_thresholds(config) == {
        "spread_bet": 1.0,
        "spread_high": 8.0,
        "total_bet": 0.5,
        "total_grade": 1.5,
    }
