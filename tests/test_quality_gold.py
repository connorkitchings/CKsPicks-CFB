"""Gold gates reject missing and numerically contradictory measurements."""

from test_gold_contracts import _frame, _metric_row

from cks_picks_cfb.quality.checks import run_stage
from cks_picks_cfb.quality.gold import metric_semantics


def test_missing_gold_inputs_fail_but_only_block_when_promoted():
    report = run_stage("gold", {})
    assert not report.blocked
    assert all(not row.passed and not row.skipped for row in report.results)
    promoted = run_stage("gold", {}, required_checks=("gold.schema_contract",))
    assert promoted.blocked


def test_gold_metric_semantics_checks_values_and_mirrors():
    frame = _frame(_metric_row(), _metric_row(role="defense", team="B", opponent="A"))
    assert metric_semantics({"team_game_metrics": frame}).passed
    frame.loc[0, "value"] = 99.0
    assert not metric_semantics({"team_game_metrics": frame}).passed


def test_partitioned_gold_reader_verifies_root_and_parts(tmp_path):
    from dataclasses import replace
    from datetime import datetime, timezone

    import pytest
    from test_data_lake import _phase3_population_frame

    from cks_picks_cfb.data.lake import (
        BuildRequest,
        DatasetRef,
        PartitionedDatasetPart,
        PartitionedDatasetWriter,
    )
    from cks_picks_cfb.data.storage import LocalStorage, StorageError
    from cks_picks_cfb.quality.loaders import read_quality_dataset

    storage = LocalStorage(tmp_path)
    writer = PartitionedDatasetWriter(
        storage,
        build=BuildRequest(
            dataset="phase3_population",
            parent_refs=(),
            code_sha="test",
            config_sha="test",
            as_of=datetime(2026, 9, 10, tzinfo=timezone.utc),
            schema_version="data_first_phase3_population_v2",
            tier="gold",
        ),
        partition_keys=("season",),
    )
    for season in (2024, 2025):
        writer.add(
            PartitionedDatasetPart({"season": season}, _phase3_population_frame(season))
        )
    root = writer.finish()
    ref = DatasetRef(
        root.dataset, root.version_id, root.schema_version, root.content_sha, root.uri
    )
    assert list(read_quality_dataset(storage, ref).season) == [2024, 2025]
    with pytest.raises(ValueError, match="checksum"):
        read_quality_dataset(storage, replace(ref, content_sha="0" * 64))
    with pytest.raises(ValueError, match="identity"):
        read_quality_dataset(storage, replace(ref, version_id="wrong"))
    import json

    manifest = json.loads(storage.read_bytes(root.uri))
    storage.write_bytes(b"corrupted", manifest["parts"][0]["ref"]["uri"])
    with pytest.raises(StorageError, match="checksum"):
        read_quality_dataset(storage, ref)
