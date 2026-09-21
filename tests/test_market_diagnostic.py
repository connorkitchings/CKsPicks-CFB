"""Unit tests for the Contract 02 2025 market-line diagnostic study.

Uses small synthetic fixtures; never touches R2, Neon, or production.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.forecast.market_diagnostic import (
    MARKET_CONTENT_SHA,
    MARKET_DATASET,
    MARKET_SCHEMA_VERSION,
    MARKET_URI,
    MARKET_VERSION_ID,
    PERMITTED_USE,
    MarketDiagnosticError,
    _paired_metrics,
    assert_market_quarantined,
    build_study_population,
    render_report,
    replay_market_ref_uris,
    resolve_market_snapshots_ref,
    validate_sign_convention,
    validate_snapshots_frame,
)


class FakeStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)

    def read_bytes(self, uri: str) -> bytes:
        try:
            return self.objects[uri]
        except KeyError:
            raise FileNotFoundError(uri) from None


def _pinned_ref(extra: dict | None = None) -> dict:
    ref = {
        "dataset": MARKET_DATASET,
        "version_id": MARKET_VERSION_ID,
        "schema_version": MARKET_SCHEMA_VERSION,
        "content_sha": MARKET_CONTENT_SHA,
        "uri": MARKET_URI,
        "entity": "betting_lines",
        "year": 2025,
    }
    if extra:
        ref.update(extra)
    return ref


_SPREAD_SCHEDULE = [-10.0, -7.0, -3.0, -1.0, 2.0, 5.0, 7.0, 10.0]
_TOTAL_SCHEDULE = [38.0, 44.0, 49.0, 55.0, 60.0, 65.0, 71.0, 77.0]


def _snapshot_frame(n: int = 8, *, spread=None, total=None) -> pd.DataFrame:
    games = list(range(1001, 1001 + n))
    cycle_spread = [_SPREAD_SCHEDULE[i % len(_SPREAD_SCHEDULE)] for i in range(n)]
    cycle_total = [_TOTAL_SCHEDULE[i % len(_TOTAL_SCHEDULE)] for i in range(n)]
    return pd.DataFrame(
        {
            "game_id": games,
            "spread_line": spread if spread is not None else cycle_spread,
            "total_line": total if total is not None else cycle_total,
            "market_policy_version": ["consensus_then_median_v1"] * n,
        }
    )


def _forecast_frame(n: int = 8) -> pd.DataFrame:
    """Consistent fixture: home-margin predictions track -spread_line."""
    games = list(range(1001, 1001 + n))
    rows = []
    for i, game in enumerate(games):
        spread = _SPREAD_SCHEDULE[i % len(_SPREAD_SCHEDULE)]
        total = _TOTAL_SCHEDULE[i % len(_TOTAL_SCHEDULE)]
        implied = -spread
        rows.append(
            {
                "game_id": game,
                "season": 2025,
                "target": "margin",
                "prediction": implied + (0.75 if i % 2 else -0.75),
                "actual": implied + (1.5 if i % 3 else -1.5),
                "completed_games": min(i, 5),
            }
        )
        rows.append(
            {
                "game_id": game,
                "season": 2025,
                "target": "total",
                "prediction": total + (0.75 if i % 2 else -0.75),
                "actual": total + (2.0 if i % 3 else -2.0),
                "completed_games": min(i, 5),
            }
        )
    return pd.DataFrame(rows)


def _storage_with_refs(*, divergent_week: str | None = None) -> FakeStorage:
    objects = {}
    for uri in replay_market_ref_uris():
        ref = _pinned_ref()
        if divergent_week is not None and uri.endswith(
            f"{divergent_week}/input_refs.json"
        ):
            ref = _pinned_ref({"content_sha": "0" * 64})
        records = [
            ref,
            _pinned_ref(
                {
                    "dataset": "market_quotes",
                    "version_id": "32db239e920946dc72480830",
                    "entity": "betting_lines_quotes",
                }
            ),
        ]
        objects[uri] = json.dumps(records).encode()
    return FakeStorage(objects)


# ---------------------------------------------------------------------------
# Ref resolution
# ---------------------------------------------------------------------------


def test_replay_ref_uris_cover_all_sixteen_weeks():
    uris = replay_market_ref_uris()
    assert len(uris) == 16
    assert uris[0].endswith("replay-2025-v4-w1/input_refs.json")
    assert uris[-1].endswith("replay-2025-v4-w16/input_refs.json")


def test_resolve_market_ref_unanimous():
    storage = _storage_with_refs()
    ref = resolve_market_snapshots_ref(storage)
    assert ref["version_id"] == MARKET_VERSION_ID
    assert ref["content_sha"] == MARKET_CONTENT_SHA
    assert ref["uri"] == MARKET_URI


def test_resolve_market_ref_divergent_fails_closed():
    storage = _storage_with_refs(divergent_week="w7")
    with pytest.raises(MarketDiagnosticError, match="disagree"):
        resolve_market_snapshots_ref(storage)


def test_resolve_market_ref_missing_fails_closed():
    with pytest.raises(MarketDiagnosticError, match="unreadable"):
        resolve_market_snapshots_ref(FakeStorage({}))


def test_resolve_market_ref_wrong_identity_fails_closed():
    storage = _storage_with_refs()
    for uri in replay_market_ref_uris():
        records = json.loads(storage.objects[uri])
        records[0] = _pinned_ref({"version_id": "deadbeef"})
        storage.objects[uri] = json.dumps(records).encode()
    with pytest.raises(MarketDiagnosticError, match="mismatch"):
        resolve_market_snapshots_ref(storage)


def test_assert_market_quarantined_passes():
    assert_market_quarantined(
        {
            "version_id": MARKET_VERSION_ID,
            "schema_version": MARKET_SCHEMA_VERSION,
            "content_sha": MARKET_CONTENT_SHA,
            "uri": MARKET_URI,
            "state": "quarantined",
        }
    )


def test_assert_market_quarantined_rejects_validated_state():
    with pytest.raises(MarketDiagnosticError, match="quarantined"):
        assert_market_quarantined(
            {
                "version_id": MARKET_VERSION_ID,
                "schema_version": MARKET_SCHEMA_VERSION,
                "content_sha": MARKET_CONTENT_SHA,
                "uri": MARKET_URI,
                "state": "validated",
            }
        )


# ---------------------------------------------------------------------------
# Snapshot validation
# ---------------------------------------------------------------------------


def test_validate_snapshots_frame_ok():
    summary = validate_snapshots_frame(_snapshot_frame())
    assert summary["snapshot_rows"] == 8
    assert summary["spread_lined"] == 8
    assert summary["policy"] == "consensus_then_median_v1"


def test_validate_snapshots_frame_duplicate_fails():
    frame = pd.concat([_snapshot_frame(n=4), _snapshot_frame(n=4)], ignore_index=True)
    with pytest.raises(MarketDiagnosticError, match="duplicate"):
        validate_snapshots_frame(frame)


def test_validate_snapshots_frame_policy_fails():
    frame = _snapshot_frame()
    frame.loc[0, "market_policy_version"] = "other_policy"
    with pytest.raises(MarketDiagnosticError, match="policy"):
        validate_snapshots_frame(frame)


# ---------------------------------------------------------------------------
# Sign convention
# ---------------------------------------------------------------------------


def test_sign_convention_passes_on_consistent_data():
    sign = validate_sign_convention(_forecast_frame(), _snapshot_frame())
    assert sign["gates"] == "pass"
    assert sign["r_pred_market"] > 0.6


def test_sign_convention_fails_on_flipped_predictions():
    forecasts = _forecast_frame()
    mask = forecasts["target"] == "margin"
    forecasts.loc[mask, "prediction"] = -forecasts.loc[mask, "prediction"]
    with pytest.raises(MarketDiagnosticError, match="Sign-convention"):
        validate_sign_convention(forecasts, _snapshot_frame())


def test_sign_convention_fails_on_garbage():
    forecasts = _forecast_frame(n=12)
    rng = np.random.default_rng(7)
    forecasts["prediction"] = rng.normal(0, 30, size=len(forecasts))
    forecasts["actual"] = rng.normal(0, 30, size=len(forecasts))
    with pytest.raises(MarketDiagnosticError, match="Sign-convention"):
        validate_sign_convention(forecasts, _snapshot_frame(n=12))


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------


def test_build_study_population_accounts_exclusions():
    forecasts = _forecast_frame(n=6)
    snapshots = _snapshot_frame(n=4)  # games 1001-1004 lined; 1005-1006 excluded
    population, accounting = build_study_population(
        forecasts, snapshots, min_intersection=1
    )
    assert len(population) == 8  # 4 games x 2 targets
    margin = accounting["per_target"]["margin"]
    assert margin["intersection_games"] == 4
    assert margin["excluded_unlined_count"] == 2
    assert margin["excluded_unlined_game_ids"] == [1005, 1006]
    # margin leg uses -spread_line; total leg uses total_line directly
    exp_margin = -float(
        snapshots.loc[snapshots["game_id"] == 1001, "spread_line"].iloc[0]
    )
    exp_total = float(snapshots.loc[snapshots["game_id"] == 1001, "total_line"].iloc[0])
    m_row = population[
        (population["target"] == "margin") & (population["game_id"] == 1001)
    ].iloc[0]
    assert m_row["market_implied"] == pytest.approx(exp_margin)
    t_row = population[
        (population["target"] == "total") & (population["game_id"] == 1001)
    ].iloc[0]
    assert t_row["market_implied"] == pytest.approx(exp_total)


def test_build_study_population_floor_fails_closed():
    forecasts = _forecast_frame(n=6)
    snapshots = _snapshot_frame(n=4)
    with pytest.raises(MarketDiagnosticError, match="floor"):
        build_study_population(forecasts, snapshots)  # default floor 500


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_paired_metrics_hand_checked():
    v5 = np.array([3.0, 5.0, 7.0])
    mkt = np.array([4.0, 4.0, 4.0])
    actual = np.array([4.0, 4.0, 4.0])
    m = _paired_metrics(v5, mkt, actual)
    assert m["n"] == 3
    assert m["v5_mae"] == pytest.approx((1 + 1 + 3) / 3)
    assert m["market_mae"] == pytest.approx(0.0)
    assert m["mae_delta_market_minus_v5"] == pytest.approx(-5 / 3)
    assert m["v5_closer"] == 0
    assert m["market_closer"] == 3
    assert m["ties"] == 0
    lo, hi = m["mae_delta_ci95"]
    assert lo <= m["mae_delta_market_minus_v5"] <= hi


def test_paired_metrics_bootstrap_deterministic():
    rng = np.random.default_rng(3)
    v5 = rng.normal(0, 5, size=50)
    mkt = rng.normal(0, 5, size=50)
    actual = rng.normal(0, 5, size=50)
    first = _paired_metrics(v5, mkt, actual)
    second = _paired_metrics(v5, mkt, actual)
    assert first["mae_delta_ci95"] == second["mae_delta_ci95"]


def test_parquet_roundtrip_for_snapshot_bytes():
    frame = _snapshot_frame()
    buf = io.BytesIO()
    frame.to_parquet(buf)
    restored = pd.read_parquet(io.BytesIO(buf.getvalue()))
    assert validate_snapshots_frame(restored)["snapshot_rows"] == len(frame)


# ---------------------------------------------------------------------------
# Report labeling
# ---------------------------------------------------------------------------


def test_render_report_carries_mandatory_labeling():
    evidence = {
        "targets": {
            "margin": {
                "overall": {
                    "n": 10,
                    "v5_mae": 14.0,
                    "v5_rmse": 18.0,
                    "v5_bias": -0.5,
                    "market_mae": 13.0,
                    "market_rmse": 17.0,
                    "market_bias": 0.1,
                    "mae_delta_market_minus_v5": -1.0,
                    "mae_delta_ci95": [-1.5, -0.5],
                    "v5_closer": 3,
                    "market_closer": 6,
                    "ties": 1,
                },
                "edge_v5_minus_market": {
                    "mean": 0.2,
                    "sd": 3.0,
                    "p10": -3.0,
                    "p25": -1.0,
                    "p50": 0.0,
                    "p75": 1.0,
                    "p90": 3.0,
                },
                "by_completed_game_stage": {},
            },
            "total": {
                "overall": {"n": 0},
                "edge_v5_minus_market": {},
                "by_completed_game_stage": {},
            },
        },
        "population": {
            "per_target": {
                "margin": {
                    "v5_games": 12,
                    "lined_games": 10,
                    "intersection_games": 10,
                    "excluded_unlined_count": 2,
                },
                "total": {
                    "v5_games": 12,
                    "lined_games": 10,
                    "intersection_games": 10,
                    "excluded_unlined_count": 2,
                },
            }
        },
        "sign_convention": {
            "n": 10,
            "r_pred_market": 0.9,
            "r_actual_pred": 0.5,
            "r_actual_market": 0.5,
            "gates": "pass",
        },
        "market": {
            "dataset": MARKET_DATASET,
            "version_id": MARKET_VERSION_ID,
            "content_sha": MARKET_CONTENT_SHA,
            "uri": MARKET_URI,
            "replay_ref_agreement": "unanimous_16_of_16",
            "catalog_state": "quarantined",
            "policy": "consensus_then_median_v1",
        },
    }
    report = render_report(
        evidence,
        run_id="test-run",
        manifest_uri="test-manifest.json",
        manifest_raw_sha256="abc123",
    )
    assert PERMITTED_USE in report
    assert "diagnostic_comparison_only" in report
    assert "provider_recorded_lines_postseason_capture" in report
    assert "NOT closing-line or CLV" in report
    assert "V4 comparison:** none" in report
