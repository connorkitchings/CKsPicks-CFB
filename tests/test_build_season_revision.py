"""Weekly season revision builder and explicit market-capture resolution.

Local storage and in-memory captures only; no database or network.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import datetime, timezone

import pandas as pd
import pytest

from cks_picks_cfb.data.lake import DatasetRef, SourceCapture
from cks_picks_cfb.data.storage.local import LocalStorage
from scripts.pipeline import build_season_revision as builder
from scripts.pipeline import build_week_market_snapshot as snapshot

SHA = "a" * 64
GAMES = pd.DataFrame({"game_id": [1, 2], "season": [2026, 2026], "week": [7, 7]})


def ref(dataset: str, version: str) -> DatasetRef:
    return DatasetRef(
        dataset=dataset,
        version_id=version,
        schema_version="v1",
        content_sha=hashlib.sha256(version.encode()).hexdigest(),
        uri=f"lake/silver/dataset={dataset}/version={version}/data.parquet",
    )


def previous_revision() -> dict:
    entry = {"uri": "lake/silver/dataset=x/version=old/data.parquet", "sha256": SHA}
    return {
        "schema_version": "season_revision_v1",
        "season": 2026,
        "revision_id": "season-2026-w7-preview-r1",
        "captured_at": "2026-10-14T14:42:04Z",
        "pre_week_cutoffs": {"6": "2026-10-05T00:00:00Z", "7": "2026-10-13T18:00:00Z"},
        "post_week_cutoffs": {"5": "2026-10-05T00:00:00Z", "6": "2026-10-11T15:00:00Z"},
        "score_reconciliation_exceptions": {
            "uri": "conf/season/2026/score_reconciliation_exceptions.json",
            "sha256": SHA,
        },
        "inputs": {
            name: dict(entry)
            for name in (
                "schedule",
                "finals",
                "byplay",
                "drives",
                "reconciliation",
                "observations",
                "scoring_events",
                "market_quotes",
                "venue_games",
                "venues",
                "teams",
            )
        },
    }


def fresh_refs() -> dict[str, DatasetRef]:
    return {
        name: ref(name, f"{name}-w8")
        for name in (
            "games",
            "game_outcomes",
            "byplay",
            "drives",
            "source_reconciliation",
            "market_quotes",
        )
    }


def market_capture(
    storage: LocalStorage, capture_id: str, captured_at: datetime, rows: list[dict]
) -> SourceCapture:
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_parquet(buffer, index=False)
    raw = buffer.getvalue()
    uri = f"lake/bronze/provider=cfbd/entity=betting_lines/{capture_id}/data.parquet"
    storage.write_bytes(raw, uri)
    return SourceCapture(
        capture_id=capture_id,
        provider="cfbd",
        entity="betting_lines",
        captured_at=captured_at,
        effective_at=None,
        request={},
        content_sha=hashlib.sha256(raw).hexdigest(),
        object_sha=hashlib.sha256(raw).hexdigest(),
        uri=uri,
        row_count=len(rows),
        state="registered",
    )


def line(game_id: int, spread: float, total: float) -> dict:
    return {
        "game_id": game_id,
        "provider": "Bovada",
        "spread": spread,
        "over_under": total,
    }


def test_revision_manifest_fresh_inputs_omits_recomputed_measurements():
    manifest = builder.revision_manifest(
        previous_revision(),
        week=8,
        as_of=datetime(2026, 10, 18, 15, tzinfo=timezone.utc),
        pre_week_cutoff=datetime(2026, 10, 20, 18, tzinfo=timezone.utc),
        captured_at=datetime(2026, 10, 18, 16, 1, 2, tzinfo=timezone.utc),
        refs=fresh_refs(),
    )

    inputs = manifest["inputs"]
    assert manifest["revision_id"] == "season-2026-w8-preview-r1"
    assert manifest["captured_at"] == "2026-10-18T16:01:02Z"
    assert "observations" not in inputs and "scoring_events" not in inputs
    assert inputs["byplay"]["uri"].endswith("version=byplay-w8/data.parquet")
    assert inputs["venue_games"] == inputs["schedule"]
    assert inputs["teams"] == previous_revision()["inputs"]["teams"]
    assert manifest["pre_week_cutoffs"]["8"] == "2026-10-20T18:00:00Z"
    assert manifest["post_week_cutoffs"]["7"] == "2026-10-18T15:00:00Z"
    assert (
        manifest["score_reconciliation_exceptions"]
        == (previous_revision()["score_reconciliation_exceptions"])
    )


def test_revision_manifest_naive_timestamp_raises():
    with pytest.raises(ValueError, match="timezone"):
        builder._utc("2026-10-18T15:00:00")


def test_build_market_quotes_repeated_lines_keeps_every_capture(tmp_path):
    source = LocalStorage(str(tmp_path))
    early = market_capture(
        source,
        "early",
        datetime(2026, 10, 13, 21, tzinfo=timezone.utc),
        [line(1, -3, 50)],
    )
    late = market_capture(
        source,
        "late",
        datetime(2026, 10, 14, 14, tzinfo=timezone.utc),
        [line(1, -3, 50), line(2, 7, 44)],
    )

    quotes_ref, manifest = builder.build_market_quotes(
        source, source, captures=[early, late], games=GAMES, code_sha="test"
    )

    quotes = pd.read_parquet(tmp_path / quotes_ref.uri)
    assert len(quotes) == 3 and quotes.quote_id.is_unique
    game_one = quotes[quotes.game_id.eq(1)].sort_values("captured_at")
    assert game_one["__capture_id"].tolist() == ["early", "late"]
    assert game_one.total.tolist() == [50.0, 50.0]
    assert manifest.source_capture_ids == ("early", "late")
    assert manifest.as_of == "2026-10-14T14:00:00+00:00"


def test_build_market_quotes_same_captures_same_version(tmp_path):
    source = LocalStorage(str(tmp_path))
    captures = [
        market_capture(
            source,
            "only",
            datetime(2026, 10, 14, tzinfo=timezone.utc),
            [line(1, -3, 50)],
        )
    ]

    first, _ = builder.build_market_quotes(
        source, source, captures=captures, games=GAMES, code_sha="test"
    )
    second, _ = builder.build_market_quotes(
        source, source, captures=captures, games=GAMES, code_sha="test"
    )

    assert first == second


def test_build_market_quotes_no_captures_raises(tmp_path):
    source = LocalStorage(str(tmp_path))

    with pytest.raises(LookupError):
        builder.build_market_quotes(
            source, source, captures=[], games=GAMES, code_sha="test"
        )


def test_market_captures_duplicate_ids_resolves_each_once(monkeypatch, tmp_path):
    storage = LocalStorage(str(tmp_path))
    known = {
        name: market_capture(
            storage, name, datetime(2026, 10, 14, tzinfo=timezone.utc), []
        )
        for name in ("a", "b")
    }
    lookups = []
    monkeypatch.setattr(
        snapshot,
        "source_capture_by_id",
        lambda _, capture_id: lookups.append(capture_id) or known[capture_id],
    )

    captures = snapshot.market_captures("conn", ["b", "a", "b"])

    assert [capture.capture_id for capture in captures] == ["b", "a"]
    assert lookups == ["b", "a"]


@pytest.mark.parametrize(
    ("entity", "state"), [("plays", "registered"), ("betting_lines", "staged")]
)
def test_market_captures_non_market_capture_raises(
    monkeypatch, tmp_path, entity, state
):
    storage = LocalStorage(str(tmp_path))
    capture = market_capture(
        storage, "x", datetime(2026, 10, 14, tzinfo=timezone.utc), []
    )
    wrong = SourceCapture(**{**capture.__dict__, "entity": entity, "state": state})
    monkeypatch.setattr(snapshot, "source_capture_by_id", lambda *_: wrong)

    with pytest.raises(ValueError, match="not a registered market capture"):
        snapshot.market_captures("conn", ["x"])


def test_snapshot_cli_explicit_capture_ids_skips_run_lookup(monkeypatch, tmp_path):
    storage = LocalStorage(str(tmp_path))
    capture = market_capture(
        storage,
        "explicit",
        datetime(2026, 10, 14, tzinfo=timezone.utc),
        [line(1, -3, 50)],
    )
    registered = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://preview")
    monkeypatch.setattr(snapshot, "load_dotenv", lambda: None)
    monkeypatch.setattr(snapshot, "get_storage", lambda: storage)
    monkeypatch.setattr(snapshot, "source_capture_by_id", lambda *_: capture)
    monkeypatch.setattr(
        snapshot,
        "run_capture_ids",
        lambda *_: pytest.fail("explicit capture IDs must not query run captures"),
    )
    monkeypatch.setattr(
        snapshot, "register_dataset_version", lambda _, r, __: registered.append(r)
    )
    output = "artifacts/preview/pipeline-runs/w8/market_snapshots_ref.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_week_market_snapshot.py",
            "--year=2026",
            "--week=8",
            "--as-of=2026-10-15T00:00:00Z",
            "--capture-id=explicit",
            f"--output-ref-uri={output}",
        ],
    )

    snapshot.main()

    assert [r.dataset for r in registered] == ["market_quotes", "market_snapshots"]
    assert json.loads(storage.read_bytes(output))["dataset"] == "market_snapshots"


def test_snapshot_cli_without_capture_source_exits(monkeypatch):
    monkeypatch.setattr(snapshot, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_week_market_snapshot.py",
            "--year=2026",
            "--week=8",
            "--as-of=2026-10-15T00:00:00Z",
            "--output-ref-uri=artifacts/x.json",
        ],
    )

    with pytest.raises(SystemExit):
        snapshot.main()


def test_season_revision_dry_run_prints_and_writes_nothing(
    monkeypatch, tmp_path, capsys
):
    conf = tmp_path / "conf/season/2026"
    conf.mkdir(parents=True)
    (conf / "revision_manifest_w7_v1.json").write_text(json.dumps(previous_revision()))
    source = LocalStorage(str(tmp_path))
    seen = {}

    def fake_build_revision(**kwargs):
        seen.update(kwargs)
        manifest = builder.revision_manifest(
            kwargs["previous"],
            week=kwargs["week"],
            as_of=kwargs["as_of"],
            pre_week_cutoff=kwargs["pre_week_cutoff"],
            captured_at=datetime(2026, 10, 18, 16, tzinfo=timezone.utc),
            refs=fresh_refs(),
        )
        return manifest, [(ref("market_quotes", "q"), object())]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PREVIEW_DATABASE_URL", "postgresql://preview")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(builder, "load_dotenv", lambda: None)
    monkeypatch.setattr(builder, "get_storage", lambda **_: source)
    monkeypatch.setattr(builder, "build_revision", fake_build_revision)
    monkeypatch.setattr(
        builder,
        "refresh_controller_silver",
        lambda *_, **__: pytest.fail("dry run must not fetch or build Silver"),
    )
    monkeypatch.setattr(
        builder,
        "register_dataset_version",
        lambda *_: pytest.fail("dry run must not register"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_season_revision.py",
            "--season=2026",
            "--week=8",
            "--environment=preview",
            "--as-of=2026-10-18T15:00:00Z",
            "--pre-week-cutoff=2026-10-20T18:00:00Z",
            "--pipeline-run-id=w7-closeout-r1",
            "--dry-run",
        ],
    )
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    builder.main()

    printed = json.loads(capsys.readouterr().out)
    assert printed["revision_id"] == "season-2026-w8-preview-r1"
    assert seen["sink"] is not source and isinstance(seen["sink"], LocalStorage)
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before
