"""Versioned required-check policy for the repair track."""

from __future__ import annotations

import json
from pathlib import Path

from cks_picks_cfb.quality.checks import REGISTRY, STAGES


def load_required_policy(path: Path) -> dict[str, tuple[str, ...]]:
    value = json.loads(path.read_text())
    if value.get("schema_version") != "data_quality_required_policy_v1":
        raise ValueError("Unknown data-quality required policy")
    stages = value.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGES):
        raise ValueError("Required policy must declare every stage")
    result = {}
    for stage, check_ids in stages.items():
        if not isinstance(check_ids, list) or len(check_ids) != len(set(check_ids)):
            raise ValueError(f"Invalid required-check list for {stage}")
        if any(
            check_id not in REGISTRY or REGISTRY[check_id].stage != stage
            for check_id in check_ids
        ):
            raise ValueError(f"Unknown or wrong-stage required check in {stage}")
        result[stage] = tuple(check_ids)
    return result
