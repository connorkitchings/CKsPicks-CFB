"""Retrospective-lines revision: pins only the CFBD fallback input, nothing else."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pipeline import build_historical_lines_revision as builder
from scripts.pipeline.build_market_revision import derive_manifest

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "conf/season/2026/revision_manifest_w9_v3.json"
)
LINES = {
    "uri": "lake/silver/dataset=market_quotes/version=hist/data.parquet",
    "sha256": "c" * 64,
}


def derive(old: dict) -> dict:
    return derive_manifest(
        old,
        revision_id="season-2026-w9-preview-r4",
        historical_lines=LINES,
        captured_at=old["captured_at"],
        target_week="9",
        cutoff=old["pre_week_cutoffs"]["9"],
    )


def test_derive_adds_only_historical_lines_and_revision_id():
    old = json.loads(SOURCE.read_text())
    new = derive(old)

    assert new["inputs"]["historical_lines"] == LINES
    assert {k: v for k, v in new["inputs"].items() if k != "historical_lines"} == old[
        "inputs"
    ]
    assert {k: v for k, v in new.items() if k not in {"revision_id", "inputs"}} == {
        k: v for k, v in old.items() if k not in {"revision_id", "inputs"}
    }


def test_select_rows_keeps_named_games_tagged_cfbd():
    records = [{"game_id": 1, "provider": "A"}, {"game_id": 2, "provider": "B"}]

    rows = builder.select_rows(records, {1}, "cap")

    assert rows == [{"game_id": 1, "provider": "A", "source_provider": "cfbd"}]


def test_select_rows_refuses_a_game_the_capture_lacks():
    with pytest.raises(ValueError, match=r"no lines for games \[3\]"):
        builder.select_rows([{"game_id": 1}], {1, 3}, "cap")
