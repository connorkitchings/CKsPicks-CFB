"""Digests of model outputs and core projection payloads for the isolation test.

``digests`` hashes the prepared V5 rating and forecast frames (numeric content;
release identity and provenance columns are excluded and listed in
``EXCLUDED_PROVENANCE``) and the byte payload of the existing football
projection tables built with the fixture's fixed identity.
"""

from __future__ import annotations

from typing import Any

from cks_picks_cfb.season import projection_common as pc
from cks_picks_cfb.season.projection_football import FOOTBALL_KEYS, build_football

MODEL_FRAMES = (
    "ratings",
    "rating_roles",
    "current_ratings",
    "current_rating_roles",
    "features",
    "offsets",
    "predictions",
    "grades",
)
#: Identity/provenance columns that may legitimately change with the release
#: (code commit, release and run ids, created-at and provenance hashes).
EXCLUDED_PROVENANCE = frozenset(
    {"run_id", "model_ref", "state_ref", "source_ref", "candidate_id", "created_at"}
)


def digests(season: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in MODEL_FRAMES:
        frame = season["frames"][name]
        columns = [c for c in frame.columns if c not in EXCLUDED_PROVENANCE]
        out[f"frame:{name}"] = pc.sha256_hex(
            pc.canonical_bytes(pc.clean_rows(frame, columns))
        )
    payload = build_football(**season)
    for key in FOOTBALL_KEYS:
        out[f"core_v1:{key}"] = pc.sha256_hex(pc.canonical_bytes(payload[key]))
    return out
