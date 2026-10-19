import datetime as dt
import math

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.season import projection_common as pc
from cks_picks_cfb.season import release
from cks_picks_cfb.season.projection_charts import CHART_KEYS
from cks_picks_cfb.season.projection_football import FOOTBALL_KEYS
from cks_picks_cfb.season.projection_serving import SERVING_KEYS

RATING_SHAS = {name: name * 2 for name in pc.RATING_OUTPUTS}
MEASUREMENT_SHAS = {name: name * 2 for name in pc.MEASUREMENT_OUTPUTS}


def test_projection_order_matches_release_keys():
    assert list(pc.PROJECTION_ORDER) == list(release.PROJECTION_KEYS)


def test_builder_keys_partition_projection_tables():
    serving = set(SERVING_KEYS) - {"prediction_runs"}
    assert serving.isdisjoint(FOOTBALL_KEYS)
    resume = {"team_resume"}
    assert serving | set(FOOTBALL_KEYS) | set(CHART_KEYS) | resume == set(
        pc.PROJECTION_ORDER
    )


def test_server_columns_are_release_and_environment():
    assert pc.SERVER_COLUMNS == {"release_id", "environment"}


def test_versions_and_run_ids():
    assert pc.weekly_run_id("run", 3) == "run:w3"
    assert pc.benchmark_grading_version("closing") == (
        "model_side_best_quote_v2:closing"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.00005, 1.0),
        (1.00015, 1.0002),
        (-0.90909090, -0.9091),
        (2, 2.0),
        (None, None),
        (float("nan"), None),
        (np.float64("nan"), None),
    ],
)
def test_quantize4_half_even_and_missing(value, expected):
    assert pc.quantize4(value) == expected


def test_clean_rows_types_order_and_missing():
    frame = pd.DataFrame(
        {
            "extra": [1, 2],
            "b": [np.float64(1.5), np.nan],
            "a": [np.int64(7), np.int64(8)],
            "flag": [np.bool_(True), np.bool_(False)],
            "at": pd.to_datetime(["2026-10-14T10:42:04-04:00", None], utc=True),
            "weeks": [np.array([1, 2]), []],
        }
    )
    rows = pc.clean_rows(frame, ["b", "a", "flag", "at", "weeks"])
    assert [list(row) for row in rows] == [["b", "a", "flag", "at", "weeks"]] * 2
    assert rows[0] == {
        "b": 1.5,
        "a": 7,
        "flag": True,
        "at": "2026-10-14T14:42:04.000000+00:00",
        "weeks": [1, 2],
    }
    assert rows[1]["b"] is None and rows[1]["at"] is None
    assert type(rows[0]["a"]) is int and type(rows[0]["flag"]) is bool
    assert pc.clean_value(pd.NA) is None


def test_clean_value_converts_aware_python_datetime():
    stamp = dt.datetime(2026, 9, 1, 12, tzinfo=dt.timezone(dt.timedelta(hours=-5)))
    assert pc.clean_value(stamp) == "2026-09-01T17:00:00.000000+00:00"


def test_clean_rows_rejects_naive_timestamp():
    frame = pd.DataFrame({"at": pd.to_datetime(["2026-10-14T14:42:04"])})
    with pytest.raises(ValueError, match="naive"):
        pc.clean_rows(frame, ["at"])


def test_clean_rows_rejects_infinity_and_missing_columns():
    with pytest.raises(ValueError, match="non-finite"):
        pc.clean_rows(pd.DataFrame({"x": [math.inf]}), ["x"])
    with pytest.raises(KeyError):
        pc.clean_rows(pd.DataFrame({"x": [1]}), ["x", "y"])


def test_canonical_bytes_is_deterministic():
    left = pc.canonical_bytes({"b": [1, 2], "a": {"y": 1, "x": None}})
    right = pc.canonical_bytes({"a": {"x": None, "y": 1}, "b": [1, 2]})
    assert left == right == b'{"a":{"x":null,"y":1},"b":[1,2]}'
    assert pc.sha256_hex(left) == pc.sha256_hex(right)
    with pytest.raises(ValueError):
        pc.canonical_bytes({"x": math.nan})


def _rating(**overrides):
    args = {
        "model_sha": "m",
        "revision_sha": "r",
        "workflow": "w",
        "output_shas": RATING_SHAS,
    }
    return pc.rating_identity(**{**args, **overrides})


def test_rating_identity_changes_with_every_input():
    base = _rating()
    assert base == _rating(output_shas={**RATING_SHAS, "unrelated": "x"})
    variants = [_rating(model_sha="m2"), _rating(revision_sha="r2")]
    variants.append(_rating(workflow="w2"))
    variants += [
        _rating(output_shas={**RATING_SHAS, name: "changed"})
        for name in pc.RATING_OUTPUTS
    ]
    assert base not in variants and len(set(variants)) == len(variants)


def test_measurement_identity_changes_with_every_input():
    base = pc.measurement_identity(revision_sha="r", output_shas=MEASUREMENT_SHAS)
    variants = [
        pc.measurement_identity(revision_sha="r2", output_shas=MEASUREMENT_SHAS)
    ]
    variants += [
        pc.measurement_identity(
            revision_sha="r", output_shas={**MEASUREMENT_SHAS, name: "changed"}
        )
        for name in pc.MEASUREMENT_OUTPUTS
    ]
    assert base not in variants and len(set(variants)) == len(variants)


def test_identities_raise_on_missing_outputs():
    shas = dict(RATING_SHAS)
    del shas["current_rating_roles"]
    with pytest.raises(KeyError, match="current_rating_roles"):
        _rating(output_shas=shas)
    with pytest.raises(KeyError, match="scoring_events"):
        pc.measurement_identity(revision_sha="r", output_shas={"measurements": "x"})
