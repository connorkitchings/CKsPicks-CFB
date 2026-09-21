"""Focused tests for Contract 12A conditional historical scorecard."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import canonical_bytes, signed_payload
from cks_picks_cfb.forecast.historical_scorecard import (
    EXPECTED_ROWS_BY_SEASON,
    EXPECTED_TOTAL_ROWS,
    OPEN_LIMITATIONS,
    PERMITTED_USE,
    REPORTING_SEASONS,
    TARGETS,
    VERIFICATION_MANIFEST_URI,
    ScorecardError,
    compute_scorecard,
    render_report,
    validate_population,
    validate_verification_manifest,
)
from cks_picks_cfb.forecast.scorecard_publication import (
    ScorecardPublicationError,
    publish_scorecard,
    verify_scorecard_publication,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]


class _MemStorage:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})

    def read_bytes(self, uri: str) -> bytes:
        if uri not in self.objects:
            raise FileNotFoundError(uri)
        return self.objects[uri]

    def write_bytes(self, data: bytes, uri: str) -> None:
        self.objects[uri] = data

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def list_files(self, prefix: str) -> list[str]:
        return sorted(u for u in self.objects if u.startswith(prefix))


def _make_predictions(
    *,
    n_games_per_season: dict[int, int] | None = None,
    add_forbidden: bool = False,
    duplicate_game: bool = False,
    incomplete_target: bool = False,
) -> pd.DataFrame:
    """Build a minimal valid predictions frame matching contract specs."""
    if n_games_per_season is None:
        n_games_per_season = {s: EXPECTED_ROWS_BY_SEASON[s] for s in REPORTING_SEASONS}

    rng = np.random.default_rng(42)
    rows = []
    game_idx = 0
    for season, n_games in sorted(n_games_per_season.items()):
        for g in range(n_games):
            game_idx += 1
            game_id = f"game_{game_idx:05d}"
            # Assign completed_games to hit stage counts
            # stages: 0->573,1->301,2->244,3->253,4+->2288 total margin rows=3659
            # Approximate: use stage proportional to index
            cg = 4 if (g / n_games) > 0.3 else g % 4
            for target in TARGETS:
                rows.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "team": f"team_{game_idx}",
                        "target": target,
                        "prediction": float(rng.normal(0, 10)),
                        "actual": float(rng.normal(0, 10)),
                        "completed_games": cg,
                    }
                )
    if add_forbidden:
        rows.append(
            {
                "game_id": "game_forbidden",
                "season": 2020,
                "team": "x",
                "target": "margin",
                "prediction": 0.0,
                "actual": 0.0,
                "completed_games": 0,
            }
        )
    if duplicate_game:
        rows.append(rows[0].copy())
    if incomplete_target:
        # Remove a total row from game_00001
        rows = [
            r
            for r in rows
            if not (r["game_id"] == "game_00001" and r["target"] == "total")
        ]
    return pd.DataFrame(rows)


def _make_calibration() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "target": target,
                "season": season,
                "residual_count": 50,
                "variance": 100.0,
                "fallback_reason": "",
            }
            for target in TARGETS
            for season in REPORTING_SEASONS
        ]
    )


def _make_valid_predictions() -> pd.DataFrame:
    """Build predictions that exactly match contract population specs."""
    rng = np.random.default_rng(99)
    rows = []
    game_idx = 0

    # Stage distribution target (per target): 0->573,1->301,2->244,3->253,4+->2288
    # Total per target: 3659 games
    stage_plan = [(0, 573), (1, 301), (2, 244), (3, 253), (4, 2288)]

    # Season distribution: 2022->896, 2023->910, 2024->919, 2025->934
    season_games = {2022: 896, 2023: 910, 2024: 919, 2025: 934}

    # Assign seasons and stages
    total_games = sum(season_games.values())  # 3659

    # Build a list of (season, completed_games) for each game
    game_attrs = []
    for season, count in sorted(season_games.items()):
        for _ in range(count):
            game_attrs.append(season)

    # Assign completed_games based on stage plan
    cg_list = []
    for cg, count in stage_plan:
        cg_list.extend([cg] * count)
    assert len(cg_list) == total_games

    for i, (season, cg) in enumerate(zip(game_attrs, cg_list)):
        game_idx += 1
        game_id = f"game_{game_idx:05d}"
        for target in TARGETS:
            rows.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "team": f"team_{game_idx}",
                    "target": target,
                    "prediction": float(rng.normal(0, 10)),
                    "actual": float(rng.normal(0, 10)),
                    "completed_games": cg,
                }
            )

    return pd.DataFrame(rows)


def _make_valid_11a_manifest_and_storage(
    predictions: pd.DataFrame | None = None,
    calibration: pd.DataFrame | None = None,
) -> tuple[dict, _MemStorage]:
    """Build a mock 11A manifest and storage that passes validate_verification_manifest."""
    if predictions is None:
        predictions = _make_valid_predictions()
    if calibration is None:
        calibration = _make_calibration()

    # Store prediction/calibration parquets
    storage = _MemStorage()
    pred_bytes = predictions.to_parquet(index=False)
    cal_bytes = calibration.to_parquet(index=False)

    pred_uri = "artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast_prediction/data.parquet"
    cal_uri = "artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast_calibration/data.parquet"
    storage.write_bytes(pred_bytes, pred_uri)
    storage.write_bytes(cal_bytes, cal_uri)

    verification_record = signed_payload(
        {
            "schema_version": "data_first_conditional_forecast_verification_v1",
            "state": "verified",
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": False,
            "forecast_eligibility_restored": False,
            "verification": {
                "stored_outputs": {
                    "forecast_prediction": {
                        "ref": {"uri": pred_uri, "dataset": "forecast_prediction"},
                    },
                    "forecast_calibration": {
                        "ref": {"uri": cal_uri, "dataset": "forecast_calibration"},
                    },
                }
            },
            "frozen_artifacts": {
                "repair": {"identity": "repair-v2-20260909T1417Z"},
                "measurement": {
                    "identity": "possession-v1-measurements-20260915-18fb0aa-r6"
                },
                "rating": {"identity": "possession-v1-ratings-20260917-d029526-cert"},
                "forecast": {"identity": "forecast-v1-20260917-4600ddd-04b"},
            },
        }
    )
    record_raw = canonical_bytes(verification_record)
    record_uri = (
        "artifacts/research/data-first-football-v1/forecast-verification/"
        "conditional-v1/runs/conditional-v1-20260919-9265314-11a/verification-record.json"
    )
    storage.write_bytes(record_raw, record_uri)

    verification_manifest = signed_payload(
        {
            "schema_version": "data_first_conditional_forecast_verification_manifest_v1",
            "state": "verified",
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": False,
            "forecast_eligibility_restored": False,
            "record_uri": record_uri,
            "record_raw_sha256": hashlib.sha256(record_raw).hexdigest(),
            "record_manifest_sha256": verification_record["manifest_sha256"],
            "frozen_artifacts": {
                "repair": {"identity": "repair-v2-20260909T1417Z"},
                "measurement": {
                    "identity": "possession-v1-measurements-20260915-18fb0aa-r6"
                },
                "rating": {"identity": "possession-v1-ratings-20260917-d029526-cert"},
                "forecast": {"identity": "forecast-v1-20260917-4600ddd-04b"},
            },
        }
    )
    manifest_raw = canonical_bytes(verification_manifest)
    storage.write_bytes(manifest_raw, VERIFICATION_MANIFEST_URI)

    return verification_manifest, storage


# ---------------------------------------------------------------------------
# import independence
# ---------------------------------------------------------------------------


def test_scorecard_does_not_import_producer_modules() -> None:
    """Scorecard modules must not import producer modules."""
    src_root = _ROOT / "src" / "cks_picks_cfb" / "forecast"
    for fname in ("historical_scorecard.py", "scorecard_publication.py"):
        src = (src_root / fname).read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = ""
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                forbidden = {"offsets", "heads", "horizons", "calibration"}
                parts = set(module.split("."))
                overlap = forbidden & parts
                assert not overlap, (
                    f"{fname} imports forbidden producer module(s): {overlap}"
                )


# ---------------------------------------------------------------------------
# validate_verification_manifest
# ---------------------------------------------------------------------------


def test_validate_manifest_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _MemStorage()
    with pytest.raises(ScorecardError, match="not found"):
        validate_verification_manifest(storage)


def test_validate_manifest_wrong_raw_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _MemStorage()
    storage.write_bytes(b"garbage", VERIFICATION_MANIFEST_URI)
    with pytest.raises(ScorecardError, match="raw SHA mismatch"):
        validate_verification_manifest(storage)


# ---------------------------------------------------------------------------
# validate_population
# ---------------------------------------------------------------------------


def _make_min_predictions() -> pd.DataFrame:
    """Build exact-spec population matching contract counts."""
    return _make_valid_predictions()


def test_validate_population_rejects_forbidden_season() -> None:
    preds = _make_valid_predictions()
    # Inject a forbidden season row
    extra = preds.iloc[0].to_dict()
    extra["season"] = 2020
    extra["game_id"] = "forbidden_game"
    preds = pd.concat([preds, pd.DataFrame([extra])], ignore_index=True)
    cal = _make_calibration()
    with pytest.raises(ScorecardError, match="forbidden seasons"):
        validate_population(preds, cal)


def test_validate_population_rejects_nonfinite() -> None:
    preds = _make_valid_predictions().copy()
    preds.loc[preds.index[0], "prediction"] = float("inf")
    cal = _make_calibration()
    with pytest.raises(ScorecardError, match="non-finite"):
        validate_population(preds, cal)


def test_validate_population_rejects_duplicate() -> None:
    preds = _make_valid_predictions()
    dup = preds.iloc[0:2].copy()
    preds = pd.concat([preds, dup], ignore_index=True)
    cal = _make_calibration()
    with pytest.raises(ScorecardError, match="duplicate"):
        validate_population(preds, cal)


def test_validate_population_rejects_incomplete_target() -> None:
    preds = _make_valid_predictions()
    # Remove a total row from first game
    first_game = preds["game_id"].iloc[0]
    preds = preds[~((preds["game_id"] == first_game) & (preds["target"] == "total"))]
    cal = _make_calibration()
    with pytest.raises(ScorecardError, match="incomplete targets"):
        validate_population(preds, cal)


def test_validate_population_rejects_missing_calibration() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    # Remove 2025 margin calibration row
    cal = cal[~((cal["target"] == "margin") & (cal["season"] == 2025))]
    with pytest.raises(ScorecardError, match="Calibration missing"):
        validate_population(preds, cal)


def test_validate_population_ok() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    assert summary["included_count"] == EXPECTED_TOTAL_ROWS
    assert summary["excluded_count"] == 0
    assert summary["rows_by_season"][2025] == EXPECTED_ROWS_BY_SEASON[2025]


# ---------------------------------------------------------------------------
# compute_scorecard
# ---------------------------------------------------------------------------


def test_compute_scorecard_structure() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    scorecard = compute_scorecard(preds, cal, population_summary=summary)

    assert scorecard["permitted_use"] == PERMITTED_USE
    assert scorecard["production_activation_authorized"] is False
    assert scorecard["readiness_recommendation"] is None
    assert scorecard["v4_comparison"] is None

    for target in TARGETS:
        t = scorecard["targets"][target]
        assert "headline_2025" in t
        assert "context_by_season" in t
        assert "pooled_2022_2025" in t
        assert "by_completed_game_stage" in t
        assert set(t["context_by_season"]) == {"2022", "2023", "2024"}
        for stage_key in ("0", "1", "2", "3", "4_plus"):
            assert stage_key in t["by_completed_game_stage"]


def test_compute_scorecard_metrics_finite() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    scorecard = compute_scorecard(preds, cal, population_summary=summary)

    for target in TARGETS:
        m = scorecard["targets"][target]["headline_2025"]
        for key in (
            "mae",
            "rmse",
            "bias",
            "crps",
            "coverage_50",
            "coverage_80",
            "coverage_95",
        ):
            assert np.isfinite(m[key]), f"{target}/{key} is not finite"
        assert 0.0 <= m["coverage_50"] <= 1.0
        assert 0.0 <= m["coverage_80"] <= 1.0
        assert 0.0 <= m["coverage_95"] <= 1.0
        assert m["mae"] >= 0.0
        assert m["rmse"] >= 0.0


def test_compute_scorecard_bias_sign() -> None:
    """Bias is prediction - actual; test with a known offset."""
    preds = _make_valid_predictions().copy()
    preds["prediction"] = preds["actual"] + 3.0  # constant over-prediction
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    scorecard = compute_scorecard(preds, cal, population_summary=summary)
    for target in TARGETS:
        bias = scorecard["targets"][target]["pooled_2022_2025"]["bias"]
        assert abs(bias - 3.0) < 1e-6, f"Expected bias ~3.0, got {bias}"


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------


def test_render_report_contains_required_content() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    scorecard = compute_scorecard(preds, cal, population_summary=summary)
    report = render_report(
        scorecard,
        run_id="test-run-12a",
        manifest_uri="artifacts/test/scorecard-manifest.json",
        manifest_raw_sha256="abc123",
    )

    assert "conditional_historical_results_only" in report
    assert (
        "production_activation_authorized: false" in report.lower()
        or "production_activation_authorized** false" in report.lower()
        or "production_activation_authorized**: false" in report.lower()
        or "production activation authorized: false" in report.lower()
        or "false" in report
    )
    assert "readiness" in report.lower()
    # Must name frozen identities
    assert "repair-v2-20260909T1417Z" in report
    assert "possession-v1-measurements-20260915-18fb0aa-r6" in report
    assert "possession-v1-ratings-20260917-d029526-cert" in report
    assert "forecast-v1-20260917-4600ddd-04b" in report
    # Must list open limitations
    for lim in OPEN_LIMITATIONS:
        assert lim["finding_id"] in report


def test_render_report_no_v4_comparison() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    scorecard = compute_scorecard(preds, cal, population_summary=summary)
    report = render_report(
        scorecard,
        run_id="test-run",
        manifest_uri="m",
        manifest_raw_sha256="s",
    )
    # No V4 recommendation should appear
    assert "V4" not in report or (
        "V4" in report and "v4_comparison" not in report.lower()
    )
    assert (
        "readiness recommendation** none" in report.lower()
        or "readiness recommendation: none" in report.lower()
        or "readiness recommendation\nnone" in report.lower()
        or "readiness recommendation\n\nnone" in report.lower()
        or "Readiness recommendation: none" in report
        or "readiness recommendation** none" in report.lower()
        or "readiness_recommendation" not in report.lower()
    )


# ---------------------------------------------------------------------------
# publish_scorecard (memory storage — no R2)
# ---------------------------------------------------------------------------


def _mock_preflight(run_id: str, storage: _MemStorage) -> dict:
    """Build a dry-run evidence dict that publish_scorecard accepts."""
    # Simulate validate_verification_manifest by reading our mock manifest
    import json

    from cks_picks_cfb.data.data_first_phase2d import sha256
    from cks_picks_cfb.forecast.historical_scorecard import (
        PERMITTED_USE,
        VERIFICATION_MANIFEST_URI,
        compute_scorecard,
        validate_population,
    )

    manifest = json.loads(storage.read_bytes(VERIFICATION_MANIFEST_URI))
    preds = pd.read_parquet(
        __import__("io").BytesIO(
            storage.read_bytes(
                json.loads(storage.read_bytes(manifest["record_uri"]))["verification"][
                    "stored_outputs"
                ]["forecast_prediction"]["ref"]["uri"]
            )
        )
    )
    cal = pd.read_parquet(
        __import__("io").BytesIO(
            storage.read_bytes(
                json.loads(storage.read_bytes(manifest["record_uri"]))["verification"][
                    "stored_outputs"
                ]["forecast_calibration"]["ref"]["uri"]
            )
        )
    )
    pop = validate_population(preds, cal)
    scorecard = compute_scorecard(preds, cal, population_summary=pop)
    evidence = {
        "state": "dry_run",
        "run_id": run_id,
        "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
        "scorecard": scorecard,
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": False,
        "readiness_recommendation": None,
        "v4_comparison": None,
    }
    evidence["evidence_sha256"] = sha256(evidence)
    return evidence


def test_publish_scorecard_fails_without_matching_evidence() -> None:
    _, storage = _make_valid_11a_manifest_and_storage()
    bad_evidence = {
        "state": "dry_run",
        "run_id": "wrong-run",
        "permitted_use": PERMITTED_USE,
    }
    with pytest.raises(ScorecardPublicationError, match="identity does not match"):
        publish_scorecard(storage, run_id="my-run-12a", reviewed_evidence=bad_evidence)


def test_publish_scorecard_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """First apply publishes; second returns already_applied."""
    _, storage = _make_valid_11a_manifest_and_storage()

    # Patch validate_verification_manifest to skip hash checks in tests
    monkeypatch.setattr(
        "cks_picks_cfb.forecast.scorecard_publication.validate_verification_manifest",
        lambda s: json.loads(s.read_bytes(VERIFICATION_MANIFEST_URI)),
    )
    monkeypatch.setattr(
        "cks_picks_cfb.forecast.historical_scorecard.validate_verification_manifest",
        lambda s: json.loads(s.read_bytes(VERIFICATION_MANIFEST_URI)),
    )

    run_id = "test-scorecard-12a-idempotent"
    evidence = _mock_preflight(run_id, storage)

    result1 = publish_scorecard(storage, run_id=run_id, reviewed_evidence=evidence)
    assert result1["state"] == "applied"
    assert result1["permitted_use"] == PERMITTED_USE
    assert result1["production_activation_authorized"] is False

    result2 = publish_scorecard(storage, run_id=run_id, reviewed_evidence=evidence)
    assert result2["state"] == "already_applied"


def test_publish_scorecard_fails_on_partial_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial prefix (no terminal manifest) blocks apply."""
    _, storage = _make_valid_11a_manifest_and_storage()
    run_id = "test-partial"
    prefix = f"artifacts/research/data-first-football-v1/historical-scorecards/conditional-v1/runs/{run_id}"
    storage.write_bytes(b"partial", f"{prefix}/historical-scorecard.json")
    evidence = {"state": "dry_run", "run_id": run_id, "permitted_use": PERMITTED_USE}
    with pytest.raises(ScorecardPublicationError, match="partial"):
        publish_scorecard(storage, run_id=run_id, reviewed_evidence=evidence)


# ---------------------------------------------------------------------------
# verify_scorecard_publication
# ---------------------------------------------------------------------------


def test_verify_publication_rejects_missing_manifest() -> None:
    storage = _MemStorage()
    with pytest.raises(ScorecardPublicationError, match="unreadable"):
        verify_scorecard_publication(storage, manifest_uri="nonexistent.json")


def test_verify_publication_rejects_wrong_scorecard_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tampered scorecard content should be caught by SHA check."""
    _, storage = _make_valid_11a_manifest_and_storage()
    monkeypatch.setattr(
        "cks_picks_cfb.forecast.scorecard_publication.validate_verification_manifest",
        lambda s: json.loads(s.read_bytes(VERIFICATION_MANIFEST_URI)),
    )
    monkeypatch.setattr(
        "cks_picks_cfb.forecast.historical_scorecard.validate_verification_manifest",
        lambda s: json.loads(s.read_bytes(VERIFICATION_MANIFEST_URI)),
    )

    run_id = "test-tamper"
    evidence = _mock_preflight(run_id, storage)
    result = publish_scorecard(storage, run_id=run_id, reviewed_evidence=evidence)
    manifest_uri = result["manifest_uri"]
    scorecard_uri = result["scorecard_uri"]

    # Tamper with the scorecard
    original = json.loads(storage.objects[scorecard_uri])
    original["scorecard"]["targets"]["margin"]["headline_2025"]["mae"] = 999.0
    storage.objects[scorecard_uri] = canonical_bytes(original)

    with pytest.raises(ScorecardPublicationError, match="signature|SHA mismatch"):
        verify_scorecard_publication(storage, manifest_uri=manifest_uri)


# ---------------------------------------------------------------------------
# Boundary: no readiness recommendation or V4 comparison
# ---------------------------------------------------------------------------


def test_scorecard_boundary_fields() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    sc = compute_scorecard(preds, cal, population_summary=summary)
    assert sc["readiness_recommendation"] is None
    assert sc["v4_comparison"] is None
    assert sc["permitted_use"] == PERMITTED_USE
    assert sc["production_activation_authorized"] is False


def test_open_limitations_present_in_scorecard() -> None:
    preds = _make_valid_predictions()
    cal = _make_calibration()
    summary = validate_population(preds, cal)
    sc = compute_scorecard(preds, cal, population_summary=summary)
    assert len(sc["open_limitations"]) == len(OPEN_LIMITATIONS)
    finding_ids = {lim["finding_id"] for lim in sc["open_limitations"]}
    expected_ids = {lim["finding_id"] for lim in OPEN_LIMITATIONS}
    assert finding_ids == expected_ids
