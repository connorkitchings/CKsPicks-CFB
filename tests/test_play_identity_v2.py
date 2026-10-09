"""byplay_v2 / drives_v2: provider-keyed play identity (contract 2026-10-09/01, Task 2)."""

import io

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.lake import BuildRequest, DatasetRef, build_dataset_version
from cks_picks_cfb.data.play_identity import (
    PlayIdentityError,
    deduplicate_source_plays,
    derived_drive_ambiguity,
    lineage_problem,
    provider_drive_ids,
    require_v2_byplay,
    source_id_strings,
)
from cks_picks_cfb.data.schema_contracts import (
    DatasetSchemaError,
    schema_for,
    validate_frame,
)
from cks_picks_cfb.data.silver.contracts import (
    SILVER_CONTRACTS,
    SilverValidationError,
    silver_contract,
)
from cks_picks_cfb.data.storage import StorageError
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.features.byplay.enrichment import allplays_to_byplay
from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline

REGULATION_ID = 401762831104868701
OVERTIME_ID = -22405
#: Published schema identities of the superseded v1 contracts; they must never move.
BYPLAY_V1_SHA = "daf7cbd977cb666606afaf28e7757125f954685fb0f550bb3a55020ff9772ae8"
DRIVES_V1_SHA = "a1400b6ad766272bb4b2644af3408f769753de2025d52e002bc8d1cc7e811473"


def play(**overrides) -> dict:
    row = {
        "season": 2025,
        "week": 6,
        "game_id": 9,
        "offense": "Buffalo",
        "defense": "Eastern Michigan",
        "play_number": 1,
        "drive_number": 18,
        "quarter": 4,
        "down": 1,
        "yards_to_first": 10,
        "yards_to_goal": 70,
        "yards_gained": 5,
        "yard_line": 30,
        "adj_yd_line": 70,
        "offense_score": 0,
        "defense_score": 0,
        "play_type": "Rush",
        "play_text": "",
        "ppa": 0.1,
        "scoring": 0,
        "turnover": 0,
        "penalty": 0,
        "offense_timeouts": 3,
        "defense_timeouts": 3,
        "play_id": REGULATION_ID,
        "drive_id": 40176283118,
    }
    row.update(overrides)
    return row


def cross_period_collision() -> pd.DataFrame:
    """A regulation play and an overtime play that share drive 18, play 1."""
    return pd.DataFrame(
        [
            play(),
            play(
                offense="Eastern Michigan",
                defense="Buffalo",
                quarter=5,
                play_id=OVERTIME_ID,
                drive_id=-2885,
                ppa=-0.45,
            ),
        ]
    )


# --- strict identifier strings -------------------------------------------------------


def test_source_ids_round_trip_negative_and_eighteen_digit_values_exactly():
    series = pd.Series([OVERTIME_ID, REGULATION_ID], dtype="int64")
    assert source_id_strings(series, label="x").tolist() == [
        "-22405",
        "401762831104868701",
    ]
    text = pd.Series([" -22405 ", "0401762831104868701"], dtype=object)
    assert source_id_strings(text, label="x").tolist() == [
        "-22405",
        "401762831104868701",
    ]


@pytest.mark.parametrize(
    "values",
    [
        pd.Series([1.0, 2.0]),
        pd.Series([1, 2.5], dtype=object),
        pd.Series(["12.0"], dtype=object),
        pd.Series(["abc"], dtype=object),
        pd.Series([True], dtype=object),
        pd.Series([1, None], dtype="Int64"),
    ],
)
def test_source_ids_reject_floats_text_and_missing(values):
    with pytest.raises(PlayIdentityError):
        source_id_strings(values, label="source_play_id")


def test_drive_ids_accept_only_exactly_representable_floats():
    promoted = pd.Series([40176283118.0, np.nan])
    got = source_id_strings(
        promoted, label="drive_id", allow_missing=True, allow_exact_float=True
    )
    assert got.iloc[0] == "40176283118" and pd.isna(got.iloc[1])
    with pytest.raises(PlayIdentityError):
        source_id_strings(
            pd.Series([float(REGULATION_ID)]),
            label="drive_id",
            allow_exact_float=True,
        )


# --- dedup ---------------------------------------------------------------------------


def test_exact_repeats_collapse_ignoring_capture_metadata():
    base = play(__capture_id="first")
    frame = pd.DataFrame([base, {**base, "__capture_id": "retry"}])
    assert len(deduplicate_source_plays(frame)) == 1


def test_divergent_versions_of_one_provider_play_block():
    frame = pd.DataFrame([play(ppa=0.1), play(ppa=0.2)])
    with pytest.raises(PlayIdentityError, match="divergent versions"):
        deduplicate_source_plays(frame)


def test_distinct_provider_ids_at_one_sequence_are_all_kept():
    kept = deduplicate_source_plays(cross_period_collision())
    assert kept["source_play_id"].tolist() == ["401762831104868701", "-22405"]


def test_dedup_requires_a_provider_id_on_every_row():
    with pytest.raises(PlayIdentityError):
        deduplicate_source_plays(pd.DataFrame([play(), play(play_id=None)]))
    with pytest.raises(PlayIdentityError, match="lack a provider play ID"):
        deduplicate_source_plays(pd.DataFrame([play()]).drop(columns="play_id"))


# --- schema registry -----------------------------------------------------------------


def test_v1_schema_identities_do_not_move():
    assert schema_for("byplay", "byplay_v1").sha256 == BYPLAY_V1_SHA
    assert schema_for("drives", "drives_v1").sha256 == DRIVES_V1_SHA


def test_v2_schemas_are_registered_beside_v1():
    byplay = schema_for("byplay", "byplay_v2")
    drives = schema_for("drives", "drives_v2")
    assert byplay.keys == ("season", "game_id", "source_play_id")
    assert drives.keys == ("season", "game_id", "drive_id", "offense", "defense")
    assert byplay.sha256 != BYPLAY_V1_SHA
    assert schema_for("byplay", "byplay_v1").schema_version == "byplay_v1"
    with pytest.raises(DatasetSchemaError, match="byplay_v1 or byplay_v2"):
        schema_for("byplay", "byplay_v3")
    with pytest.raises(DatasetSchemaError):
        schema_for("drives", "byplay_v2")


def test_silver_contract_revisions_keep_v1_selectable():
    assert silver_contract("byplay", "byplay_v1") is SILVER_CONTRACTS["byplay"]
    v2 = silver_contract("byplay", "byplay_v2")
    assert v2.key_columns == ("season", "game_id", "source_play_id")
    assert "source_play_id" in v2.required_columns
    assert silver_contract("drives", "drives_v2").key_columns == (
        "season",
        "game_id",
        "drive_id",
        "offense",
        "defense",
    )
    with pytest.raises(SilverValidationError):
        silver_contract("byplay", "byplay_v9")


# --- byplay_v2 -----------------------------------------------------------------------


def v2_byplay(frame: pd.DataFrame) -> pd.DataFrame:
    return allplays_to_byplay(frame, nullable_ppa=True, play_identity="byplay_v2")


def test_byplay_v2_keeps_both_plays_and_validates_against_its_schema():
    byplay = v2_byplay(cross_period_collision())
    assert len(byplay) == 2
    assert set(byplay["source_play_id"]) == {"401762831104868701", "-22405"}
    assert byplay.duplicated(
        ["game_id", "drive_number", "play_number"], keep=False
    ).all()
    validate_frame(byplay, schema_for("byplay", "byplay_v2"))
    by_id = byplay.set_index("source_play_id")
    assert by_id.loc["-22405", "drive_id"] == "-2885"
    assert by_id.loc["401762831104868701", "drive_id_source"] == "provider"
    assert not byplay["drive_ambiguous"].any()


def test_byplay_v1_still_fails_closed_on_the_same_population():
    with pytest.raises(ValueError, match="byplay_v1 cannot represent distinct"):
        allplays_to_byplay(cross_period_collision())


def test_byplay_v2_exact_repeats_collapse_and_divergent_versions_block():
    base = play(__capture_id="a")
    assert len(v2_byplay(pd.DataFrame([base, {**base, "__capture_id": "b"}]))) == 1
    with pytest.raises(PlayIdentityError):
        v2_byplay(pd.DataFrame([play(ppa=0.1), play(ppa=0.9)]))


def test_byplay_v2_rejects_float_provider_ids():
    frame = pd.DataFrame([play(play_id=1.0), play(play_id=2.0, play_number=2)])
    with pytest.raises(PlayIdentityError, match="float provider IDs"):
        v2_byplay(frame)


def test_v2_schema_rejects_non_string_and_duplicate_identities():
    byplay = v2_byplay(cross_period_collision())
    schema = schema_for("byplay", "byplay_v2")
    as_int = byplay.assign(source_play_id=[1, 2])
    with pytest.raises(DatasetSchemaError, match="exact integer strings"):
        validate_frame(as_int, schema)
    with pytest.raises(DatasetSchemaError, match="exact integer strings"):
        validate_frame(byplay.assign(source_play_id=["1.5", "2"]), schema)
    with pytest.raises(DatasetSchemaError, match="duplicate keys"):
        validate_frame(byplay.assign(source_play_id=["7", "7"]), schema)


def test_v2_identifiers_survive_a_parquet_round_trip_as_exact_strings():
    byplay = v2_byplay(cross_period_collision())
    buffer = io.BytesIO()
    byplay.to_parquet(buffer)
    restored = pd.read_parquet(io.BytesIO(buffer.getvalue()))
    assert sorted(restored["source_play_id"]) == ["-22405", "401762831104868701"]
    validate_frame(restored, schema_for("byplay", "byplay_v2"))


# --- drives_v2 and derived drives ------------------------------------------------------


def reused_number_same_offense() -> pd.DataFrame:
    """Two provider drives of one team that a feed numbered identically."""
    return pd.DataFrame(
        [
            play(play_id=11, play_number=1, quarter=4, drive_id=1801),
            play(play_id=12, play_number=2, quarter=4, drive_id=1801),
            play(play_id=21, play_number=1, quarter=5, drive_id=-2885),
        ]
    )


def test_drives_v2_separates_reused_drive_numbers_by_provider_drive():
    byplay, drives, team_game, _ = build_preaggregation_pipeline(
        reused_number_same_offense(), nullable_ppa=True, play_identity="byplay_v2"
    )
    validate_frame(drives, schema_for("drives", "drives_v2"))
    assert sorted(drives["drive_id"]) == ["-2885", "1801"]
    assert drives.set_index("drive_id")["drive_plays"].to_dict() == {
        "-2885": 1,
        "1801": 2,
    }
    assert not drives["drive_ambiguous"].any()
    assert len(byplay) == 3 and len(team_game) >= 1


def test_drives_v1_merges_the_same_plays_when_the_offense_matches():
    deduped = reused_number_same_offense().drop_duplicates(
        ["game_id", "drive_number", "play_number"]
    )
    _, drives, _, _ = build_preaggregation_pipeline(deduped, nullable_ppa=True)
    assert len(drives) == 1  # v1 identity is (game, drive_number, offense, defense)


def test_provider_drive_keeps_the_v1_row_split_by_orientation():
    """A provider drive holds the kickoff and the receiving team's plays; v1 split these
    into separate drive rows and the team-game drive counts depend on that."""
    frame = pd.DataFrame(
        [
            play(play_id=1, play_number=1, drive_id=77, play_type="Kickoff"),
            play(
                play_id=2,
                play_number=2,
                drive_id=77,
                offense="Eastern Michigan",
                defense="Buffalo",
            ),
        ]
    )
    _, drives, _, _ = build_preaggregation_pipeline(
        frame, nullable_ppa=True, play_identity="byplay_v2"
    )
    _, v1_drives, _, _ = build_preaggregation_pipeline(frame, nullable_ppa=True)
    assert len(drives) == len(v1_drives) == 2
    assert set(drives["drive_id"]) == {"77"}
    assert not drives["drive_ambiguous"].any()
    validate_frame(drives, schema_for("drives", "drives_v2"))


def test_derived_drive_is_admitted_only_when_unambiguous():
    base = pd.DataFrame([play(play_id=1), play(play_id=2, play_number=2)]).drop(
        columns="drive_id"
    )
    ids, origin = provider_drive_ids(base)
    assert ids.tolist() == ["9-18", "9-18"] and set(origin) == {"derived"}
    admitted = base.assign(drive_id=ids, drive_id_source=origin)
    assert not derived_drive_ambiguity(admitted).any()
    # a kickoff plus the receiving team's plays is the normal two-orientation drive
    two_sided = admitted.copy()
    two_sided.loc[1, ["offense", "defense"]] = ["Eastern Michigan", "Buffalo"]
    assert not derived_drive_ambiguity(two_sided).any()
    # three orientations, or plays spread over distant periods, are not one drive
    three_sided = pd.concat(
        [two_sided, two_sided.iloc[[1]].assign(offense="BYU", defense="Arizona")],
        ignore_index=True,
    )
    assert derived_drive_ambiguity(three_sided).all()
    spread = admitted.copy()
    spread.loc[1, "quarter"] = 6
    assert derived_drive_ambiguity(spread).all()


# --- lineage -------------------------------------------------------------------------


def parent(dataset: str, schema_version: str) -> DatasetRef:
    return DatasetRef(
        dataset=dataset,
        version_id="v1",
        schema_version=schema_version,
        content_sha="0" * 64,
        uri=f"lake/silver/dataset={dataset}/version=v1/data.parquet",
    )


def test_lineage_problem_refuses_only_superseded_parents_for_v2_builds():
    old = [{"dataset": "byplay", "schema_version": "byplay_v1"}]
    new = [{"dataset": "byplay", "schema_version": "byplay_v2"}]
    assert "superseded byplay_v1" in lineage_problem("drives", "drives_v2", old)
    assert lineage_problem("drives", "drives_v2", new) is None
    assert (
        lineage_problem("drives", "drives_v1", old) is None
    )  # v1 evidence stays buildable
    assert lineage_problem("plays", "plays_v1", []) is None


def test_lake_builds_v2_and_refuses_a_v1_parent(tmp_path):
    from datetime import datetime, timezone

    storage = LocalStorage(str(tmp_path))
    byplay, drives, _, _ = build_preaggregation_pipeline(
        reused_number_same_offense(), nullable_ppa=True, play_identity="byplay_v2"
    )
    as_of = datetime(2026, 10, 9, tzinfo=timezone.utc)

    def build(dataset, version, frame, parents):
        return build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=tuple(parents),
                code_sha="c",
                config_sha="g",
                as_of=as_of,
                schema_version=version,
                tier="silver",
            ),
            records=frame.to_dict("records"),
            partitions={"seasons": [2025]},
        )

    byplay_ref, _ = build("byplay", "byplay_v2", byplay, [parent("plays", "plays_v1")])
    assert byplay_ref.schema_version == "byplay_v2"
    drives_ref, _ = build("drives", "drives_v2", drives, [byplay_ref])
    assert drives_ref.schema_version == "drives_v2"
    with pytest.raises(StorageError, match="superseded byplay_v1"):
        build("drives", "drives_v2", drives, [parent("byplay", "byplay_v1")])


# --- consumer guard ------------------------------------------------------------------


def test_consumers_refuse_a_byplay_v1_frame():
    v1 = allplays_to_byplay(pd.DataFrame([play()]))
    with pytest.raises(PlayIdentityError, match="requires byplay_v2"):
        require_v2_byplay(v1, consumer="possession ledger")
    v2 = v2_byplay(cross_period_collision())
    require_v2_byplay(v2, consumer="possession ledger")
    with pytest.raises(PlayIdentityError, match="exact strings"):
        require_v2_byplay(v2.assign(source_play_id=[1, 2]), consumer="x")
