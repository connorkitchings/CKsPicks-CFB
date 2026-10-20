"""Market-only revision builder: what it may change, what it must refuse.

Fakes stand in for storage, the database and the quote builder; no network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.pipeline import build_market_revision as builder

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "conf/season/2026/revision_manifest_w8_v2.json"
)
CUTOFF = "2026-10-20T14:39:00Z"
LAST_CAPTURE = datetime(2026, 10, 20, 14, 33, 30, tzinfo=timezone.utc)
QUOTES = {
    "uri": "lake/silver/dataset=market_quotes/version=new/data.parquet",
    "sha256": "b" * 64,
}


def source_manifest() -> dict:
    return json.loads(SOURCE.read_text())


def derive(old: dict) -> dict:
    return builder.derive_manifest(
        old,
        revision_id="season-2026-w8-preview-r3",
        quotes_input=QUOTES,
        captured_at="2026-10-20T14:33:30Z",
        target_week="8",
        cutoff=CUTOFF,
    )


def changed_paths(old: dict, new: dict, prefix: str = "") -> set[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        return {
            path
            for key in old.keys() | new.keys()
            for path in changed_paths(old.get(key), new.get(key), f"{prefix}/{key}")
        }
    return set() if old == new else {prefix}


def test_derive_changes_only_quotes_cutoff_and_revision_identity():
    old = source_manifest()
    new = derive(old)

    assert changed_paths(old, new) == {
        "/revision_id",
        "/captured_at",
        "/inputs/market_quotes/uri",
        "/inputs/market_quotes/sha256",
        "/pre_week_cutoffs/8",
    }
    assert new["inputs"]["market_quotes"] == QUOTES
    assert new["pre_week_cutoffs"]["8"] == CUTOFF
    # The source is untouched, so a failed build can never corrupt the certified manifest.
    assert old == source_manifest()


def test_derive_keeps_every_football_input_and_completed_week_cutoff():
    old = source_manifest()
    new = derive(old)

    football = lambda m: {k: v for k, v in m["inputs"].items() if k != "market_quotes"}  # noqa: E731
    assert football(new) == football(old)
    assert new["post_week_cutoffs"] == old["post_week_cutoffs"]
    assert (
        new["score_reconciliation_exceptions"] == old["score_reconciliation_exceptions"]
    )
    assert {k: v for k, v in new["pre_week_cutoffs"].items() if k != "8"} == {
        k: v for k, v in old["pre_week_cutoffs"].items() if k != "8"
    }


@pytest.fixture
def registered(monkeypatch) -> list:
    """Quotes versions the builder registered in the (fake) catalog."""
    calls: list = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setattr(builder, "get_storage", lambda environment: object())
    monkeypatch.setattr(builder, "season_market_capture_ids", lambda *a: ["c1"])
    monkeypatch.setattr(
        builder,
        "build_market_quotes",
        lambda *a, **k: (
            SimpleNamespace(uri=QUOTES["uri"], content_sha=QUOTES["sha256"]),
            {"manifest": True},
        ),
    )
    monkeypatch.setattr(
        builder, "register_dataset_version", lambda *args: calls.append(args)
    )
    return calls


def run_main(monkeypatch, target, *, captured_at=LAST_CAPTURE, week_games=56) -> int:
    schedule = pd.DataFrame({"game_id": range(week_games), "season": 2026, "week": 8})
    monkeypatch.setattr(builder, "frame", lambda store, ref: schedule)
    monkeypatch.setattr(
        builder,
        "market_captures",
        lambda *a: [SimpleNamespace(captured_at=captured_at)],
    )
    return builder.main(
        [
            "--from-manifest", str(SOURCE),
            "--to-manifest", str(target),
            "--revision-id", "season-2026-w8-preview-r3",
            "--cutoff", CUTOFF,
        ]
    )  # fmt: skip


def test_main_writes_the_new_manifest_and_registers_the_quotes_version(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"

    assert run_main(monkeypatch, target) == 0

    assert len(registered) == 1
    written = json.loads(target.read_text())
    assert written["revision_id"] == "season-2026-w8-preview-r3"
    assert written["captured_at"] == "2026-10-20T14:33:30Z"
    assert written["inputs"]["market_quotes"] == QUOTES


def test_main_refuses_to_overwrite_an_existing_manifest(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"
    target.write_text("certified\n")

    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        run_main(monkeypatch, target)

    assert target.read_text() == "certified\n"
    assert registered == []


def test_main_refuses_a_capture_later_than_the_cutoff(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"
    late = datetime(2026, 10, 20, 14, 40, tzinfo=timezone.utc)

    with pytest.raises(SystemExit, match="later than --cutoff"):
        run_main(monkeypatch, target, captured_at=late)

    assert not target.exists()
    assert registered == []


def test_main_refuses_an_incomplete_target_week_schedule(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"

    with pytest.raises(SystemExit, match="is not 56 games"):
        run_main(monkeypatch, target, week_games=55)

    assert not target.exists()
    assert registered == []


def test_main_registers_nothing_when_the_manifest_is_invalid(
    tmp_path, monkeypatch, registered
):
    target = tmp_path / "revision_manifest_w8_v3.json"

    def reject(_manifest):
        raise ValueError("invalid revision")

    monkeypatch.setattr(builder, "validate_revision", reject)

    with pytest.raises(ValueError, match="invalid revision"):
        run_main(monkeypatch, target)

    assert not target.exists()
    assert registered == []
