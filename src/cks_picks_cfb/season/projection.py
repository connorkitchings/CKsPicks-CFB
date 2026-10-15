"""Assemble the Step 2 serving-projection payload from the two builders.

The payload spec is :mod:`cks_picks_cfb.season.projection_common`. Lineage
identities are computed once here (:func:`verification.lineage_identities`) and
handed to both builders, so every table carries the same rating/measurement sha.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.season import projection_football, projection_serving
from cks_picks_cfb.season.projection_common import PROJECTION_ORDER
from cks_picks_cfb.season.verification import lineage_identities, run_id_for


def build_projections(
    frames: Mapping[str, Any],
    inputs: Any,
    revision: Mapping[str, Any],
    manifest_context: Mapping[str, Any],
) -> dict[str, list[dict]]:
    """Return the full payload: ``prediction_runs`` then :data:`PROJECTION_ORDER`.

    ``manifest_context`` holds the run ``identity`` and the prepared
    ``output_refs`` (the written frames, at least the rating, measurement and
    ``predictions`` outputs). ``inputs`` is the ``inputs.SeasonInputs`` whose
    ``schedule`` is the FULL season (``frames["schedule"]`` stops at the active
    week). The builders receive ``identity`` plus ``run_id`` / ``release_id`` (the
    run id they derive weekly run, snapshot and ``season-run:`` ids from) and
    ``predictions_sha256`` (the written predictions artifact).
    """
    identity = manifest_context["identity"]
    refs = manifest_context["output_refs"]
    lineage = lineage_identities(identity, refs)
    run_id = run_id_for(identity)
    arguments = {
        "frames": frames,
        "inputs": inputs,
        "revision": revision,
        "identity": {
            **identity,
            "run_id": run_id,
            "release_id": run_id,
            "predictions_sha256": refs["predictions"]["sha256"],
        },
        "ratings_id": lineage["rating"],
        "measurement_id": lineage["measurement"],
    }
    parts = (
        (projection_serving.SERVING_KEYS, projection_serving.build_serving_core),
        (projection_football.FOOTBALL_KEYS, projection_football.build_football),
    )
    tables: dict[str, list[dict]] = {}
    for keys, build in parts:
        built = build(**arguments)
        if set(built) != set(keys):
            raise ValueError(f"{build.__name__} returned tables {sorted(built)}")
        tables.update(built)
    return {name: tables[name] for name in ("prediction_runs", *PROJECTION_ORDER)}
