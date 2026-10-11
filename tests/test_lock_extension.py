"""Extending the 2026 rebuild source lock by one completed week."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import lock_extension as le

COLUMNS = [
    "week",
    "game_id",
    "start_date",
    "home_team",
    "away_team",
    "home_points",
    "away_points",
]
BASE = {
    "schema_version": "v5_intended_update_2026_source_lock_v1",
    "game_rows_sha256": "f" * 64,
    "games": {
        "columns": COLUMNS,
        "rows": [
            [0, 1, "2026-08-29T16:00:00Z", "A", "B", 10, 7],
            [1, 2, "2026-09-05T16:00:00Z", "C", "D", 21, 14],
            [2, 3, "2026-10-03T16:00:00Z", "E", "F", None, None],
            [2, 4, "2026-10-03T23:00:00Z", "G", "H", None, None],
        ],
    },
    "post_week_cutoffs": {"0": "2026-09-03T04:00:00Z", "1": "2026-09-13T04:00:00Z"},
    "research_2026_prediction_keys": {"completed_games": 2, "week2_games": 2},
}
OUTCOMES = {"dataset": "game_outcomes", "version_id": "v-new", "content_sha": "c" * 64}
CUTOFF = "2026-10-05T00:00:00Z"


def _finals(*rows):
    return pd.DataFrame(rows, columns=["game_id", "home_points", "away_points"])


def _extend(finals, cutoff=CUTOFF, base=BASE):
    return le.extend_lock(
        base,
        base_sha256="a" * 64,
        finals=finals,
        new_cutoff=cutoff,
        outcomes_ref=OUTCOMES,
    )


def test_adds_the_next_cutoff_and_the_new_finals_without_touching_earlier_rows():
    result = _extend(_finals((1, 10, 7), (2, 21, 14), (3, 30, 3), (4, 17, 20)))
    assert result["post_week_cutoffs"]["2"] == CUTOFF
    assert list(result["post_week_cutoffs"]) == ["0", "1", "2"]
    rows = {row[1]: row for row in result["games"]["rows"]}
    assert rows[3][5:] == [30, 3] and rows[4][5:] == [17, 20]
    assert rows[1][5:] == [10, 7] and rows[2][5:] == [21, 14]
    assert result["research_2026_prediction_keys"]["completed_games"] == 4
    ext = result["extends"]
    assert ext["added_post_week"] == 2 and ext["newly_final_game_ids"] == [3, 4]
    assert ext["completed_games_before"] == 2 and ext["completed_games_after"] == 4
    assert ext["base_game_rows_sha256"] == "f" * 64
    assert ext["game_rows_sha256"] == le.rows_sha256(result["games"]["rows"])
    assert (
        result["game_rows_sha256"] == "f" * 64
    )  # the base's own field stays untouched


def test_the_base_lock_is_not_mutated_and_the_result_is_deterministic():
    snapshot = copy.deepcopy(BASE)
    finals = _finals((3, 30, 3), (4, 17, 20))
    first, second = _extend(finals), _extend(finals)
    assert BASE == snapshot
    assert first == second


def test_a_changed_final_score_is_refused_not_overwritten():
    with pytest.raises(le.LockExtensionError, match="game 1"):
        _extend(_finals((1, 11, 7), (3, 30, 3)))


def test_a_final_that_is_not_yet_available_at_the_cutoff_is_refused():
    # Game 4 kicks off 2026-10-03T23:00Z; with a six-hour buffer it is available from 2026-10-04T05:00Z.
    with pytest.raises(le.LockExtensionError, match="not available"):
        _extend(_finals((3, 30, 3), (4, 17, 20)), cutoff="2026-10-04T04:00:00Z")


def test_the_new_cutoff_must_follow_the_last_one_and_there_must_be_something_new():
    with pytest.raises(le.LockExtensionError, match="after the last"):
        _extend(_finals((3, 30, 3)), cutoff="2026-09-13T04:00:00Z")
    with pytest.raises(le.LockExtensionError, match="nothing to extend"):
        _extend(_finals((1, 10, 7)))


def test_non_contiguous_cutoffs_and_repeated_extension_are_refused():
    gap = copy.deepcopy(BASE)
    gap["post_week_cutoffs"] = {
        "0": "2026-09-03T04:00:00Z",
        "2": "2026-09-13T04:00:00Z",
    }
    with pytest.raises(le.LockExtensionError, match="contiguous"):
        _extend(_finals((3, 30, 3)), base=gap)
    once = _extend(_finals((3, 30, 3), (4, 17, 20)))
    with pytest.raises(le.LockExtensionError, match="already an extension"):
        _extend(_finals((3, 30, 3)), base=once, cutoff="2026-10-12T00:00:00Z")


def test_games_without_a_final_stay_unrecorded():
    result = _extend(_finals((3, 30, 3)))
    rows = {row[1]: row for row in result["games"]["rows"]}
    assert rows[4][5:] == [None, None]
    assert result["research_2026_prediction_keys"]["completed_games"] == 3


def _schedule(kickoff_for_3="2026-10-03T16:00:00Z", week_for_3=2):
    return pd.DataFrame(
        {
            "game_id": [1, 2, 3, 4],
            "week": [0, 1, week_for_3, 2],
            "kickoff_utc": [
                "2026-08-29T16:00:00Z",
                "2026-09-05T16:00:00Z",
                kickoff_for_3,
                "2026-10-03T23:00:00Z",
            ],
        }
    )


def _extend_with_schedule(schedule, accepted=()):
    return le.extend_lock(
        BASE,
        base_sha256="a" * 64,
        finals=_finals((3, 30, 3), (4, 17, 20)),
        new_cutoff=CUTOFF,
        outcomes_ref=OUTCOMES,
        schedule=schedule,
        schedule_ref={"version_id": "g1"},
        accepted_kickoff_revisions=accepted,
    )


def test_a_matching_schedule_records_no_revisions():
    result = _extend_with_schedule(_schedule())
    assert result["extends"]["kickoff_revisions"] == []
    assert result["extends"]["schedule_ref"] == {"version_id": "g1"}


def test_an_unaccepted_kickoff_revision_is_refused():
    with pytest.raises(le.LockExtensionError, match="not accepted"):
        _extend_with_schedule(_schedule("2026-10-03T12:00:00Z"))


def test_an_accepted_kickoff_revision_updates_the_row_and_is_recorded():
    result = _extend_with_schedule(_schedule("2026-10-03T12:00:00Z"), accepted=[3])
    row = next(r for r in result["games"]["rows"] if r[1] == 3)
    assert row[2] == "2026-10-03T12:00:00Z"
    assert result["extends"]["kickoff_revisions"] == [
        {
            "game_id": 3,
            "old_start_date": "2026-10-03T16:00:00Z",
            "new_start_date": "2026-10-03T12:00:00Z",
        }
    ]
    assert result["extends"]["game_rows_sha256"] == le.rows_sha256(
        result["games"]["rows"]
    )
    # The shared BASE fixture is not mutated by the revision.
    assert BASE["games"]["rows"][2][2] == "2026-10-03T16:00:00Z"


def test_a_changed_week_is_refused_even_if_the_game_is_accepted():
    with pytest.raises(le.LockExtensionError, match="changed the week"):
        _extend_with_schedule(_schedule(week_for_3=3), accepted=[3])


def test_an_acceptance_without_a_change_is_refused():
    with pytest.raises(le.LockExtensionError, match="without a change"):
        _extend_with_schedule(_schedule(), accepted=[3])


def _append_inputs():
    base = _extend(_finals((3, 30, 3), (4, 17, 20)))
    schedule = pd.DataFrame(base["games"]["rows"], columns=COLUMNS).rename(
        columns={"start_date": "kickoff_utc"}
    )
    new = pd.DataFrame(
        [
            [3, 5, "2026-10-10T16:00:00Z", "I", "J", 14, 21],
            [3, 6, "2026-10-10T23:00:00Z", "K", "L", 30, 24],
        ],
        columns=COLUMNS,
    ).rename(columns={"start_date": "kickoff_utc"})
    schedule = pd.concat([schedule, new], ignore_index=True)
    finals = schedule[["game_id", "home_points", "away_points"]].copy()
    return base, schedule, finals


def _append(base, schedule_input, finals_input, **overrides):
    kwargs = dict(
        base_sha256="a" * 64,
        finals=finals_input,
        schedule=schedule_input,
        schedule_ref={"version_id": "fixture-games", "content_sha": "b" * 64},
        outcomes_ref=OUTCOMES,
        new_cutoff="2026-10-12T14:08:14Z",
        append_week=3,
        expected_games=2,
    )
    kwargs.update(overrides)
    return le.extend_lock(base, **kwargs)


def test_append_preserves_history_metadata_and_binds_checksums():
    base, schedule, finals = _append_inputs()
    snapshot = copy.deepcopy(base)
    result = _append(base, schedule, finals)
    assert base == snapshot
    assert result["games"]["rows"][:4] == base["games"]["rows"]
    assert {
        k: result["post_week_cutoffs"][k] for k in base["post_week_cutoffs"]
    } == base["post_week_cutoffs"]
    ext = result["extends"]
    assert ext["previous_extension"] == base["extends"]
    assert ext["base_lock_sha256"] == "a" * 64
    assert ext["base_game_rows_sha256"] == le.rows_sha256(base["games"]["rows"])
    assert ext["game_rows_sha256"] == le.rows_sha256(result["games"]["rows"])
    assert ext["completed_games_before"] == 4 and ext["completed_games_after"] == 6
    assert ext["newly_final_game_ids"] == [5, 6]
    assert result == _append(base, schedule.iloc[::-1], finals.iloc[::-1])


@pytest.mark.parametrize("frame", ["schedule", "finals"])
@pytest.mark.parametrize(
    "mutation", ["missing_history", "missing_new", "duplicate", "null_id"]
)
def test_append_refuses_missing_and_duplicate_games(frame, mutation):
    base, schedule, finals = _append_inputs()
    inputs = {"schedule": schedule, "finals": finals}
    data = inputs[frame]
    if mutation.startswith("missing"):
        data = data[data.game_id != (1 if mutation == "missing_history" else 5)]
    elif mutation == "duplicate":
        data = pd.concat([data, data.iloc[[-1]]])
    else:
        data = data.copy()
        data.loc[0, "game_id"] = None
    inputs[frame] = data
    with pytest.raises(le.LockExtensionError):
        _append(base, inputs["schedule"], inputs["finals"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("week", 1),
        ("home_team", "changed"),
        ("away_team", "changed"),
        ("kickoff_utc", "2026-08-29T17:00:00Z"),
    ],
)
def test_append_refuses_historical_schedule_drift(field, value):
    base, schedule, finals = _append_inputs()
    schedule.loc[0, field] = value
    with pytest.raises(le.LockExtensionError, match="historical drift"):
        _append(base, schedule, finals)


@pytest.mark.parametrize(
    "index,value", [(0, 11), (4, None), (4, float("inf")), (4, -1), (4, 1.5)]
)
def test_append_refuses_conflicting_or_invalid_finals(index, value):
    base, schedule, finals = _append_inputs()
    finals["home_points"] = finals["home_points"].astype(float)
    finals.loc[index, "home_points"] = value
    with pytest.raises(le.LockExtensionError):
        _append(base, schedule, finals)


@pytest.mark.parametrize(
    "overrides",
    [
        {"append_week": 4},
        {"expected_games": 3},
        {"expected_games": None},
        {"expected_games": 0},
        {"schedule_ref": None},
        {"schedule": None},
        {"accepted_kickoff_revisions": [1]},
        {"new_cutoff": CUTOFF},
        {"new_cutoff": "2026-10-11T04:00:00Z"},
        {"new_cutoff": "invalid"},
        {"new_cutoff": "2026-10-12"},
    ],
)
def test_append_refuses_invalid_scope_or_cutoff(overrides):
    base, schedule, finals = _append_inputs()
    with pytest.raises(le.LockExtensionError):
        _append(base, schedule, finals, **overrides)


def test_append_refuses_checksum_and_population_drift():
    base, schedule, finals = _append_inputs()
    base["extends"]["game_rows_sha256"] = "bad"
    with pytest.raises(le.LockExtensionError, match="checksum"):
        _append(base, schedule, finals)
    base, schedule, finals = _append_inputs()
    extra = schedule.iloc[[0]].copy()
    extra["game_id"] = 99
    with pytest.raises(le.LockExtensionError, match="population"):
        _append(base, pd.concat([schedule, extra]), finals)


def test_append_refuses_uncompleted_game():
    base, schedule, finals = _append_inputs()
    finals["completed"] = True
    finals.loc[4, "completed"] = False
    with pytest.raises(le.LockExtensionError, match="not completed"):
        _append(base, schedule, finals)


@pytest.mark.parametrize("mutation", ["duplicate", "count", "skipped_cutoff"])
def test_append_refuses_corrupt_historical_structure(mutation):
    base, schedule, finals = _append_inputs()
    if mutation == "duplicate":
        base["games"]["rows"].append(base["games"]["rows"][0])
    elif mutation == "count":
        base["research_2026_prediction_keys"]["completed_games"] = 3
    else:
        del base["post_week_cutoffs"]["1"]
    with pytest.raises(le.LockExtensionError):
        _append(base, schedule, finals)


def test_retained_271_plus_58_fixture_and_successor_compatibility():
    # Retained observations are fixtures only: never serialize this candidate.
    from cks_picks_cfb.rebuild.successor_lock import derive_successor_lock

    root = Path(__file__).resolve().parents[1]
    raw = (root / "conf/rebuild/source_lock_2026_w5_v1.json").read_bytes()
    base = json.loads(raw)
    observed = json.loads(
        (
            root
            / "docs/plans/2026-10-11/week6-closeout-evidence/20261011T140813Z/cfbd-games.json"
        ).read_bytes()
    )
    schedule = pd.DataFrame(
        base["games"]["rows"], columns=base["games"]["columns"]
    ).rename(columns={"start_date": "kickoff_utc"})
    new = pd.DataFrame(
        [
            {
                "week": g["week"],
                "game_id": g["id"],
                "kickoff_utc": g["startDate"],
                "home_team": g["homeTeam"],
                "away_team": g["awayTeam"],
                "home_points": g["homePoints"],
                "away_points": g["awayPoints"],
            }
            for g in observed
            if g["completed"]
        ]
    )
    assert len(schedule) == 271 and len(new) == 58
    schedule = pd.concat([schedule, new], ignore_index=True)
    result = _append(
        base,
        schedule,
        schedule[["game_id", "home_points", "away_points"]],
        base_sha256=hashlib.sha256(raw).hexdigest(),
        append_week=6,
        expected_games=58,
    )
    assert len(result["games"]["rows"]) == 329
    assert result["games"]["rows"][:271] == base["games"]["rows"]
    assert result["extends"]["previous_extension"] == base["extends"]
    successor = derive_successor_lock(
        result,
        refs={
            "weeks": {
                str(w): {
                    "as_of": base["market_sources"]
                    .get(str(w), {})
                    .get("as_of", "fixture"),
                    "source_manifest": {"uri": "fixture", "sha256": "fixture"},
                    "market_sources": {"market_quotes": {}, "market_snapshots": {}},
                }
                for w in range(7)
            }
        },
        served_runs={w: {"run_id": f"fixture-{w}"} for w in range(7)},
        week_configs={w: {"path": "fixture", "sha256": "fixture"} for w in range(7)},
        lineage={
            "measurement_parent_sha256": "fixture",
            "rating_parent_sha256": "fixture",
        },
        schedule_content_sha256="fixture",
        schedule_uri="fixture",
    )
    assert successor["game_rows_sha256"] == le.rows_sha256(result["games"]["rows"])
    assert successor["games"] == result["games"]
    assert (
        successor["active_week"]["week"] == 7
    )  # in-memory consumer output, not activation


def test_append_comparison_scope_uses_latest_extension():
    from cks_picks_cfb.rebuild import published_comparison as pc

    result = _append(*_append_inputs())
    scope = pc.lock_scope(result)
    assert pc.game_scope(scope)(pd.DataFrame({"game_id": [3, 4, 5, 6]})).tolist() == [
        False,
        False,
        True,
        True,
    ]
    assert pc.week_scope(scope)(pd.DataFrame({"as_of_week": [3, 4]})).tolist() == [
        False,
        True,
    ]


def _cli_fixture(monkeypatch, tmp_path):
    from scripts.pipeline import extend_rebuild_source_lock as cli

    base, schedule, finals = _append_inputs()
    raw = json.dumps(base).encode()
    base_path = tmp_path / "base.json"
    base_path.write_bytes(raw)
    out = tmp_path / "fixture-output.json"
    argv = [
        "extend",
        "--base-lock",
        str(base_path),
        "--base-sha256",
        hashlib.sha256(raw).hexdigest(),
        "--outcomes-ref-uri",
        "fixture-outcomes",
        "--games-ref-uri",
        "fixture-games",
        "--new-cutoff",
        "2026-10-12T14:08:14Z",
        "--append-week",
        "3",
        "--expected-games",
        "2",
        "--out",
        str(out),
    ]
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli.sys, "argv", argv)
    return cli, schedule, finals, out, argv


def test_cli_append_flags_and_exclusive_fixture_output(monkeypatch, tmp_path):
    from types import SimpleNamespace

    cli, schedule, finals, out, _ = _cli_fixture(monkeypatch, tmp_path)
    finals["season"], finals["completed"] = 2026, True

    def read_ref(uri):
        return json.dumps(
            {
                "dataset": "games" if uri == "fixture-games" else "game_outcomes",
                "version_id": uri,
                "schema_version": "fixture",
                "content_sha": "c" * 64,
                "uri": uri,
            }
        ).encode()

    monkeypatch.setattr(
        cli, "get_storage", lambda **kwargs: SimpleNamespace(read_bytes=read_ref)
    )
    monkeypatch.setattr(
        cli,
        "read_dataset",
        lambda storage, ref: schedule if ref.dataset == "games" else finals,
    )
    assert cli.main() == 0
    result = json.loads(out.read_bytes())
    assert result["extends"]["added_post_week"] == 3
    assert result["extends"]["completed_games_after"] == 6
    assert result["extends"]["schedule_ref"]["version_id"] == "fixture-games"


def test_cli_existing_output_refused_before_storage(monkeypatch, tmp_path):
    cli, _, _, out, _ = _cli_fixture(monkeypatch, tmp_path)
    out.write_text("preserve")

    def forbidden(**kwargs):
        pytest.fail("storage must not be accessed")

    monkeypatch.setattr(cli, "get_storage", forbidden)
    with pytest.raises(SystemExit, match="already exists"):
        cli.main()
    assert out.read_text() == "preserve"


@pytest.mark.parametrize(
    "flag", ["--append-week", "--expected-games", "--games-ref-uri"]
)
def test_cli_requires_paired_append_flags(monkeypatch, tmp_path, flag):
    cli, _, _, _, argv = _cli_fixture(monkeypatch, tmp_path)
    index = argv.index(flag)
    del argv[index : index + 2]
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
