"""Immutable inputs for the fixed V5 season computation (no catalog lookup)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pandas as pd

from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS

WORKFLOW_VERSION = "season_workflow_v1"
GRADING_POLICY = {
    "version": "season_grading_v1",
    "sources": ["retained_prekickoff", "cfbd_retrospective", "ungraded"],
    "selection": "model_side_best_quote_v2",
}


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def utc(value: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return stamp.tz_convert("UTC")


def validate_ref(ref: dict) -> None:
    if (
        not isinstance(ref, dict)
        or not ref.get("uri")
        or not re.fullmatch("[0-9a-f]{64}", ref.get("sha256", ""))
    ):
        raise ValueError("artifact ref requires uri and raw sha256")


def validate_model(model: dict) -> None:
    if (
        model.get("schema_version") != "season_model_v1"
        or model.get("model_id") != "v5-intended-update-2026-v1"
    ):
        raise ValueError("unsupported fixed season model")
    if model.get("design") != "ppp__rho_0_60__exposure" or model.get(
        "development_seasons"
    ) != list(DEVELOPMENT_SEASONS):
        raise ValueError("fixed model design/training seasons changed")
    for name in (
        "bridge",
        "priors",
        "terminal",
        "historical_population",
        "historical_events",
    ):
        validate_ref(model["inputs"][name])
    if (
        model["inputs"]["bridge"]["sha256"]
        != "a507d0c7cba5419868eac5c0955853d3e2855fc857aabf36f5cd192d5e7a90f1"
    ):
        raise ValueError("accepted B2 bridge bytes changed")


def validate_revision(revision: dict) -> None:
    if (
        revision.get("schema_version") != "season_revision_v1"
        or revision.get("season") != 2026
        or not revision.get("revision_id")
    ):
        raise ValueError("unsupported season revision")
    utc(revision["captured_at"])
    for name in ("schedule", "finals", "byplay", "drives", "reconciliation"):
        validate_ref(revision["inputs"][name])
    for name, ref in revision["inputs"].items():
        validate_ref(ref)
    for value in revision["pre_week_cutoffs"].values():
        utc(value)
