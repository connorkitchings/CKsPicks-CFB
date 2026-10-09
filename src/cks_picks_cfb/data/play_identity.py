"""Provider-keyed play identity for ``byplay_v2`` and ``drives_v2``.

A source play is identified by ``(season, game_id, source_play_id)``. Displayed drive and
play numbers are attributes and ordering inputs, never the uniqueness key. Provider IDs
are exact strings: some are negative synthetic values and some have 18 digits, so a float
conversion would silently corrupt them. ``byplay_v1`` stays readable as superseded
evidence; new corrected descendants must descend from v2.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd

BYPLAY_V1 = "byplay_v1"
BYPLAY_V2 = "byplay_v2"
DRIVES_V1 = "drives_v1"
DRIVES_V2 = "drives_v2"

#: Schema versions whose builds may only descend from v2 play identity. Later tasks add the
#: v2 possession, scoring-ledger and observation versions here.
REQUIRES_V2_PLAY_IDENTITY = frozenset({BYPLAY_V2, DRIVES_V2})
#: Play-derived datasets that carry a play-identity version, and their superseded versions.
PLAY_IDENTITY_DATASETS = {"byplay": BYPLAY_V1, "drives": DRIVES_V1}

SOURCE_PLAY_ID = "source_play_id"
#: Floats are exact only below 2**53; drive IDs (about 11 digits) fit, play IDs do not.
_EXACT_FLOAT_LIMIT = 2**53
_INTEGER_TEXT = re.compile(r"[+-]?\d+")


class PlayIdentityError(ValueError):
    """Raised when play identity cannot be established without losing a source event."""


def source_id_strings(
    values: pd.Series,
    *,
    label: str,
    allow_missing: bool = False,
    allow_exact_float: bool = False,
) -> pd.Series:
    """Provider IDs as exact strings.

    Integers and integer text are converted once. Float input is rejected, because it loses
    precision on 18-digit IDs, unless ``allow_exact_float`` admits integral values below
    2**53 (used only for drive IDs that pandas promoted to float because some were missing).
    """
    if not allow_exact_float and pd.api.types.is_float_dtype(values):
        raise PlayIdentityError(
            f"{label}: float provider IDs lose precision; refusing to convert"
        )
    converted: list[str | None] = []
    for value in values:
        if (
            value is None
            or value is pd.NA
            or (isinstance(value, (float, np.floating)) and np.isnan(value))
        ):
            if not allow_missing:
                raise PlayIdentityError(f"{label}: provider ID is missing")
            converted.append(None)
        elif isinstance(value, (bool, np.bool_)):
            raise PlayIdentityError(f"{label}: boolean provider ID")
        elif isinstance(value, str):
            text = value.strip()
            if not _INTEGER_TEXT.fullmatch(text):
                raise PlayIdentityError(f"{label}: non-integer provider ID {value!r}")
            converted.append(str(int(text)))
        elif isinstance(value, (float, np.floating)):
            if not allow_exact_float:
                raise PlayIdentityError(f"{label}: float provider ID {value!r}")
            number = float(value)
            if not number.is_integer() or abs(number) >= _EXACT_FLOAT_LIMIT:
                raise PlayIdentityError(f"{label}: inexact float provider ID {value!r}")
            converted.append(str(int(number)))
        else:
            converted.append(str(int(value)))
    return pd.Series(converted, index=values.index, dtype="string")


def deduplicate_source_plays(plays: pd.DataFrame) -> pd.DataFrame:
    """Key plays by provider ID; collapse only payload-identical repeats.

    Every row must carry a provider ID. Rows that repeat a provider ID with an identical
    payload (ignoring capture metadata) collapse to one. Two different payloads for one
    ``(season, game_id, source_play_id)`` are divergent versions of a source play and block
    the build. Distinct provider IDs that share a displayed sequence are all kept.
    """
    id_column = next((name for name in ("play_id", "id") if name in plays), None)
    if id_column is None:
        raise PlayIdentityError("source plays lack a provider play ID column")
    if "game_id" not in plays:
        raise PlayIdentityError("source plays lack game_id")
    frame = plays.copy()
    frame[SOURCE_PLAY_ID] = source_id_strings(frame[id_column], label=SOURCE_PLAY_ID)
    payload = [c for c in frame.columns if not c.startswith("__capture_")]
    exact = frame.drop_duplicates(subset=payload, keep="first")
    key = [c for c in ("season", "game_id", SOURCE_PLAY_ID) if c in exact]
    divergent = exact.duplicated(key, keep=False)
    if divergent.any():
        example = exact.loc[divergent, key].iloc[0].to_dict()
        raise PlayIdentityError(
            f"{int(divergent.sum())} rows are divergent versions of one provider play "
            f"(for example {example}); quarantine the source before building"
        )
    return exact


def provider_drive_ids(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Per-play ``drive_id`` strings and whether each came from the provider or was derived.

    A provider ``drive_id`` is used as given. Where it is absent the drive is derived from
    ``game_id`` and the displayed ``drive_number``; whether that derivation is admissible is
    decided by :func:`derived_drive_ambiguity`.
    """
    fallback = (
        frame["game_id"].astype("int64").astype(str)
        + "-"
        + frame["drive_number"].astype("int64").astype(str)
    )
    if "drive_id" not in frame:
        return fallback.astype("string"), pd.Series(
            "derived", index=frame.index, dtype="string"
        )
    provider = source_id_strings(
        frame["drive_id"],
        label="drive_id",
        allow_missing=True,
        allow_exact_float=True,
    )
    has_provider = provider.notna()
    ids = provider.where(has_provider, fallback.astype("string"))
    origin = pd.Series("derived", index=frame.index, dtype="string").mask(
        has_provider, "provider"
    )
    return ids.astype("string"), origin


def derived_drive_ambiguity(frame: pd.DataFrame) -> pd.Series:
    """True for plays of a derived drive whose membership cannot be trusted.

    A provider drive normally holds the kickoff (kicking team on offense) followed by the
    receiving team's plays, so up to two offense/defense orientations are expected. A derived
    drive (no provider ``drive_id``) is admitted only when it has at most two orientations and
    its plays fall in at most two adjacent periods; otherwise its membership is ambiguous.
    Provider drives are always admitted as the provider defines them.
    """
    derived = frame["drive_id_source"] == "derived"
    ambiguous = pd.Series(False, index=frame.index)
    if not derived.any():
        return ambiguous
    sub = frame.loc[derived]
    orientation = sub["offense"].astype(str) + "|" + sub["defense"].astype(str)
    groups = sub.assign(orientation=orientation).groupby(
        ["game_id", "drive_id"], sort=False
    )
    many_sides = groups["orientation"].transform("nunique") > 2
    spread = groups["quarter"].transform("max") - groups["quarter"].transform("min") > 1
    ambiguous.loc[sub.index] = (many_sides | spread).to_numpy()
    return ambiguous


def lineage_problem(
    dataset: str, schema_version: str, parent_versions: Iterable[Mapping[str, Any]]
) -> str | None:
    """Why this build may not use these parents, or ``None``.

    Builds of a v2 play-identity schema must not descend from a superseded ``byplay_v1`` or
    ``drives_v1`` parent. ``parent_versions`` items carry ``dataset`` and ``schema_version``.
    """
    if schema_version not in REQUIRES_V2_PLAY_IDENTITY:
        return None
    for parent in parent_versions:
        name = parent["dataset"]
        if name in PLAY_IDENTITY_DATASETS and (
            parent["schema_version"] == PLAY_IDENTITY_DATASETS[name]
        ):
            return (
                f"{dataset} {schema_version} cannot descend from the superseded "
                f"{parent['schema_version']} {name} parent"
            )
    return None


def require_v2_byplay(frame: pd.DataFrame, *, consumer: str) -> None:
    """Refuse a by-play frame that lacks v2 provider-keyed identity."""
    if SOURCE_PLAY_ID not in frame:
        raise PlayIdentityError(
            f"{consumer} requires byplay_v2 (no {SOURCE_PLAY_ID} column); "
            "byplay_v1 is superseded evidence"
        )
    column = frame[SOURCE_PLAY_ID]
    if column.isna().any():
        raise PlayIdentityError(f"{consumer}: {SOURCE_PLAY_ID} has missing values")
    if not all(isinstance(value, str) for value in column):
        raise PlayIdentityError(f"{consumer}: {SOURCE_PLAY_ID} must be exact strings")
    key = [c for c in ("season", "game_id", SOURCE_PLAY_ID) if c in frame]
    if frame.duplicated(key).any():
        raise PlayIdentityError(f"{consumer}: duplicate provider play identities")


def require_v1_byplay(*frames: pd.DataFrame, consumer: str) -> None:
    """Refuse provider-keyed v2 frames in a consumer that is pinned to ``byplay_v1`` identity.

    Some consumers sort or join on the displayed drive/play numbers or on pinned legacy event
    ids. Feeding them v2 frames would misorder or mis-join silently, so they fail loudly.
    """
    for frame in frames:
        if SOURCE_PLAY_ID in frame.columns or "drive_id_source" in frame.columns:
            raise PlayIdentityError(
                f"{consumer} is pinned to byplay_v1 identity and cannot accept "
                "provider-keyed v2 frames"
            )
