import pandas as pd
import pytest

from cks_picks_cfb.data.history import (
    import_historical_object,
    inventory_historical_source,
    inventory_report,
    read_historical_records,
    validate_historical_scope,
)
from cks_picks_cfb.data.storage import LocalStorage, ReadOnlyStorage


class ListingOnlyStorage(ReadOnlyStorage):
    """Prove inventory uses listing metadata and never per-object metadata calls."""

    def object_metadata(self, path):
        raise AssertionError(f"unexpected HEAD-equivalent lookup: {path}")


def test_inventory_classifies_legacy_and_native_objects_without_writing(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    writable = LocalStorage(source_root)
    writable.write_parquet(
        pd.DataFrame([{"season": 2025, "game_id": 1}]),
        "raw/games/year=2025/data.parquet",
    )
    writable.write_parquet(
        pd.DataFrame([{"season": 2020, "game_id": 2}]),
        "raw/games/year=2020/data.parquet",
    )
    source = ReadOnlyStorage(writable)

    objects = inventory_historical_source(source)
    report = inventory_report(objects)

    assert len(objects) == 2
    assert objects[0].provider == "legacy_cfbd_export"
    assert report["years"] == [2020, 2025]
    assert report["forbidden_2020_objects"] == ["raw/games/year=2020/data.parquet"]


def test_inventory_reuses_metadata_from_listing(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    writable = LocalStorage(source_root)
    writable.write_parquet(
        pd.DataFrame([{"season": 2025, "game_id": 1}]),
        "raw/games/year=2025/data.parquet",
    )

    objects = inventory_historical_source(ListingOnlyStorage(writable))

    assert len(objects) == 1
    assert objects[0].metadata["size"] > 0


def test_scope_rejects_2020_and_labeled_2019(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    writable = LocalStorage(source_root)
    writable.write_parquet(
        pd.DataFrame([{"season": 2020, "game_id": 1}]),
        "raw/games/year=2020/data.parquet",
    )
    writable.write_parquet(
        pd.DataFrame([{"season": 2019, "game_id": 2}]),
        "raw/plays/year=2019/data.parquet",
    )
    objects = inventory_historical_source(ReadOnlyStorage(writable))
    for item in objects:
        records, _ = read_historical_records(ReadOnlyStorage(writable), item)
        with pytest.raises(ValueError):
            validate_historical_scope(item, records)


def test_import_is_idempotent_and_records_source_provenance(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    destination_root = tmp_path / "preview"
    source_root.mkdir()
    destination_root.mkdir()
    source_backend = LocalStorage(source_root)
    source_backend.write_parquet(
        pd.DataFrame([{"season": 2025, "game_id": 1}]),
        "raw/games/year=2025/data.parquet",
    )
    source = ReadOnlyStorage(source_backend)
    destination = LocalStorage(destination_root)
    item = inventory_historical_source(source)[0]
    registered = []
    monkeypatch.setattr(
        "cks_picks_cfb.data.history.begin_ingestion_run", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.history.finish_ingestion_run", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.history.register_source_capture",
        lambda _url, capture, **_kwargs: registered.append(capture),
    )

    first = import_historical_object(
        source=source,
        destination=destination,
        conn_url="postgresql://unused",
        item=item,
    )
    second = import_historical_object(
        source=source,
        destination=destination,
        conn_url="postgresql://unused",
        item=item,
    )

    assert first.capture_id == second.capture_id
    assert first.content_sha == second.content_sha
    assert first.provider == "legacy_cfbd_export"
    assert first.response_metadata["source_sha256"]
    assert len(registered) == 2


def test_dataset_provider_routing_separates_canonical_and_legacy():
    """Canonical market builds must only consume native captures;
    legacy_market_references must only consume legacy captures."""
    from cks_picks_cfb.data.silver import DATASET_PROVIDERS

    assert DATASET_PROVIDERS["market_quotes"] == ("cfbd",)
    assert DATASET_PROVIDERS["market_snapshots"] == ("cfbd",)
    assert DATASET_PROVIDERS["legacy_market_references"] == ("legacy_cfbd_export",)
    assert DATASET_PROVIDERS.get("games") is None
    assert DATASET_PROVIDERS.get("plays") is None
