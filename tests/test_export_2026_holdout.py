"""Holdout export: determinism, cutoff safety and analysis-only separation."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.season.manifest import canonical, utc
from tests.season_fixtures import MemoryReader, build_season

SCRIPT = Path(__file__).parents[1] / "scripts/research/export_2026_holdout.py"
spec = importlib.util.spec_from_file_location("export_2026_holdout", SCRIPT)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

MODEL = canonical(
    {"model_id": "m", "inputs": {"priors": {"uri": "p", "sha256": "a" * 64}}}
)


@pytest.fixture(scope="module")
def revision(tmp_path_factory) -> dict:
    revision = copy.deepcopy(
        build_season(tmp_path_factory.mktemp("season"))["revision"]
    )
    # Live manifests carry the next week's cutoff, after their capture time.
    revision["pre_week_cutoffs"]["2"] = "2026-09-13T18:00:00Z"
    return revision


def run(revision: dict, **kwargs) -> bytes:
    manifests = {"w2_v1": canonical(revision)}
    return canonical(export.build_export(manifests, MODEL, **kwargs))


def test_two_runs_produce_identical_bytes(revision):
    assert run(revision) == run(copy.deepcopy(revision))


def test_every_input_is_hash_pinned_with_outcomes_and_lines_marked(revision):
    section = json.loads(run(revision))["manifests"][0]
    roles = {i["name"]: i["role"] for i in section["inputs"]}

    assert roles["finals"] == "outcomes"
    assert roles["market_quotes"] == "early_week_lines"
    assert all(len(i["sha256"]) == 64 and i["uri"] for i in section["inputs"])


def test_no_manifest_is_captured_after_its_cutoff(revision):
    section = json.loads(run(revision))["manifests"][0]

    assert utc(section["captured_at"]) <= max(
        utc(v) for v in section["pre_week_cutoffs"].values()
    )


def test_manifest_captured_after_its_cutoff_is_rejected(revision):
    late = copy.deepcopy(revision)
    late["captured_at"] = "2026-09-14T00:00:00Z"

    with pytest.raises(ValueError, match="after its newest pre-week cutoff"):
        run(late)


def test_quote_stamped_after_capture_is_rejected(revision):
    reader = MemoryReader()
    quotes = pd.DataFrame({"captured_at": ["2026-09-13T12:00:01Z"]})
    late = copy.deepcopy(revision)
    late["inputs"]["market_quotes"] = reader.add("quotes", quotes)

    with pytest.raises(ValueError, match="quote after capture"):
        run(late, reader=reader)


def test_near_kickoff_captures_are_listed_only_as_analysis_only(revision):
    capture = {"capture_id": "c1", "uri": "bronze/nk", "sha256": "b" * 64}
    result = json.loads(run(revision, near_kickoff=[capture]))

    assert result["analysis_only"]["near_kickoff_captures"] == [capture]
    assert all(
        i["uri"] != "bronze/nk" for s in result["manifests"] for i in s["inputs"]
    )


def test_near_kickoff_capture_that_is_a_pinned_input_is_rejected(revision):
    pinned = revision["inputs"]["market_quotes"]["uri"]

    with pytest.raises(ValueError, match="pinned input"):
        run(revision, near_kickoff=[{"capture_id": "c1", "uri": pinned}])
