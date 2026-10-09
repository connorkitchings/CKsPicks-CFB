"""Silver stage helpers: config identity, capture-manifest pin, season guard."""

from __future__ import annotations

import hashlib
import json

import pytest

from cks_picks_cfb.rebuild import silver
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.plan import HISTORICAL_SEASONS


def test_config_sha_changes_with_nullable_ppa():
    on = silver.config_sha()
    off = silver.config_sha({**silver.PIPELINE_CONFIG, "nullable_ppa": False})
    assert on != off
    assert on == silver.config_sha()


def test_capture_manifest_accepts_raw_or_signed_hash_only():
    raw = json.dumps({"manifest_sha256": "a" * 64, "x": 1}).encode()
    silver.check_capture_manifest(raw, hashlib.sha256(raw).hexdigest())
    silver.check_capture_manifest(raw, "a" * 64)
    with pytest.raises(GateError):
        silver.check_capture_manifest(raw, "b" * 64)


def test_season_list_rejects_2020_and_partial_sets():
    assert silver.season_list(HISTORICAL_SEASONS) == list(HISTORICAL_SEASONS)
    with pytest.raises(GateError):
        silver.season_list(HISTORICAL_SEASONS + (2020,))
    with pytest.raises(GateError):
        silver.season_list((2015, 2016))


def _context(version="v", sha="c" * 64):
    from types import SimpleNamespace

    return SimpleNamespace(
        plan=SimpleNamespace(
            policies={"corrections_ref": {"version_id": version, "content_sha": sha}}
        )
    )


def _pin(season=2024, version="v", sha="c" * 64):
    parents = [
        {
            "dataset": name,
            "version_id": f"{name}-v",
            "schema_version": "s",
            "content_sha": "a" * 64,
            "uri": f"lake/silver/{name}",
        }
        for name in silver.PARENT_ORDER
    ] + [
        {
            "dataset": silver.CORRECTIONS_DATASET,
            "version_id": version,
            "schema_version": "s",
            "content_sha": sha,
            "uri": "lake/silver/c",
        }
    ]
    return {
        "schema_version": silver.PIN_SCHEMA,
        "seasons": {str(season): {"parents": parents}},
    }


def test_season_pin_returns_legacy_parent_order_and_checks_corrections():
    entry, refs = silver._season_pin(_context(), _pin(), 2024)
    assert [r.dataset for r in refs] == [*silver.PARENT_ORDER, "data_corrections"]
    with pytest.raises(GateError, match="corrections"):
        silver._season_pin(_context(version="other"), _pin(), 2024)
    with pytest.raises(GateError, match="lacks season"):
        silver._season_pin(_context(), _pin(), 2023)
    with pytest.raises(GateError, match="schema"):
        silver._season_pin(_context(), {**_pin(), "schema_version": "x"}, 2024)
    broken = _pin()
    broken["seasons"]["2024"]["parents"].pop(0)
    with pytest.raises(GateError, match="exactly"):
        silver._season_pin(_context(), broken, 2024)


def test_value_differences_normalize_legacy_nan_strings():
    import pandas as pd

    new = pd.DataFrame(
        {"a": [None, "x", "y"], "ppa": [None, 1.0, None], "extra": [1, 2, 3]}
    )
    legacy = pd.DataFrame({"a": ["nan", "x", "z"], "ppa": [0.0, 1.0, 0.0]})
    assert silver.value_differences(new, legacy) == {"a": 1, "ppa": 2}
    with pytest.raises(GateError):
        silver.value_differences(new, legacy.iloc[:2])


def test_punt_return_fix_accepts_only_the_documented_change():
    import pandas as pd

    legacy = pd.DataFrame(
        {
            "play_type": ["Punt Return", "Rush", "Punt Return"],
            "st": [0, 0, 1],
            "st_punt": [0, 0, 1],
        }
    )
    good = legacy.assign(st=[1, 0, 1], st_punt=[1, 0, 1])
    assert silver.punt_return_fix(good, legacy) == {
        "rows": 1,
        "fits_punt_return_fix": True,
    }
    wrong_type = legacy.assign(st=[0, 1, 1], st_punt=[0, 1, 1])
    assert not silver.punt_return_fix(wrong_type, legacy)["fits_punt_return_fix"]
    reverse = legacy.assign(st=[0, 0, 0], st_punt=[0, 0, 0])
    assert not silver.punt_return_fix(reverse, legacy)["fits_punt_return_fix"]
    assert silver.punt_return_fix(legacy, legacy)["rows"] == 0


# --- provider-keyed play identity (contract 2026-10-09/01) ---------------------------


def _policy_context(**policies):
    from types import SimpleNamespace

    return SimpleNamespace(plan=SimpleNamespace(policies=policies))


def test_play_identity_policy_defaults_to_v1_and_rejects_unknown_values():
    assert silver.identity_of(_policy_context()) == "byplay_v1"
    assert silver.identity_of(_policy_context(play_identity="byplay_v2")) == "byplay_v2"
    with pytest.raises(GateError):
        silver.identity_of(_policy_context(play_identity="byplay_v3"))


def test_v2_registers_beside_v1_without_changing_the_v1_build():
    assert silver.DERIVED["byplay"] == "byplay_v1"
    assert silver.DERIVED["drives"] == "drives_v1"
    assert silver.DERIVED_V2["byplay"] == "byplay_v2"
    assert silver.DERIVED_V2["drives"] == "drives_v2"
    assert (
        silver.DERIVED_V2["reconciled_team_game"]
        == silver.DERIVED["reconciled_team_game"]
    )
    # a v2 build can never share a config identity with a v1 build
    assert silver.config_sha(silver.config_for("byplay_v2")) != silver.config_sha()
    assert silver.config_for("byplay_v1") is silver.PIPELINE_CONFIG


def _legacy_rows():
    import pandas as pd

    return pd.DataFrame(
        {
            "game_id": [9, 9, 9],
            "drive_number": [18, 18, 19],
            "play_number": [1, 2, 1],
            "ppa": [0.0, 0.5, 0.0],
            "drive_id": [40176283118.0, 40176283118.0, None],
        }
    )


def _source_plays():
    import pandas as pd

    # the first play at (18, 1) is the overtime play v1 kept; the regulation play was dropped
    return pd.DataFrame(
        {
            "game_id": [9, 9, 9, 9],
            "drive_number": [18, 18, 18, 19],
            "play_number": [1, 1, 2, 1],
            "play_id": [-22405, 401762831104868701, 401762831104874702, 7],
        }
    )


def test_legacy_rows_map_to_the_source_play_v1_kept():
    keyed = silver.attach_legacy_source_ids(_legacy_rows(), _source_plays())
    assert keyed["source_play_id"].tolist() == ["-22405", "401762831104874702", "7"]


def test_legacy_rows_without_a_source_play_fail():
    plays = _source_plays().iloc[:2]
    with pytest.raises(GateError, match="without a source play"):
        silver.attach_legacy_source_ids(_legacy_rows(), plays)


def test_alignment_reports_one_sided_keys_instead_of_requiring_equal_length():
    import pandas as pd

    legacy = silver.attach_legacy_source_ids(_legacy_rows(), _source_plays())
    new = pd.DataFrame(
        {
            "game_id": [9, 9, 9, 9],
            "source_play_id": [
                "-22405",
                "401762831104868701",
                "401762831104874702",
                "7",
            ],
            "ppa": [0.0, 0.1, 0.5, 0.0],
            "drive_id": ["-2885", "40176283118", "40176283118", "9-19"],
        }
    )
    new_m, legacy_m, only_new, only_legacy = silver.align_on_source_play(new, legacy)
    assert only_new == [[9, "401762831104868701"]]
    assert only_legacy == []
    assert new_m["source_play_id"].tolist() == legacy_m["source_play_id"].tolist()
    assert (
        silver.value_differences(
            new_m.drop(columns="drive_id"), legacy_m.drop(columns="drive_id")
        )
        == {}
    )
    # the retained regulation play is the only difference and is reported by key


def test_alignment_rejects_duplicate_provider_identities():
    import pandas as pd

    frame = pd.DataFrame({"game_id": [9, 9], "source_play_id": ["1", "1"]})
    with pytest.raises(GateError):
        silver.align_on_source_play(frame, frame)


def test_drive_id_differences_separate_mismatches_from_derived_fills():
    import pandas as pd

    legacy = pd.DataFrame({"drive_id": [40176283118.0, None, 5.0]})
    new = pd.DataFrame({"drive_id": ["40176283118", "9-19", "6"]})
    assert silver.drive_id_differences(new, legacy) == {
        "provider_text_mismatches": 1,
        "filled_from_derived": 1,
    }
