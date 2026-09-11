import hashlib
import io
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    MarketQuote,
    PartitionedDatasetPart,
    PartitionedDatasetWriter,
    build_dataset_version,
    canonicalize_market_quotes_frame,
    capture_provider_records,
    iter_partitioned_dataset,
    parquet_bytes,
    read_dataset,
    select_capture_as_of,
    select_market_snapshot,
)
from cks_picks_cfb.data.storage import LocalStorage, StorageError


def _phase3_population_frame(season: int = 2025) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": season,
                "week": 1,
                "game_id": season,
                "kickoff_utc": "2025-09-01T12:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
                "home_points": 21,
                "away_points": 14,
                "forecast_eligible": True,
                "measurement_usable": True,
                "missing_reason": None,
                "timing_class": "historically_reconstructed",
                "outer_validation": True,
            }
        ]
    )


def _phase3_attribution_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate": "prior_only",
                "components": "core",
                "component_count": 1,
                "validation_rows": 10,
                "validation_games": 2,
                "pooled_mae": 15.0,
                "baseline_mae": 16.0,
                "improvement_pct": 6.25,
                "bootstrap_mean_improvement": 1.0,
                "bootstrap_90_lower": 0.5,
                "bootstrap_90_upper": 1.5,
                "bootstrap_excludes_zero": True,
                "coverage_equal": True,
                "maximum_seasonal_regression_pct": 1.0,
                "seasonal_gate_passed": True,
                "sensitivity_mae": 15.5,
                "sensitivity_baseline_mae": 16.0,
                "sensitivity_regression_pct": 3.1,
                "sensitivity_gate_passed": True,
                "primary_gate_passed": True,
                "selected": False,
            }
        ]
    )


def test_parquet_bytes_preserves_nullable_boolean_values() -> None:
    payload = parquet_bytes([{"flag": True}, {"flag": False}, {"flag": None}])
    values = pd.read_parquet(io.BytesIO(payload))["flag"].tolist()
    assert values[:2] == [True, False]
    assert pd.isna(values[2])


def test_parquet_bytes_preserves_missing_object_values_as_null() -> None:
    payload = parquet_bytes([{"value": "present"}, {"value": float("nan")}])
    values = pd.read_parquet(io.BytesIO(payload))["value"].tolist()
    assert values[0] == "present"
    assert pd.isna(values[1])


def test_identical_capture_reuses_content_and_preserves_observations(tmp_path):
    storage = LocalStorage(tmp_path)
    now = datetime.now(timezone.utc)
    first = capture_provider_records(
        storage,
        provider="cfbd",
        entity="games",
        records=[{"id": 1, "week": 1}],
        captured_at=now,
        effective_at=None,
        request={"year": 2026},
        capture_id="capture-1",
    )
    second = capture_provider_records(
        storage,
        provider="cfbd",
        entity="games",
        records=[{"id": 1, "week": 1}],
        captured_at=now + timedelta(minutes=1),
        effective_at=None,
        request={"year": 2026},
        capture_id="capture-2",
    )
    assert first.content_sha == second.content_sha
    assert first.uri == second.uri
    observations = storage.list_files(first.uri.rsplit("/", 1)[0] + "/observations")
    assert len(observations) == 2


def test_capture_reuses_existing_observation_when_parquet_is_reserialized(tmp_path):
    storage = LocalStorage(tmp_path)
    now = datetime.now(timezone.utc)
    first = capture_provider_records(
        storage,
        provider="cfbd",
        entity="games",
        records=[{"id": 1, "week": 1}],
        captured_at=now,
        effective_at=None,
        request={"year": 2026},
        capture_id="capture-1",
    )
    buffer = io.BytesIO()
    pd.DataFrame([{"id": 1, "week": 1}]).to_parquet(buffer, compression="gzip")
    storage.write_bytes(buffer.getvalue(), first.uri)

    repeated = capture_provider_records(
        storage,
        provider="cfbd",
        entity="games",
        records=[{"id": 1, "week": 1}],
        captured_at=now,
        effective_at=None,
        request={"year": 2026},
        capture_id="capture-1",
    )

    assert repeated.object_sha != first.object_sha
    assert repeated.object_sha == hashlib.sha256(buffer.getvalue()).hexdigest()


def test_capture_reuses_existing_content_addressed_parquet_after_reserialization(
    tmp_path,
):
    storage = LocalStorage(tmp_path)
    now = datetime.now(timezone.utc)
    first = capture_provider_records(
        storage,
        provider="cfbd",
        entity="games",
        records=[{"id": 1, "week": 1}],
        captured_at=now,
        effective_at=None,
        request={"year": 2026},
        capture_id="capture-1",
    )
    buffer = io.BytesIO()
    pd.DataFrame([{"id": 1, "week": 1}]).to_parquet(buffer, compression="gzip")
    storage.write_bytes(buffer.getvalue(), first.uri)

    second = capture_provider_records(
        storage,
        provider="cfbd",
        entity="games",
        records=[{"id": 1, "week": 1}],
        captured_at=now + timedelta(minutes=1),
        effective_at=None,
        request={"year": 2026},
        capture_id="capture-2",
    )

    assert second.uri == first.uri
    observations = storage.list_files(first.uri.rsplit("/", 1)[0] + "/observations")
    assert len(observations) == 2


def test_as_of_never_selects_future_capture(tmp_path):
    storage = LocalStorage(tmp_path)
    now = datetime.now(timezone.utc)
    captures = [
        capture_provider_records(
            storage,
            provider="cfbd",
            entity="games",
            records=[{"id": index}],
            captured_at=now + timedelta(hours=index),
            effective_at=None,
            request={},
            capture_id=f"capture-{index}",
        )
        for index in range(3)
    ]
    selected = select_capture_as_of(captures, now + timedelta(hours=1, minutes=30))
    assert selected.capture_id == "capture-1"


def test_dataset_ref_is_checksum_verified(tmp_path):
    storage = LocalStorage(tmp_path)
    parent = DatasetRef("schedule", "v1", "1", "a" * 64, "unused")
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="matchup_features",
            parent_refs=(parent,),
            code_sha="code",
            config_sha="config",
            as_of=datetime.now(timezone.utc),
            tier="gold",
        ),
        records=[{"game_id": 1, "feature": 2.0}],
    )
    assert manifest.parent_versions == ("v1",)
    assert read_dataset(storage, ref).to_dict("records") == [
        {"game_id": 1, "feature": 2.0}
    ]
    same_ref, same_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="matchup_features",
            parent_refs=(parent,),
            code_sha="code",
            config_sha="config",
            as_of=datetime.fromisoformat(manifest.as_of),
            tier="gold",
        ),
        records=[{"game_id": 1, "feature": 2.0}],
    )
    assert same_ref == ref
    assert same_manifest.created_at == manifest.created_at
    storage.write_bytes(b"corrupt", ref.uri)
    with pytest.raises(StorageError, match="checksum mismatch"):
        read_dataset(storage, ref)


def test_v2_dataset_identity_includes_cutoff_and_partitions(tmp_path):
    storage = LocalStorage(tmp_path)
    parent = DatasetRef("schedule", "v1", "1", "a" * 64, "unused")
    first, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="matchup_features",
            parent_refs=(parent,),
            code_sha="code",
            config_sha="config",
            as_of=datetime(2026, 8, 1, tzinfo=timezone.utc),
            tier="gold",
        ),
        records=[{"game_id": 1, "feature": 2.0}],
        partitions={"seasons": [2026]},
    )
    later, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="matchup_features",
            parent_refs=(parent,),
            code_sha="code",
            config_sha="config",
            as_of=datetime(2026, 8, 2, tzinfo=timezone.utc),
            tier="gold",
        ),
        records=[{"game_id": 1, "feature": 2.0}],
        partitions={"seasons": [2026]},
    )
    other_partition, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="matchup_features",
            parent_refs=(parent,),
            code_sha="code",
            config_sha="config",
            as_of=datetime(2026, 8, 1, tzinfo=timezone.utc),
            tier="gold",
        ),
        records=[{"game_id": 1, "feature": 2.0}],
        partitions={"seasons": [2025]},
    )
    assert len({first.version_id, later.version_id, other_partition.version_id}) == 3


def test_v2_dataset_identity_reuses_numpy_scalar_partitions(tmp_path):
    storage = LocalStorage(tmp_path)
    parent = DatasetRef("schedule", "v1", "1", "a" * 64, "unused")
    week = pd.Series([1], dtype="int64").iloc[0]
    build = BuildRequest(
        dataset="matchup_features",
        parent_refs=(parent,),
        code_sha="code",
        config_sha="config",
        as_of=datetime(2026, 8, 1, tzinfo=timezone.utc),
        tier="gold",
    )
    first, first_manifest = build_dataset_version(
        storage,
        build=build,
        records=[{"game_id": 1, "feature": 2.0}],
        partitions={"week": [week]},
    )
    repeated, repeated_manifest = build_dataset_version(
        storage,
        build=build,
        records=[{"game_id": 1, "feature": 2.0}],
        partitions={"week": [week]},
    )
    assert repeated == first
    assert repeated_manifest.created_at == first_manifest.created_at


def test_failed_v2_validation_does_not_write_canonical_dataset(tmp_path):
    storage = LocalStorage(tmp_path)
    with pytest.raises(StorageError, match="validation failed"):
        build_dataset_version(
            storage,
            build=BuildRequest(
                dataset="matchup_features",
                parent_refs=(),
                code_sha="code",
                config_sha="config",
                as_of=datetime.now(timezone.utc),
                tier="gold",
            ),
            records=[{"game_id": 1}],
            validation={"valid": False},
        )
    assert storage.list_files("lake/") == []


def test_partitioned_dataset_streams_ordered_immutable_parts(tmp_path):
    storage = LocalStorage(tmp_path)
    build = BuildRequest(
        dataset="phase3_population",
        parent_refs=(),
        code_sha="code",
        config_sha="config",
        as_of=datetime(2026, 9, 10, tzinfo=timezone.utc),
        schema_version="data_first_phase3_population_v2",
        tier="gold",
    )
    writer = PartitionedDatasetWriter(storage, build=build, partition_keys=("season",))
    writer.add(
        PartitionedDatasetPart(
            {"season": 2023}, _phase3_population_frame(2023).iloc[:0]
        )
    )
    writer.add(PartitionedDatasetPart({"season": 2024}, _phase3_population_frame(2024)))
    writer.add(PartitionedDatasetPart({"season": 2025}, _phase3_population_frame(2025)))
    ref = writer.finish()
    assert ref.row_count == 2
    assert [
        int(frame.iloc[0]["season"]) for frame in iter_partitioned_dataset(storage, ref)
    ] == [2024, 2025]

    repeated = PartitionedDatasetWriter(
        storage, build=build, partition_keys=("season",)
    )
    repeated.add(
        PartitionedDatasetPart(
            {"season": 2023}, _phase3_population_frame(2023).iloc[:0]
        )
    )
    repeated.add(
        PartitionedDatasetPart({"season": 2024}, _phase3_population_frame(2024))
    )
    repeated.add(
        PartitionedDatasetPart({"season": 2025}, _phase3_population_frame(2025))
    )
    assert repeated.finish() == ref


def test_partitioned_dataset_orders_numeric_partition_values_naturally(tmp_path):
    storage = LocalStorage(tmp_path)
    build = BuildRequest(
        dataset="phase3_population",
        parent_refs=(),
        code_sha="code",
        config_sha="config",
        as_of=datetime(2026, 9, 10, tzinfo=timezone.utc),
        schema_version="data_first_phase3_population_v2",
        tier="gold",
    )
    writer = PartitionedDatasetWriter(
        storage,
        build=build,
        partition_keys=("season", "week"),
        row_partition_keys=("season",),
    )
    for week in (1, 2, 10):
        writer.add(
            PartitionedDatasetPart(
                {"season": 2025, "week": week}, _phase3_population_frame()
            )
        )
    ref = writer.finish()
    manifest = json.loads(storage.read_bytes(ref.uri))
    assert [part["partition"]["week"] for part in manifest["parts"]] == [1, 2, 10]


def test_partitioned_dataset_rejects_malformed_or_corrupt_parts(tmp_path):
    storage = LocalStorage(tmp_path)
    build = BuildRequest(
        dataset="phase3_population",
        parent_refs=(),
        code_sha="code",
        config_sha="config",
        as_of=datetime(2026, 9, 10, tzinfo=timezone.utc),
        schema_version="data_first_phase3_population_v2",
        tier="gold",
    )
    writer = PartitionedDatasetWriter(storage, build=build, partition_keys=("season",))
    with pytest.raises(StorageError, match="partition keys"):
        writer.add(PartitionedDatasetPart({"week": 1}, _phase3_population_frame()))
    writer.add(PartitionedDatasetPart({"season": 2025}, _phase3_population_frame()))
    ref = writer.finish()
    child = next(
        path for path in storage.list_files("lake/") if path.endswith("data.parquet")
    )
    storage.write_bytes(b"corrupt", child)
    with pytest.raises(StorageError, match="checksum mismatch"):
        list(iter_partitioned_dataset(storage, ref))


def test_partitioned_dataset_supports_logical_only_partitions(tmp_path):
    storage = LocalStorage(tmp_path)
    build = BuildRequest(
        dataset="phase3_attribution",
        parent_refs=(),
        code_sha="code",
        config_sha="config",
        as_of=datetime(2026, 9, 10, tzinfo=timezone.utc),
        schema_version="data_first_phase3_attribution_v2",
        tier="gold",
    )
    writer = PartitionedDatasetWriter(
        storage,
        build=build,
        partition_keys=("scope",),
        row_partition_keys=(),
    )
    frame = _phase3_attribution_frame()
    assert "scope" not in frame.columns
    writer.add(PartitionedDatasetPart({"scope": "all"}, frame))
    ref = writer.finish()
    manifest = json.loads(storage.read_bytes(ref.uri))
    assert manifest["row_partition_keys"] == []
    frames = list(iter_partitioned_dataset(storage, ref))
    assert [len(part) for part in frames] == [1]
    assert frames[0]["candidate"].tolist() == ["prior_only"]

    repeated = PartitionedDatasetWriter(
        storage,
        build=build,
        partition_keys=("scope",),
        row_partition_keys=(),
    )
    repeated.add(PartitionedDatasetPart({"scope": "all"}, _phase3_attribution_frame()))
    assert repeated.finish() == ref


def test_partitioned_dataset_binds_rows_to_declared_partition_columns(tmp_path):
    storage = LocalStorage(tmp_path)
    build = BuildRequest(
        dataset="phase3_population",
        parent_refs=(),
        code_sha="code",
        config_sha="config",
        as_of=datetime(2026, 9, 10, tzinfo=timezone.utc),
        schema_version="data_first_phase3_population_v2",
        tier="gold",
    )
    writer = PartitionedDatasetWriter(
        storage,
        build=build,
        partition_keys=("season",),
        row_partition_keys=("season",),
    )
    with pytest.raises(StorageError, match="rows escape partition"):
        writer.add(
            PartitionedDatasetPart({"season": 2025}, _phase3_population_frame(2024))
        )


def test_consensus_then_median_is_independent_by_target():
    now = datetime.now(timezone.utc)
    quotes = [
        MarketQuote("a", 1, "Book A", now, spread=-3.0, total=50.0),
        MarketQuote("b", 1, "Book B", now, spread=-5.0, total=54.0),
        MarketQuote("c", 1, "Consensus", now, spread=-4.5, total=None),
    ]
    snapshot = select_market_snapshot(quotes, game_id=1, as_of=now)
    assert snapshot.spread == -4.5
    assert snapshot.spread_rule == "cfbd_consensus"
    assert snapshot.total == 52.0
    assert snapshot.total_rule == "provider_median"

    frame = canonicalize_market_quotes_frame(
        pd.DataFrame(
            [
                {"game_id": 1, "provider": "Book A", "spread": -3, "over_under": 50},
                {"game_id": 1, "provider": "Book B", "spread": -5, "over_under": 54},
                {
                    "game_id": 1,
                    "provider": "Consensus",
                    "spread": -4.5,
                    "over_under": None,
                },
            ]
        )
    )
    assert frame.iloc[0]["spread_line"] == -4.5
    assert frame.iloc[0]["total_line"] == 52.0
