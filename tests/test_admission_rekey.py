"""Re-keying the pinned admission decisions to provider-keyed ids (contract 2026-10-09/01, 4.5)."""

import json

import pandas as pd
import pytest

from cks_picks_cfb.ratings import admission as adm
from cks_picks_cfb.ratings.admission_rekey import (
    NEW_GROUP_STATUS,
    RekeyError,
    legacy_event_map,
    reconcile_groups,
    recover_first_event,
    rekey_decisions,
    rekey_status,
)
from cks_picks_cfb.ratings.score_envelope_r1 import _group_id

SEASON = 2025


def plays():
    # (drive 19, play 4) is shared by two distinct provider plays; the file lists the
    # overtime play first, so that is the one the legacy build kept.
    return pd.DataFrame(
        {
            "game_id": [7, 7, 7, 7],
            "drive_number": [19, 19, 19, 20],
            "play_number": [4, 4, 5, 1],
            "play_id": [-22488, 401761632104855401, 401761632104855402, 55],
            "period": [5, 4, 4, 4],
        }
    )


def pinned():
    members = ["2025:7:19:4", "2025:7:19:5", "2025:7:20:1"]
    first = "2025:7:19:5"  # the group's first event in ledger order, not string order
    return pd.DataFrame(
        [
            {
                "group_id": _group_id(SEASON, 7, "A", first),
                "season": SEASON,
                "game_id": 7,
                "team": "A",
                "channel": "attribution_only",
                "primary_cause": "final_cap",
                "net_points": 0.0,
                "status": "corroborated",
                "decision": "admitted",
                "evidence_source": "cfbd_drives_5a",
                "event_ids": json.dumps(sorted(members)),
            },
            {
                "group_id": _group_id(SEASON, 8, "B", "2025:8:3:1"),
                "season": SEASON,
                "game_id": 8,
                "team": "B",
                "channel": "points_recovery",
                "primary_cause": "incomplete_stream",
                "net_points": 3.0,
                "status": "game_unusable",
                "decision": "reverted_unverified",
                "evidence_source": "cfbd_drives_5a",
                "event_ids": json.dumps(["2025:8:3:1"]),
            },
        ]
    )


def event_map():
    other = pd.DataFrame(
        {
            "game_id": [8],
            "drive_number": [3],
            "play_number": [1],
            "play_id": [99],
            "period": [1],
        }
    )
    both = pd.concat([plays(), other], ignore_index=True)
    return legacy_event_map(both, SEASON)


def test_the_first_event_is_recovered_by_hashing_not_by_string_order():
    row = pinned().iloc[0]
    members = json.loads(row.event_ids)
    assert members[0] == "2025:7:19:4" != "2025:7:19:5"
    assert recover_first_event(SEASON, 7, "A", row.group_id, members) == "2025:7:19:5"
    with pytest.raises(RekeyError, match="0 members"):
        recover_first_event(SEASON, 7, "A", "deadbeefdeadbeef", members)


def test_a_legacy_event_maps_to_the_play_the_legacy_build_kept_in_file_order():
    mapped = event_map()
    assert mapped["2025:7:19:4"] == "2025:7:-22488"  # file-first, an overtime play
    assert mapped["2025:7:19:5"] == "2025:7:401761632104855402"
    assert "2025:7:401761632104855401" not in mapped.values()  # the dropped twin


def test_rekeyed_decisions_keep_every_pinned_field_and_the_v1_id():
    old = pinned()
    new = rekey_decisions(old, event_map())
    assert (
        list(new.columns).index("group_id_v1")
        == list(old.columns).index("group_id") + 1
    )
    assert set(new["group_id_v1"]) == set(old["group_id"])
    assert new["group_id"].is_unique and not set(new["group_id"]) & set(old["group_id"])
    row = new[new["game_id"] == 7].iloc[0]
    assert json.loads(row.event_ids) == sorted(
        ["2025:7:-22488", "2025:7:401761632104855402", "2025:7:55"]
    )
    assert row.group_id == _group_id(SEASON, 7, "A", "2025:7:401761632104855402")
    for column in ("decision", "status", "net_points", "channel", "primary_cause"):
        assert (
            new.set_index("group_id_v1")[column].to_dict()
            == old.set_index("group_id")[column].to_dict()
        )


def test_an_unmappable_event_is_an_error_not_a_guess():
    broken = pinned()
    broken.loc[0, "event_ids"] = json.dumps(
        ["2025:7:19:4", "2025:7:19:5", "2025:7:99:99"]
    )
    with pytest.raises(RekeyError):
        rekey_decisions(broken, event_map())


def test_status_rows_follow_the_group_id_mapping():
    status = pinned()[["group_id", "season", "game_id", "team", "status"]]
    new = rekey_decisions(pinned(), event_map())
    out = rekey_status(status, dict(zip(new["group_id_v1"], new["group_id"])))
    assert set(out["group_id_v1"]) == set(status["group_id"])
    assert set(out["group_id"]) == set(new["group_id"])


def recomputed_from(rekeyed, drop=(), extra=()):
    rows, members = [], {}
    for r in rekeyed.to_dict("records"):
        if r["group_id"] in drop:
            continue
        rows.append(
            {
                k: r[k]
                for k in (
                    "group_id",
                    "season",
                    "game_id",
                    "team",
                    "channel",
                    "primary_cause",
                    "net_points",
                )
            }
        )
        members[r["group_id"]] = json.loads(r["event_ids"])
    for g, game in extra:
        rows.append(
            {
                "group_id": g,
                "season": SEASON,
                "game_id": game,
                "team": "A",
                "channel": "attribution_only",
                "primary_cause": "other",
                "net_points": 0.0,
            }
        )
        members[g] = ["2025:%d:1" % game]
    return pd.DataFrame(rows), members


def test_matching_groups_reconcile_with_no_problems_and_keep_their_status():
    rekeyed = rekey_decisions(pinned(), event_map())
    recomputed, members = recomputed_from(rekeyed)
    result = reconcile_groups(
        pinned(), rekeyed, recomputed, members, collision_games={7}
    )
    assert result["problems"] == [] and result["matched"] == 2
    assert dict(
        zip(result["final_status"]["group_id"], result["final_status"]["status"])
    ) == dict(zip(rekeyed["group_id"], rekeyed["status"]))


def test_a_difference_outside_the_collision_games_is_a_problem():
    rekeyed = rekey_decisions(pinned(), event_map())
    recomputed, members = recomputed_from(rekeyed)
    members[rekeyed.iloc[0]["group_id"]] = ["2025:7:other"]
    result = reconcile_groups(
        pinned(), rekeyed, recomputed, members, collision_games=set()
    )
    assert any(
        "groups that differ outside the collision games" in p
        for p in result["problems"]
    )


def test_new_groups_in_a_collision_game_fail_closed_and_vanished_ones_are_listed():
    rekeyed = rekey_decisions(pinned(), event_map())
    vanished = rekeyed[rekeyed["game_id"] == 7].iloc[0]["group_id"]
    recomputed, members = recomputed_from(
        rekeyed, drop={vanished}, extra=[("abc123abc123abc1", 7)]
    )
    result = reconcile_groups(
        pinned(), rekeyed, recomputed, members, collision_games={7}
    )
    assert result["problems"] == []
    assert [g["group_id"] for g in result["pinned_only"]] == [vanished]
    assert [g["group_id"] for g in result["recomputed_only"]] == ["abc123abc123abc1"]
    final = result["final_status"].set_index("group_id")["status"]
    assert final["abc123abc123abc1"] == NEW_GROUP_STATUS
    assert (
        adm.decide(NEW_GROUP_STATUS) == adm.REVERTED_UNVERIFIED
    )  # never admitted by default


def test_the_same_differences_outside_a_collision_game_are_problems():
    rekeyed = rekey_decisions(pinned(), event_map())
    recomputed, members = recomputed_from(
        rekeyed, drop={rekeyed.iloc[0]["group_id"]}, extra=[("abc123abc123abc1", 9)]
    )
    result = reconcile_groups(
        pinned(), rekeyed, recomputed, members, collision_games=set()
    )
    assert len(result["problems"]) >= 2
