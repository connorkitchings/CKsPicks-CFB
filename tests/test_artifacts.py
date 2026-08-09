"""Tests for operational artifact path conventions."""

import pandas as pd
import pytest

from cks_picks_cfb.artifacts import (
    active_prediction_manifest_path,
    local_prediction_path,
    local_scored_path,
    prediction_artifact_path,
    prediction_run_artifact_path,
    prediction_run_manifest_path,
    preview_prediction_manifest_path,
    read_verified_csv_artifact,
    scored_artifact_path,
    scored_artifact_prefix,
    sha256_bytes,
)
from cks_picks_cfb.data.storage import LocalStorage


def test_prediction_paths_are_explicit():
    assert "cks-picks-cfb/predictions/2026/CFB_week1_bets.csv" in str(
        local_prediction_path(2026, 1)
    )
    assert prediction_artifact_path(2026, 1) == (
        "artifacts/production/predictions/year=2026/CFB_week1_bets.csv"
    )
    assert prediction_run_artifact_path(2026, 1, "run-1") == (
        "artifacts/production/predictions/year=2026/week=1/run_id=run-1/predictions.csv"
    )
    assert prediction_run_manifest_path(2026, 1, "run-1").endswith(
        "run_id=run-1/manifest.json"
    )
    assert active_prediction_manifest_path(2026, 1).endswith(
        "legacy-pointers/year=2026/week=1/active.json"
    )
    assert preview_prediction_manifest_path(2026, 1).endswith(
        "legacy-pointers/year=2026/week=1/preview.json"
    )


def test_scored_paths_are_explicit():
    assert "cks-picks-cfb/scored/2026/CFB_week1_bets_scored.csv" in str(
        local_scored_path(2026, 1)
    )
    assert scored_artifact_path(2026, 1) == (
        "artifacts/production/scored/year=2026/CFB_week1_bets_scored.csv"
    )
    assert scored_artifact_prefix(2026) == "artifacts/production/scored/year=2026/"


def test_verified_csv_rejects_changed_artifact(tmp_path):
    storage = LocalStorage(tmp_path)
    payload = b"game_id,prediction\n1,2.5\n"
    storage.write_bytes(payload, "runs/predictions.csv")
    manifest = {
        "artifact_uri": "runs/predictions.csv",
        "artifact_sha256": sha256_bytes(payload),
    }
    result = read_verified_csv_artifact(manifest, storage)
    pd.testing.assert_frame_equal(
        result, pd.DataFrame({"game_id": [1], "prediction": [2.5]})
    )

    storage.write_bytes(b"changed", "runs/predictions.csv")
    with pytest.raises(ValueError, match="checksum mismatch"):
        read_verified_csv_artifact(manifest, storage)
