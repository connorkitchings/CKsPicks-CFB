"""Tests for Stage 6B reconstruction stages, schemas, boundaries, and receipt."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.models.market_grading import select_best_quote
from cks_picks_cfb.rebuild import recon_comparison, recon_receipt
from cks_picks_cfb.rebuild.errors import TargetError
from cks_picks_cfb.rebuild.legacy import (
    _profit,
    score_bets,
    spread_result,
    total_result,
)
from cks_picks_cfb.rebuild.plan import RebuildPlan
from cks_picks_cfb.rebuild.recon_common import LEGACY_6A_RECEIPT_SHA
from cks_picks_cfb.rebuild.recon_stages import SIX_B_STAGE_BUILDERS
from cks_picks_cfb.rebuild.stages import STAGE_BUILDERS, get_stages
from cks_picks_cfb.rebuild.targets import GuardedStore, InMemoryStore

REPO = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO / "conf/rebuild/6b_v1.yaml"
IDENTITY = "r2:bfea6d113b8173c1f28a7d528825c924:cks-picks-cfb-preview"


# ---------------------------------------------------------------------------
# 1. Plan and Namespace Dispatch Tests
# ---------------------------------------------------------------------------


def test_6b_plan_loads_and_validates():
    plan_dict = yaml.safe_load(PLAN_PATH.read_text())
    plan = RebuildPlan.from_dict(plan_dict)
    plan.validate()

    assert plan.namespace == "rebuild/6b/"
    assert plan.run_id == "6b-replay-20261005-r1"
    assert plan.storage_identity == IDENTITY
    assert len(plan.stages) == 12

    stage_names = [s.name for s in plan.stages]
    assert stage_names == [
        "foundation",
        "scoring_events_2026",
        "offsets_2026",
        "states_at_cutoff",
        "application_frames",
        "predictions",
        "markets",
        "finals",
        "old_grade_reproduction",
        "retrospective_grades",
        "comparison",
        "receipt",
    ]

    # Verify input pins
    pin_names = {p.name for p in plan.inputs}
    assert {
        "root_manifest_6a",
        "root_manifest_task4",
        "task4_receipt",
        "source_lock_2026",
        "bets_config",
        "silver_2026_parents",
        "reconstruction_source_refs",
    } <= pin_names


def test_6b_stage_dispatch_by_namespace():
    plan_dict = yaml.safe_load(PLAN_PATH.read_text())
    plan_6b = RebuildPlan.from_dict(plan_dict)
    stages_6b = get_stages(plan_6b)

    assert len(stages_6b) == 12
    # Check that stage builders are from SIX_B_STAGE_BUILDERS
    for stage in stages_6b:
        expected_build, expected_verify = SIX_B_STAGE_BUILDERS[stage.plan.name]
        assert stage.build == expected_build
        assert stage.verify == expected_verify

    # Verify that receipt in 6B uses recon_receipt, not 6A receipt
    receipt_stage = next(s for s in stages_6b if s.plan.name == "receipt")
    assert receipt_stage.build == recon_receipt.build_receipt
    assert receipt_stage.verify == SIX_B_STAGE_BUILDERS["receipt"][1]

    # Verify 6A dispatch
    plan_6a_dict = yaml.safe_load((REPO / "conf/rebuild/6a_task4_v1.yaml").read_text())
    plan_6a = RebuildPlan.from_dict(plan_6a_dict)
    stages_6a = get_stages(plan_6a)
    receipt_6a = next(s for s in stages_6a if s.plan.name == "receipt")
    assert receipt_6a.build == STAGE_BUILDERS["receipt"][0]


# ---------------------------------------------------------------------------
# 2. GuardedStore Write Boundaries
# ---------------------------------------------------------------------------


def test_6b_write_boundary_guard():
    mem = InMemoryStore(IDENTITY)
    guard = GuardedStore(
        mem,
        run_id="6b-replay-20261005-r1",
        expected_identity=IDENTITY,
        run_namespace="rebuild/6b/",
    )

    # Allowed: 6b run artifacts and reconstruction gold datasets
    guard.create_once("rebuild/6b/6b-replay-20261005-r1/foundation/summary.json", b"{}")
    guard.create_once(
        "rebuild/6b/6b-replay-20261005-r1/served/week=0/predictions.csv", b"a,b\n1,2"
    )
    guard.create_once(
        "lake/gold/dataset=reconstruction_offsets_2026/version=v1/data.parquet", b"PAR1"
    )
    guard.create_once(
        "lake/gold/dataset=reconstruction_predictions/version=v1/data.parquet", b"PAR1"
    )
    guard.create_once(
        "lake/gold/dataset=reconstruction_market_selections/version=v1/data.parquet",
        b"PAR1",
    )
    guard.create_once(
        "lake/gold/dataset=reconstruction_grades/version=v1/data.parquet", b"PAR1"
    )

    # Forbidden: 6a, silver, unrelated gold, serving, production
    with pytest.raises(TargetError, match="outside permitted"):
        guard.create_once("rebuild/6a/run1/report.json", b"{}")

    with pytest.raises(TargetError, match="outside permitted"):
        guard.create_once("lake/silver/dataset=games/version=v1/data.parquet", b"PAR1")

    with pytest.raises(TargetError, match="outside permitted"):
        guard.create_once("lake/gold/dataset=ratings/version=v1/data.parquet", b"PAR1")

    with pytest.raises(TargetError, match="forbidden"):
        guard.create_once("predictions/2026w0/data.csv", b"{}")

    with pytest.raises(TargetError, match="forbidden"):
        guard.create_once("production/predictions/2026w0.csv", b"{}")

    with pytest.raises(TargetError, match="outside permitted"):
        guard.create_once("artifacts/production/predictions/2026w0.csv", b"{}")


# ---------------------------------------------------------------------------
# 3. Legacy Grading and Scoring Helpers
# ---------------------------------------------------------------------------


def test_legacy_spread_and_total_result():
    # Spread results
    # home_points=24, away_points=17 (margin = +7)
    # line = -6.5 -> cover_margin = 7 - 6.5 = +0.5 > 0 -> Home win, Away loss
    assert spread_result(24.0, 17.0, -6.5, "home") == "win"
    assert spread_result(24.0, 17.0, -6.5, "away") == "loss"

    # line = -7.5 -> cover_margin = 7 - 7.5 = -0.5 < 0 -> Home loss, Away win
    assert spread_result(24.0, 17.0, -7.5, "home") == "loss"
    assert spread_result(24.0, 17.0, -7.5, "away") == "win"

    # line = -7.0 -> cover_margin = 0 -> Push
    assert spread_result(24.0, 17.0, -7.0, "home") == "push"
    assert spread_result(24.0, 17.0, -7.0, "away") == "push"

    # Total results
    # home_points=24, away_points=17 (total = 41)
    assert total_result(24.0, 17.0, 40.5, "over") == "win"
    assert total_result(24.0, 17.0, 40.5, "under") == "loss"
    assert total_result(24.0, 17.0, 41.5, "over") == "loss"
    assert total_result(24.0, 17.0, 41.5, "under") == "win"
    assert total_result(24.0, 17.0, 41.0, "over") == "push"

    # Missing scores or lines return None
    assert spread_result(None, 17.0, -7.0, "home") is None
    assert total_result(24.0, None, 41.0, "over") is None


def test_legacy_profit_calculation():
    assert _profit("push", -110.0) == 0.0
    assert _profit("loss", -110.0) == -1.0
    # Standard -110 profit on $100 risk is $90.91 (0.9091 units)
    assert abs(_profit("win", -110.0) - (100.0 / 110.0)) < 1e-4
    # Plus money: +150 profit is 1.5 units
    assert abs(_profit("win", 150.0) - 1.5) < 1e-4


def test_legacy_score_bets():
    bets = pd.DataFrame(
        [
            {
                "game_id": 101,
                "Spread Bet": "Home",
                "home_team_spread_line": -3.5,
                "Total Bet": "Over",
                "total_line": 50.5,
            },
            {
                "game_id": 102,
                "Spread Bet": "Away",
                "home_team_spread_line": -7.0,
                "Total Bet": "Under",
                "total_line": 45.0,
            },
        ]
    )
    scores = pd.DataFrame(
        [
            {
                "id": 101,
                "home_points": 28,
                "away_points": 24,
            },  # margin 4 > 3.5, total 52 > 50.5
            {
                "id": 102,
                "home_points": 21,
                "away_points": 14,
            },  # margin 7 == 7.0, total 35 < 45.0
        ]
    )
    scored = score_bets(bets, scores)
    assert scored.loc[0, "Spread Bet Result"] == "Win"
    assert scored.loc[0, "Total Bet Result"] == "Win"
    assert scored.loc[1, "Spread Bet Result"] == "Push"
    assert scored.loc[1, "Total Bet Result"] == "Win"


# ---------------------------------------------------------------------------
# 4. Market Selection Quote Ties & Worst-Line Away Spread Fix
# ---------------------------------------------------------------------------


def test_model_side_best_quote_v2_selection():
    from datetime import datetime, timezone

    kickoff = datetime(2026, 9, 5, 20, 0, tzinfo=timezone.utc)
    captured = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    quotes = [
        {
            "game_id": 201,
            "snapshot_id": "snap1",
            "quote_id": "q1",
            "target": "spread",
            "point": -7.0,
            "away_spread_price": -110.0,
            "captured_at": captured,
        },
        {
            "game_id": 201,
            "snapshot_id": "snap1",
            "quote_id": "q2",
            "target": "spread",
            "point": -6.5,
            "away_spread_price": -110.0,
            "captured_at": captured,
        },
    ]

    # Model predicts Home +3.0 vs market -6.5 (predicted margin +3.0 - (-6.5) = +9.5 > 0 => lean away)
    # prediction + consensus_line = 3.0 + (-6.5) = -3.5 <= 0 => away
    selected_away = select_best_quote(
        target="spread",
        prediction=3.0,
        canonical_snapshot_id="snap1",
        canonical_line=-6.5,
        game_id=201,
        kickoff_utc=kickoff,
        quote_candidates=quotes,
    )
    assert selected_away is not None
    assert selected_away.side == "away"
    # Should choose -7.0 (away +7.0), which is q1
    assert selected_away.point == -7.0
    assert selected_away.quote_id == "q1"


def test_quote_exact_ties_break_away_under():
    from datetime import datetime, timezone

    kickoff = datetime(2026, 9, 5, 20, 0, tzinfo=timezone.utc)
    captured = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    quotes = [
        {
            "game_id": 301,
            "snapshot_id": "snap2",
            "quote_id": "q3",
            "target": "spread",
            "point": -3.0,
            "away_spread_price": -110.0,
            "captured_at": captured,
        },
        {
            "game_id": 301,
            "snapshot_id": "snap2",
            "quote_id": "q4",
            "target": "total",
            "point": 48.0,
            "under_price": -110.0,
            "captured_at": captured,
        },
    ]
    # Edge is 0.0 -> tie: prediction 3.0 + (-3.0) == 0 => away
    sel_spread = select_best_quote(
        target="spread",
        prediction=3.0,
        canonical_snapshot_id="snap2",
        canonical_line=-3.0,
        game_id=301,
        kickoff_utc=kickoff,
        quote_candidates=quotes,
    )
    assert sel_spread is not None
    assert sel_spread.side == "away"

    sel_total = select_best_quote(
        target="total",
        prediction=48.0,
        canonical_snapshot_id="snap2",
        canonical_line=48.0,
        game_id=301,
        kickoff_utc=kickoff,
        quote_candidates=quotes,
    )
    assert sel_total is not None
    assert sel_total.side == "under"


# ---------------------------------------------------------------------------
# 5. Comparison Summary and Verification
# ---------------------------------------------------------------------------


def test_comparison_record_math():
    rec = recon_comparison._record_dict(wins=10, losses=8, pushes=2, profit_units=1.2)
    assert rec["wins"] == 10
    assert rec["losses"] == 8
    assert rec["pushes"] == 2
    assert rec["decisions"] == 18
    assert rec["win_pct"] == 0.5556
    assert rec["profit_units"] == 1.2
    assert rec["vs_52_4"] == round(0.5556 - 0.524, 4)


def test_verify_comparison_validates_counts():
    context = SimpleNamespace(
        read_artifact=lambda stage, key: json.dumps(
            {
                "status": "passed",
                "games_compared": 271,
                "selections_compared": 541,
                "grades_compared": 541,
                "by_week": {str(w): {} for w in range(6)},
                "retrospective_records": {"spread": {}, "total": {}, "overall": {}},
            }
        ),
        plan=SimpleNamespace(run_id="r1"),
    )
    problems = recon_comparison.verify_comparison(context)
    assert not problems

    # Missing games triggers problem
    context_bad = SimpleNamespace(
        read_artifact=lambda stage, key: json.dumps(
            {
                "status": "passed",
                "games_compared": 270,  # one short!
                "selections_compared": 541,
                "grades_compared": 541,
                "by_week": {str(w): {} for w in range(6)},
                "retrospective_records": {"spread": {}, "total": {}, "overall": {}},
            }
        ),
        plan=SimpleNamespace(run_id="r1"),
    )
    bad_problems = recon_comparison.verify_comparison(context_bad)
    assert any("games compared" in p for p in bad_problems)


# ---------------------------------------------------------------------------
# 6. Receipt Signature and Verification
# ---------------------------------------------------------------------------


def _dummy_receipt() -> dict:
    weeks_info = {
        str(w): {
            "week": w,
            "recon_run_id": f"2026w{w}-v5recon-6b-r1",
            "original_run_id": f"2026w{w}-orig",
            "game_count": 10,
            "artifacts": {
                "predictions_csv": {
                    "uri": f"rebuild/6b/run1/served/week={w}/predictions.csv",
                    "raw_sha256": "a" * 64,
                },
                "scored_csv": {
                    "uri": f"rebuild/6b/run1/served/week={w}/scored.csv",
                    "raw_sha256": "b" * 64,
                },
                "manifest_json": {
                    "uri": f"rebuild/6b/run1/served/week={w}/manifest.json",
                    "raw_sha256": "c" * 64,
                },
            },
        }
        for w in range(6)
    }
    return signed_payload(
        {
            "schema_version": recon_receipt.SCHEMA,
            "kind": "stage_6b_exit_receipt",
            "production_activation_authorized": False,
            "identity": {
                "run_id": "6b-replay-20261005-r1",
                "plan_sha256": "d" * 64,
                "code_sha": "e" * 40,
                "storage_identity": IDENTITY,
                "predecessor_6a": {
                    "main_run_id": "6a-rebuild-20261004-r1",
                    "main_root_raw_sha256": "741d262f116a51db0d33ffc84efb22aa5ff4093e7da38535073343aee1fa85d0",
                    "task4_root_raw_sha256": "3431a5fccd7465e872b526109f3262b3563f0d950f337b413c11aa8571f86b65",
                    "receipt_sha256": LEGACY_6A_RECEIPT_SHA,
                },
            },
            "coverage": {
                "games_total": 271,
                "weeks": list(range(6)),
                "weekly_counts": {0: 8, 1: 43, 2: 49, 3: 57, 4: 58, 5: 56},
                "selections_total": 541,
                "grades_total": 541,
                "unusable_team_games": 0,
            },
            "weeks": weeks_info,
            "outputs": {
                "gold_datasets": [],
                "comparison_summary": {
                    "retrospective_records": {
                        "spread": {
                            "wins": 10,
                            "losses": 5,
                            "pushes": 1,
                            "win_pct": 0.667,
                            "profit_units": 4.5,
                            "vs_52_4": 0.143,
                        },
                        "total": {
                            "wins": 8,
                            "losses": 7,
                            "pushes": 0,
                            "win_pct": 0.533,
                            "profit_units": 0.3,
                            "vs_52_4": 0.009,
                        },
                        "overall": {
                            "wins": 18,
                            "losses": 12,
                            "pushes": 1,
                            "win_pct": 0.600,
                            "profit_units": 4.8,
                            "vs_52_4": 0.076,
                        },
                    }
                },
            },
            "validation": {
                "foundation_passed": True,
                "scoring_events_passed": True,
                "offset_freeze_passed": True,
                "states_identity_passed": True,
                "frames_coverage_passed": True,
                "bundle_compatibility_passed": True,
                "markets_coverage_passed": True,
                "finals_coverage_passed": True,
                "old_grade_reproduction_passed": True,
                "retrospective_grades_passed": True,
                "comparison_passed": True,
            },
            "non_claims": list(recon_receipt.NON_CLAIMS),
        }
    )


def test_receipt_markdown_rendering():
    rc = _dummy_receipt()
    md = recon_receipt.render_markdown(rc)
    assert "# Stage 6B Exit Receipt" in md
    assert "271 (8/43/49/57/58/56)" in md
    assert "model_side_best_quote_v2" in md
    for nc in recon_receipt.NON_CLAIMS:
        assert nc in md


def test_receipt_verify_checks_production_flag_and_non_claims():
    rc = _dummy_receipt()

    # If production authorization is True, verify must fail
    rc_bad = copy.deepcopy(rc)
    rc_bad["production_activation_authorized"] = True
    context = SimpleNamespace(
        read_artifact=lambda stage, key: json.dumps(signed_payload(rc_bad)),
        plan=SimpleNamespace(run_id="run1"),
    )
    problems = recon_receipt.verify_receipt(context)
    assert any("production activation is not authorized" in p for p in problems)

    # If non_claims altered, verify must fail
    rc_bad_claims = copy.deepcopy(rc)
    rc_bad_claims["non_claims"] = rc_bad_claims["non_claims"][:2]
    context2 = SimpleNamespace(
        read_artifact=lambda stage, key: json.dumps(signed_payload(rc_bad_claims)),
        plan=SimpleNamespace(run_id="run1"),
    )
    problems2 = recon_receipt.verify_receipt(context2)
    assert any("non-claims were altered" in p for p in problems2)
