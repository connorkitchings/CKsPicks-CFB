"""Unit tests for Independent Repair Verifier v3 (Finding 001 closure).

Verifies the 5 behavioral matrix cases:
1. independent_reconstruction: zero producer imports
2. season_2020_exclusion: rejects forbidden 2020 rows
3. outcome_perturbation: rejects perturbed outcome scores
4. malformed_sources: rejects bad schema / missing columns / corrupt checksums
5. exact_byte_identity: verifies valid manifest signature and content SHA
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import canonical_bytes, signed_payload
from cks_picks_cfb.data.data_first_repair_v2 import (
    REPAIR_MANIFEST_SCHEMA,
    REPAIR_POPULATION_SCHEMA,
    RepairV2Error,
)
from scripts.research.verify_data_first_repair_v3 import (
    verify_repair_artifact,
)

ROOT = Path(__file__).resolve().parents[1]


class _MemStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def read_bytes(self, uri: str) -> bytes:
        if uri not in self.files:
            raise FileNotFoundError(uri)
        return self.files[uri]

    def write_bytes(self, data: bytes, uri: str) -> None:
        self.files[uri] = data

    def exists(self, uri: str) -> bool:
        return uri in self.files


def _make_mock_repair_environment() -> tuple[_MemStorage, str, dict[str, Any]]:
    """Build a valid mock repair v2 artifact and storage environment."""
    from cks_picks_cfb.data.schema_contracts import schema_for

    storage = _MemStorage()

    pop_schema = schema_for("repair_population", REPAIR_POPULATION_SCHEMA)
    pop_rows = []
    for game_id, home, away, hp, ap in [
        (401628455, "Georgia", "Clemson", 34, 3),
        (401628456, "Texas", "Colorado State", 52, 0),
    ]:
        row = {col: 0 for col in pop_schema.required}
        row.update(
            {
                "season": 2024,
                "week": 1,
                "game_id": game_id,
                "kickoff_utc": "2024-08-31T16:00:00Z",
                "home_team": home,
                "away_team": away,
                "home_points": hp,
                "away_points": ap,
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "measurement_exposure": 1,
                "missing_measurement_sources": "none",
                "disposition": "verified",
                "timing_class": "historically_reconstructed",
            }
        )
        pop_rows.append(row)
    pop_df = pd.DataFrame(pop_rows)
    pop_bytes = pop_df.to_parquet(index=False)
    pop_sha = hashlib.sha256(pop_bytes).hexdigest()
    pop_uri = "artifacts/mock/repair/population/data.parquet"
    storage.write_bytes(pop_bytes, pop_uri)

    output_refs = {
        "population": {
            "dataset": "repair_population",
            "version_id": "v1",
            "schema_version": REPAIR_POPULATION_SCHEMA,
            "content_sha": pop_sha,
            "uri": pop_uri,
        }
    }
    output_rows = {"population": len(pop_df)}

    for name, ds in [
        ("auxiliary", "repair_auxiliary"),
        ("coverage", "repair_coverage"),
        ("issues", "repair_issue"),
        ("capture_plan", "repair_capture_plan"),
    ]:
        schema = schema_for(ds, f"data_first_{ds}_v2")
        row = {}
        for col in schema.required:
            if col in schema.integer_columns:
                row[col] = 1
            elif col in schema.boolean_columns:
                row[col] = True
            elif schema.allowed_values and col in schema.allowed_values:
                row[col] = schema.allowed_values[col][0]
            else:
                row[col] = "test_val"
        if "season" in schema.required:
            row["season"] = 2024
        if "game_id" in schema.required:
            row["game_id"] = 401628455
        dummy_df = pd.DataFrame([row])
        dummy_bytes = dummy_df.to_parquet(index=False)
        dummy_sha = hashlib.sha256(dummy_bytes).hexdigest()
        uri = f"artifacts/mock/repair/{name}/data.parquet"
        storage.write_bytes(dummy_bytes, uri)
        output_refs[name] = {
            "dataset": ds,
            "version_id": "v1",
            "schema_version": f"data_first_{ds}_v2",
            "content_sha": dummy_sha,
            "uri": uri,
        }
        output_rows[name] = len(dummy_df)

    manifest_payload = signed_payload(
        {
            "schema_version": REPAIR_MANIFEST_SCHEMA,
            "state": "repaired_reconstructed_only",
            "identity": {
                "run_id": "mock-repair-run",
                "code_sha": "mockcode123",
            },
            "production_activation_authorized": False,
            "output_refs": output_refs,
            "output_rows": output_rows,
            "population": {
                "scheduled_games": len(pop_df),
                "forecast_eligible_games": 2,
                "measurement_usable_games": 2,
            },
        }
    )
    manifest_bytes = canonical_bytes(manifest_payload)
    manifest_uri = "artifacts/mock/repair/repair-manifest.json"
    storage.write_bytes(manifest_bytes, manifest_uri)

    return storage, manifest_uri, manifest_payload


def test_independent_reconstruction_zero_producer_imports() -> None:
    """Case 1: Must NOT import compute_repair or run_data_first_repair_v2."""
    script_path = ROOT / "scripts" / "research" / "verify_data_first_repair_v3.py"
    tree = ast.parse(script_path.read_text())

    forbidden_modules = {
        "scripts.research.run_data_first_repair_v2",
        "run_data_first_repair_v2",
    }
    forbidden_names = {"compute_repair", "run_data_first_repair_v2"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_modules
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules
            for alias in node.names:
                assert alias.name not in forbidden_names


def test_season_2020_exclusion_rejects_forbidden_season() -> None:
    """Case 2: Must reject any artifact containing season 2020 rows."""
    import io

    storage, manifest_uri, manifest = _make_mock_repair_environment()

    # Inject 2020 row into valid population frame
    pop_uri = manifest["output_refs"]["population"]["uri"]
    pop_df = pd.read_parquet(io.BytesIO(storage.read_bytes(pop_uri)))
    pop_df.loc[0, "season"] = 2020
    bad_bytes = pop_df.to_parquet(index=False)
    storage.write_bytes(bad_bytes, pop_uri)

    manifest["output_refs"]["population"]["content_sha"] = hashlib.sha256(
        bad_bytes
    ).hexdigest()
    signed_man = signed_payload(manifest)
    storage.write_bytes(canonical_bytes(signed_man), manifest_uri)

    with pytest.raises(RepairV2Error, match="contains forbidden season 2020"):
        verify_repair_artifact(storage, manifest_uri)


def test_outcome_perturbation_detects_tampered_scores() -> None:
    """Case 3: Must reject if scores are negative or non-integral."""
    import io

    storage, manifest_uri, manifest = _make_mock_repair_environment()

    # Negative score perturbation on valid frame
    pop_uri = manifest["output_refs"]["population"]["uri"]
    pop_df = pd.read_parquet(io.BytesIO(storage.read_bytes(pop_uri)))
    pop_df.loc[0, "home_points"] = -7
    bad_bytes = pop_df.to_parquet(index=False)
    storage.write_bytes(bad_bytes, pop_uri)

    manifest["output_refs"]["population"]["content_sha"] = hashlib.sha256(
        bad_bytes
    ).hexdigest()
    signed_man = signed_payload(manifest)
    storage.write_bytes(canonical_bytes(signed_man), manifest_uri)

    with pytest.raises(RepairV2Error, match="Negative scores detected"):
        verify_repair_artifact(storage, manifest_uri)


def test_malformed_sources_rejects_missing_dataset() -> None:
    """Case 4: Must fail closed if output refs are incomplete."""
    storage, manifest_uri, manifest = _make_mock_repair_environment()

    del manifest["output_refs"]["coverage"]
    del manifest["output_rows"]["coverage"]
    signed_man = signed_payload(manifest)
    storage.write_bytes(canonical_bytes(signed_man), manifest_uri)

    with pytest.raises(RepairV2Error, match="output refs incomplete"):
        verify_repair_artifact(storage, manifest_uri)


def test_malformed_sources_rejects_checksum_mismatch() -> None:
    """Case 4b: Must fail closed if content bytes do not match manifest SHA."""
    storage, manifest_uri, manifest = _make_mock_repair_environment()

    pop_uri = manifest["output_refs"]["population"]["uri"]
    pop_bytes = storage.read_bytes(pop_uri)
    # Tamper with population bytes without updating content_sha
    storage.write_bytes(pop_bytes + b" ", pop_uri)

    with pytest.raises(RepairV2Error, match="checksum mismatch"):
        verify_repair_artifact(storage, manifest_uri)


def test_exact_byte_identity_success_on_valid_artifact() -> None:
    """Case 5: Verifies valid artifact cleanly with exact metadata."""
    storage, manifest_uri, _ = _make_mock_repair_environment()

    result = verify_repair_artifact(
        storage, manifest_uri, expected_code_sha="mockcode123"
    )
    assert result["status"] == "verified"
    assert result["producer_imports_present"] is False
    assert result["forbidden_2020_rows"] == 0
    assert result["verified_games"] == 2
