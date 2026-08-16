import hashlib
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    MarketQuote,
    build_dataset_version,
    canonicalize_market_quotes_frame,
    capture_provider_records,
    read_dataset,
    select_capture_as_of,
    select_market_snapshot,
)
from cks_picks_cfb.data.storage import LocalStorage, StorageError


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
