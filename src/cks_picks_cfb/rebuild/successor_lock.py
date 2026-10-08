"""A successor source lock for a corrected rebuild (pure, I/O-free).

The successor builders (rating, forecast, serving, packaging) all read one lock in schema
``v5_intended_update_2026_source_lock_v1``. The first lock pinned the first repaired lineage
and the runs served in September. The corrected rebuild already extends that lock with the
finals and cutoffs it needs (``rebuild.lock_extension``); this module derives from the
extended lock the version the successor chain should read:

* replay weeks 0..N-1 only (``active_week`` names the first week that is not replayed);
* a market source for every replay week (new weeks from the reconstruction source refs;
  every week pins the current threshold configuration, the replaced one is recorded);
* the originally *served* runs as the runs being replaced;
* the corrected lineage named explicitly, with the legacy parent keys carrying the
  hashes of the corrected rebuild instead of the old research manifests.

It never edits games, points, cutoffs or earlier market sources.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

LOCK_SCHEMA = "v5_intended_update_2026_source_lock_v1"
LINEAGE_KEY = "corrected_lineage"


class SuccessorLockError(ValueError):
    """The corrected successor lock cannot be derived without inventing evidence."""


def derive_successor_lock(
    extended: Mapping[str, Any],
    *,
    refs: Mapping[str, Any],
    served_runs: Mapping[int, Mapping[str, Any]],
    week_configs: Mapping[int, Mapping[str, Any]],
    lineage: Mapping[str, Any],
    schedule_content_sha256: str,
    schedule_uri: str,
) -> dict[str, Any]:
    """Return the corrected successor lock for replay weeks ``0..max(cutoff week)``."""
    if extended.get("schema_version") != LOCK_SCHEMA:
        raise SuccessorLockError("unknown base lock schema")
    if "extends" not in extended:
        raise SuccessorLockError("the base lock must be a rebuild extension")
    if LINEAGE_KEY in extended:
        raise SuccessorLockError("the lock is already a corrected successor lock")
    lock = copy.deepcopy(dict(extended))
    cutoffs = sorted(int(week) for week in lock["post_week_cutoffs"])
    last = cutoffs[-1]
    weeks = list(range(last + 1))
    if cutoffs != weeks:
        raise SuccessorLockError("post-week cutoffs are not contiguous")
    game_weeks = {int(row[0]) for row in lock["games"]["rows"]}
    if game_weeks != set(weeks):
        raise SuccessorLockError(f"lock games cover weeks {sorted(game_weeks)}")
    if any(row[5] is None or row[6] is None for row in lock["games"]["rows"]):
        raise SuccessorLockError("every replay game needs a certified final score")
    for name, mapping in (
        ("served_runs", served_runs),
        ("week_configs", week_configs),
    ):
        if sorted(mapping) != weeks:
            raise SuccessorLockError(f"{name} must cover exactly weeks {weeks}")

    market_sources = dict(lock["market_sources"])
    for week in weeks:
        meta = refs["weeks"][str(week)]
        config = week_configs[week]
        if str(week) in market_sources:
            current = dict(market_sources[str(week)])
            if current["as_of"] != meta["as_of"]:
                raise SuccessorLockError(f"week {week} market as_of differs from refs")
            if (current["config"], current["config_sha256"]) != (
                config["path"],
                config["sha256"],
            ):
                # The threshold policy changed after the first lock (edge constraints were
                # removed); the corrected chain pins the current policy and says so.
                current["superseded_config"] = {
                    "path": current["config"],
                    "sha256": current["config_sha256"],
                }
                current["config"] = config["path"]
                current["config_sha256"] = config["sha256"]
            market_sources[str(week)] = current
            continue
        sources = meta["market_sources"]
        market_sources[str(week)] = {
            "as_of": meta["as_of"],
            "config": config["path"],
            "config_sha256": config["sha256"],
            "market_quotes": dict(sources["market_quotes"]),
            "market_snapshots": dict(sources["market_snapshots"]),
        }
    lock["market_sources"] = {str(w): market_sources[str(w)] for w in weeks}

    lock["selected_runs"] = [
        {
            "week": week,
            "run_id": served_runs[week]["run_id"],
            "state": "scored",
            "data_as_of": refs["weeks"][str(week)]["as_of"],
            "source_manifest": dict(refs["weeks"][str(week)]["source_manifest"]),
        }
        for week in weeks
    ]
    lock["active_week"] = {"active_run_id": None, "season": 2026, "week": last + 1}

    extension = lock["extends"]
    lock["game_rows_sha256"] = extension["game_rows_sha256"]
    lock["research_2026_measurement_sha256"] = lineage["measurement_parent_sha256"]
    lock["research_2026_rating_sha256"] = lineage["rating_parent_sha256"]
    lock["research_2026_prediction_keys"] = {
        "completed_games": len(lock["games"]["rows"])
    }
    lock["research_source_import"] = {
        "schema_version": "corrected_rebuild_source_import_v1",
        "replay_parents": {
            "schedule_content_sha256": schedule_content_sha256,
            "schedule_uri": schedule_uri,
        },
    }
    for stale in ("research_parent_sha256", "certified_weekly_rating_parents"):
        lock.pop(stale, None)
    lock[LINEAGE_KEY] = {
        **dict(lineage),
        "field_semantics": {
            "research_2026_measurement_sha256": "raw sha256 of the published 6A root manifest, which hash-pins the corrected measurements",
            "research_2026_rating_sha256": "raw sha256 of the Task 4 receipt that certifies the corrected ratings and forecast comparison",
            "game_rows_sha256": "sha256(canonical_json(games.rows)) of the rows in this lock (the base lock's own hash is in extends.base_game_rows_sha256)",
            "selected_runs": "the runs served before the replacement, i.e. the runs being replaced",
        },
    }
    return lock
