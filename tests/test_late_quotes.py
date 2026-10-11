from datetime import datetime, timezone

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.models.late_quotes import REASON, validate_late_evidence
from cks_picks_cfb.models.market_grading import select_best_quote
from cks_picks_cfb.rebuild.market_sources_lock import classify_week_markets

GAME = 401871051
KICKOFF = datetime(2026, 10, 7, tzinfo=timezone.utc)
CAPTURE = datetime(2026, 10, 8, 16, tzinfo=timezone.utc)


def declaration(**kwargs):
    return (
        dict(
            game_id=GAME,
            target="spread",
            quote_id="q",
            provider="cfbd",
            entity="betting_lines",
            reason=REASON,
        )
        | kwargs
    )


def quote(**kwargs):
    return (
        dict(
            game_id=GAME,
            target="spread",
            quote_id="q",
            snapshot_id="s",
            point=-3,
            captured_at=CAPTURE,
            __capture_provider="cfbd",
            entity="betting_lines",
        )
        | kwargs
    )


def select(q, declarations, cutoff=CAPTURE):
    return select_best_quote(
        target="spread",
        prediction=7,
        canonical_snapshot_id="s",
        canonical_line=-3,
        game_id=GAME,
        kickoff_utc=KICKOFF,
        quote_candidates=[q],
        forecast_cutoff=cutoff,
        accepted_late_quotes=declarations,
    )


def receipt(state="passed"):
    return signed_payload(
        {
            "schema_version": "cfbd_closing_line_comparison_v1",
            "state": state,
            "season": 2026,
            "comparisons": [{"game_id": 123, "matches": True}],
            "requests": [{"game_id": 123}],
        }
    )


def test_exact_cfbd_declaration_admits_quote_but_default_rejects():
    assert select(quote(), []) is None
    assert select(quote(), [declaration()]).quote_id == "q"


@pytest.mark.parametrize(
    "changes",
    [
        {"quote_id": "other"},
        {"target": "total"},
        {"game_id": 3},
        {"reason": "anything"},
        {"provider": "odds_api"},
        {"entity": "live_lines"},
    ],
)
def test_declaration_cannot_bypass_identity_or_provenance(changes):
    assert select(quote(), [declaration(**changes)]) is None


@pytest.mark.parametrize(
    "changes", [{"__capture_provider": "odds_api"}, {"entity": "live_lines"}]
)
def test_source_provenance_is_required(changes):
    assert select(quote(**changes), [declaration()]) is None


def test_exception_never_bypasses_market_cutoff_or_snapshot_linkage():
    assert select(quote(), [declaration()], KICKOFF) is None
    assert select(quote(snapshot_id="other"), [declaration()]) is None


def test_failed_missing_or_tampered_evidence_refuses_lock():
    for evidence in [None, receipt("failed"), dict(receipt(), state="failed")]:
        with pytest.raises(ValueError):
            validate_late_evidence([declaration()], evidence)


def test_lock_and_selector_agree_with_passing_evidence():
    snapshots = pd.DataFrame(
        [
            {
                "game_id": GAME,
                "market_snapshot_id": "s",
                "market_captured_at": CAPTURE,
                "spread_line": -3,
                "total_line": None,
                "source_quote_ids": '["q"]',
            }
        ]
    )
    quotes = pd.DataFrame([quote() | {"spread": -3, "total": None}])
    schedule = pd.DataFrame([{"game_id": GAME, "kickoff_utc": KICKOFF}])
    result = classify_week_markets(
        snapshots,
        quotes,
        schedule,
        as_of=CAPTURE.isoformat(),
        accepted_late_quotes=[declaration()],
        cfbd_comparison_receipt=receipt(),
    )
    assert result[0]["status"] == "eligible"
    assert result[1]["status"] == "no_canonical_line"


def test_independent_serving_verifier_admits_only_the_exact_cfbd_quote():
    from scripts.pipeline.verify_v5_intended_update_serving import _verify_target

    row = pd.Series(
        {
            "game_id": GAME,
            "start_date": KICKOFF,
            "canonical_spread_line": -3,
            "Spread Prediction": 7,
            "spread_market_quote_id": "q",
            "home_team_spread_line": -3,
            "spread_market_quote_price": -110,
            "Spread Bet": "Home",
            "edge_spread": 4,
            "source_quote_ids": '["q"]',
        }
    )
    quotes = pd.DataFrame([quote() | {"spread": -3}])
    with pytest.raises(ValueError, match="missing candidate"):
        _verify_target(row, quotes, target="spread", cutoff=pd.Timestamp(CAPTURE))
    _verify_target(
        row,
        quotes,
        target="spread",
        cutoff=pd.Timestamp(CAPTURE),
        accepted_late_quotes=[declaration()],
    )
    with pytest.raises(ValueError, match="missing candidate"):
        _verify_target(
            row,
            quotes,
            target="spread",
            cutoff=pd.Timestamp(KICKOFF),
            accepted_late_quotes=[declaration()],
        )
