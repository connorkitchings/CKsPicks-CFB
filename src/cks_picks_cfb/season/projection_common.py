"""Shared, frozen interface for building the Step 2 serving-projection payload.

This docstring is the AUTHORITATIVE PAYLOAD SPEC. Builders (``projection_serving``,
``projection_football``, ``projection_charts``), verification (``verification``) and staging (``release``)
must all agree with it; change it only by changing this module first.

Payload shape
-------------
The payload is ONE canonical JSON object, encoded with :func:`canonical_bytes`
(re-exported ``manifest.canonical``: sorted keys, ``(",", ":")`` separators,
``allow_nan=False``, ASCII-escaped non-ASCII text -- one encoding for every season
artifact) and hashed with :func:`sha256_hex` (``manifest.sha``)::

    {"prediction_runs": [...], "games": [...], ..., "site_week_selections": [...]}

Its keys are exactly ``"prediction_runs"`` plus the names of
:data:`PROJECTION_SETS` ``[STAGING_PROJECTION_SET]`` (retained releases keep the older set they recorded), in
:data:`PROJECTION_ORDER` (parents before children; staging inserts in this order).
Each table value is a list of row dicts built with :func:`clean_rows`, sorted by the
builder by the table's natural key (``release.PROJECTION_KEYS``).

Row columns
-----------
Every row dict has exactly the columns of ``season_release_<table>`` in
``contracts/migrations/0025_season_releases.sql`` (core tables) or ``0026_team_chart_tables.sql`` (chart tables) minus :data:`SERVER_COLUMNS`.
``release_id`` and ``environment`` are filled in by staging; they NEVER appear in
payload rows or in any checksum (payload sha, per-table ``projection_checks``,
readback comparison; note ``release.projection_check`` currently strips only
``environment`` from read-back rows -- staging must strip both). Columns that have a database default (``created_at``,
``inserted_at``, ``updated_at``, ``graded_at``, ``selected_at``, ``published_at``,
...) are still present in the payload with explicit values.

Determinism
-----------
* All audit timestamps are deterministic: the revision ``captured_at`` or the
  week's cutoff, never ``now()``. Two builds of the same inputs produce identical
  bytes.
* Timestamps are timezone-aware UTC ISO-8601 strings with microseconds, e.g.
  ``"2026-10-14T14:42:04.000000+00:00"``; naive timestamps are an error.
* NaN/NaT/NA become ``null``; non-finite floats are an error.
* ``profit_units`` (and other NUMERIC(…, 4) values) are :func:`quantize4` values.

Table semantics
---------------
* ``games``: the FULL season schedule of the revision -- every scheduled FBS game
  of every week of the season, including weeks beyond the active week and games
  already started. The prediction columns (``predicted_spread``,
  ``predicted_total``, ``predicted_spread_std_dev``, ``predicted_total_std_dev``,
  ``home_team_spread_line``, ``total_line``, ``spread_lean``, ``total_lean``,
  ``edge_spread``, ``edge_total``, ``high_confidence``, ``source_config``,
  ``system_name``, ``model_id``) are ``null`` for games without a prediction in
  the release (``high_confidence`` is NOT NULL in the schema: ``false`` there).
  ``games`` uses provider team names.
* ``predictions``: rows only for predicted games.
* ``prediction_runs``: one record per week ``0..active_week`` with run id
  :func:`weekly_run_id` ``(run_id, week)``; ``state`` is ``'scored'`` for weeks
  ``<= through_week`` else ``'published'``; ``evidence_class`` is ``'replay'``
  for reconstructed weeks and ``'pending'`` for the live week.
* ``prediction_grades``: lowercase ``result`` (``'win'``, ``'loss'``,
  ``'push'``), ``profit_units`` quantized to 4 places, ``grading_version`` =
  :func:`benchmark_grading_version` ``(benchmark_type)``.
  ``prediction_market_selections`` use :data:`SELECTION_POLICY_VERSION`; market
  snapshots use :data:`MARKET_POLICY_VERSION`.
* ``team_season_roster``, ``team_game_stats`` and ``team_adjusted_epa`` (the chart
  tables) are descriptive reconstructions from the pinned revision inputs, windowed by
  week; they use provider team names and never feed ratings, forecasts or grading.
* Rating snapshot ids (``v5_rating_snapshots.snapshot_id``):
  preseason ``{run}:pregame:{team}:preseason``; per-week pregame
  ``{run}:pregame:{team}:week-{w}`` (``w >= 1``); current
  ``{run}:current:post-week-{N}:{team}``. Rating tables use canonical team names.
* :func:`rating_identity` and :func:`measurement_identity` are computed once per
  build and are identical across every table/run that carries a rating or
  measurement manifest sha (e.g. ``matchup_data_publications.rating_manifest_sha256``
  / ``measurement_manifest_sha256``).
* ``matchup_data_publications.rating_manifest_uri`` /
  ``measurement_manifest_uri`` are logical strings
  ``season-run:<run_id>#ratings`` / ``season-run:<run_id>#measurements``, never
  local paths.

Prepared output names (``manifest["output_refs"]`` keys, from ``prepare.compute``)
------------------------------------------------------------------------------
``rating_identity`` hashes the ``sha256`` of the refs ``ratings`` (pregame team
ratings), ``rating_roles`` (pregame role ratings), ``current_ratings`` (post-week
team ratings) and ``current_rating_roles`` (post-week role ratings).
``measurement_identity`` hashes the refs ``measurements`` (``inputs.observations``)
and ``scoring_events`` (``inputs.events``).

Verification report ``season_verification_v2``
---------------------------------------------
::

    {
      "schema_version": "season_verification_v2",
      "checks": {name: {"passed": bool, "observed": {...},
                        "source": "projection" | "prepare"}},
      "projection_checks": {table: {"rows": int, "sha256": str}},
      "row_counts": {table: int}
    }

``checks`` keys are exactly ``verification.REQUIRED_PROJECTION_CHECKS |
verification.REQUIRED_PREPARE_CHECKS``. ``projection_checks`` and ``row_counts``
cover every table in :data:`PROJECTION_ORDER`.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Collection, Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.season.manifest import canonical as canonical_bytes
from cks_picks_cfb.season.manifest import sha as sha256_hex

__all__ = [
    "GRADING_VERSION",
    "MARKET_POLICY_VERSION",
    "CHART_TABLES",
    "PROJECTION_ORDER",
    "PROJECTION_SETS",
    "STAGING_PROJECTION_SET",
    "RATING_OUTPUTS",
    "MEASUREMENT_OUTPUTS",
    "SELECTION_POLICY_VERSION",
    "SERVER_COLUMNS",
    "benchmark_grading_version",
    "canonical_bytes",
    "clean_rows",
    "clean_value",
    "measurement_identity",
    "quantize4",
    "rating_identity",
    "recognized_projection_set",
    "sha256_hex",
    "weekly_run_id",
]

_CORE_V1_ORDER: tuple[str, ...] = (
    "games",
    "game_venues",
    "game_results",
    "predictions",
    "prediction_grades",
    "market_quotes",
    "market_snapshots",
    "market_snapshot_quotes",
    "prediction_market_selections",
    "system_stats",
    "v5_rating_snapshots",
    "team_season_stats",
    "matchup_data_publications",
    "team_game_measurements",
    "team_possession_stats",
    "team_possession_adjusted",
    "team_rating_components",
    "site_week_selections",
)
CHART_TABLES: tuple[str, ...] = (
    "team_season_roster",
    "team_game_stats",
    "team_adjusted_epa",
)
#: Versioned table sets. A release records the set it was staged with (its
#: ``projection_checks`` keys); retained releases are read back against that set.
PROJECTION_SETS: dict[str, tuple[str, ...]] = {
    "core_v1": _CORE_V1_ORDER,
    "charts_v1": (*_CORE_V1_ORDER, *CHART_TABLES),
}
#: The only set new candidates may be staged with.
STAGING_PROJECTION_SET = "charts_v1"
PROJECTION_ORDER: tuple[str, ...] = PROJECTION_SETS[STAGING_PROJECTION_SET]
SERVER_COLUMNS = frozenset({"release_id", "environment"})

GRADING_VERSION = "model_side_best_quote_v2"
SELECTION_POLICY_VERSION = "model_side_best_quote_v2"
MARKET_POLICY_VERSION = "consensus_then_median_v1"

RATING_OUTPUTS = ("ratings", "rating_roles", "current_ratings", "current_rating_roles")
MEASUREMENT_OUTPUTS = ("measurements", "scoring_events")

_QUANTUM = Decimal("0.0001")


def recognized_projection_set(keys: Collection[str]) -> str:
    """The name of the projection set whose tables exactly equal ``keys``.

    Unknown, partial and mixed sets always raise ``ValueError``.
    """
    names = set(keys)
    for name, tables in PROJECTION_SETS.items():
        if names == set(tables):
            return name
    raise ValueError("projection tables are not a recognized projection set")


def benchmark_grading_version(benchmark_type: str) -> str:
    return f"{GRADING_VERSION}:{benchmark_type}"


def weekly_run_id(run_id: str, week: int) -> str:
    return f"{run_id}:w{week}"


def quantize4(x: Any) -> float | None:
    """Round half-even to 4 decimals; ``None`` for missing values."""
    if x is None or (isinstance(x, (float, np.floating)) and math.isnan(x)):
        return None
    return float(Decimal(str(x)).quantize(_QUANTUM, rounding=ROUND_HALF_EVEN))


def _timestamp(value: dt.datetime) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError(f"naive timestamp in projection: {value!r}")
    return stamp.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def clean_value(v: Any) -> Any:
    """Convert one cell to a JSON-native value (see the module spec)."""
    if isinstance(v, (list, tuple, np.ndarray)):
        return [clean_value(item) for item in v]
    if isinstance(v, Mapping):
        return {str(k): clean_value(item) for k, item in v.items()}
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, dt.datetime):  # includes pd.Timestamp
        return _timestamp(v)
    if isinstance(v, np.datetime64):
        if np.isnat(v):
            return None
        raise ValueError(f"naive timestamp in projection: {v!r}")
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating, Decimal)):
        number = float(v)
        if math.isnan(number):
            return None
        if math.isinf(number):
            raise ValueError("non-finite number in projection")
        return number
    if isinstance(v, str):
        return v
    raise TypeError(f"unsupported projection value type: {type(v).__name__}")


def clean_rows(frame: pd.DataFrame, columns: Sequence[str]) -> list[dict]:
    """Rows with exactly ``columns`` in order; the caller owns row ordering."""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise KeyError(f"projection frame is missing columns: {missing}")
    selected = frame.loc[:, list(columns)]
    return [
        {column: clean_value(value) for column, value in zip(columns, row, strict=True)}
        for row in selected.itertuples(index=False, name=None)
    ]


def _identity(fields: dict, output_shas: Mapping[str, str], names: tuple) -> str:
    missing = [name for name in names if name not in output_shas]
    if missing:
        raise KeyError(f"missing output shas: {missing}")
    outputs = {name: output_shas[name] for name in names}
    return sha256_hex(canonical_bytes({**fields, "outputs": outputs}))


def rating_identity(
    *,
    model_sha: str,
    revision_sha: str,
    workflow: str,
    output_shas: Mapping[str, str],
) -> str:
    """Sha256 identifying the rating outputs (:data:`RATING_OUTPUTS`) of a run."""
    return _identity(
        {"model_sha": model_sha, "revision_sha": revision_sha, "workflow": workflow},
        output_shas,
        RATING_OUTPUTS,
    )


def measurement_identity(*, revision_sha: str, output_shas: Mapping[str, str]) -> str:
    """Sha256 identifying the measurement outputs (:data:`MEASUREMENT_OUTPUTS`)."""
    return _identity({"revision_sha": revision_sha}, output_shas, MEASUREMENT_OUTPUTS)
