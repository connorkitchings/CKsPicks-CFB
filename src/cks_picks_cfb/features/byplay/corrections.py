"""Play-by-play data corrections and legacy fix catalog."""

from __future__ import annotations

import hashlib
import json

import pandas as pd


def legacy_data_fixes() -> list[tuple[tuple[int, ...], dict[str, object]]]:
    """Return the legacy correction definitions for one-time dataset seeding."""
    conditions_and_updates = [
        ((400937467, 1, 5), {"yards_gained": 15, "play_type": "Penalty"}),
        ((400547851, 11, 6), {"yards_gained": 15, "play_type": "Penalty"}),
        ((400547737, 9, 1), {"yards_to_first": 1}),
        (
            ((400547737, 9, 2)),
            {
                "yard_line": 2,
                "yards_to_goal": 98,
                "yards_to_first": 9,
                "yards_gained": -1,
                "adj_yd_line": 98,
            },
        ),
        ((400547737, 9, 3), {"yards_to_first": 10}),
        ((400547739, 11, 14), {"yards_gained": -5}),
        (
            ((400547739, 11, 15)),
            {
                "yard_line": 82,
                "yards_to_goal": 18,
                "yards_to_first": 18,
                "adj_yd_line": 18,
            },
        ),
        (
            ((400547739, 11, 16)),
            {
                "yard_line": 82,
                "yards_to_goal": 18,
                "yards_to_first": 18,
                "adj_yd_line": 18,
            },
        ),
        ((400869843, 27, 9), {"yards_gained": -5}),
        ((400869843, 27, 10), {"yard_line": 78, "yards_to_goal": 22}),
        ((401237102, 4), {"offense": "Texas A&M", "defense": "Florida"}),
        ((401237102, 4, 8), {"play_number": 5}),
        ((401237102, 4, 9), {"play_number": 6}),
        ((401237102, 4, 10), {"play_number": 7}),
        ((401237102, 4, 11), {"play_number": 8}),
        ((401237102, 4, 12), {"play_number": 9}),
        ((401237102, 4, 13), {"play_number": 10}),
        ((401237102, 4, 14), {"play_number": 11}),
        ((401237102, 4, 15), {"play_number": 12}),
        ((401237102, 4, 16), {"play_number": 13}),
        ((401237102, 4, 17), {"play_number": 14}),
        ((401237102, 4, 18), {"play_number": 15}),
        ((401237102, 4, 29), {"play_number": 16}),
        ((400869850, 26, 15), {"yards_gained": -5}),
        ((401013353, 23, 4), {"yards_gained": -5}),
        ((400869264, 9, 1), {"yards_gained": -5}),
        ((401114260, 11, 5), {"yards_gained": -5}),
        ((401282206, 9, 6), {"yards_gained": -15}),
        ((401405102, 14, 4), {"yards_gained": -15}),
        ((401282189, 6, 7), {"yards_gained": -15}),
        ((401309577, 22, 1), {"yards_gained": -15}),
        ((400548020, 16, 10), {"yards_gained": -5}),
        ((401403927, 9, 3), {"yards_gained": -15}),
        ((400787353, 3, 5), {"yards_gained": -5}),
        ((400869721, 19, 5), {"yards_gained": -15}),
        ((401310733, 6, 8), {"yards_gained": 0}),
        ((401287949, 4, 3), {"yards_gained": -9}),
        ((401309639, 19, 5), {"yards_gained": 0}),
        ((401282215, 26, 10), {"yards_gained": 0}),
        ((401119278, 26, 7), {"yards_gained": 0}),
        ((401121957, 28, 4), {"yards_gained": -10}),
        ((400941829, 25, 2), {"play_type": "Penalty", "yards_gained": -10}),
        ((400869041, 18, 8), {"yards_gained": -9}),
        ((400547743, 21, 3), {"yards_gained": 15}),
        ((401117876, 8, 5), {"yards_gained": 0}),
        ((401022561, 20, 11), {"yards_gained": 15}),
        (
            ((401643724, 22, 15)),
            {
                "yard_line": 25,
                "yards_to_goal": 25,
                "yards_to_first": 25,
                "adj_yd_line": 25,
            },
        ),
    ]
    return conditions_and_updates


def legacy_data_correction_records() -> list[dict[str, object]]:
    """Convert legacy fixes into the canonical approved correction contract."""
    records = []
    for condition, updates in legacy_data_fixes():
        game_id, drive_number, *play_number = condition
        record_key = {"game_id": game_id, "drive_number": drive_number}
        if play_number:
            record_key["play_number"] = play_number[0]
        for field, new_value in updates.items():
            identity = json.dumps(
                {"record_key": record_key, "field": field, "value": new_value},
                sort_keys=True,
            )
            records.append(
                {
                    "correction_id": hashlib.sha256(identity.encode()).hexdigest()[:32],
                    "dataset": "plays",
                    "record_key": record_key,
                    "changed_field": field,
                    "old_value": None,
                    "new_value": json.dumps(new_value),
                    "reason": "Migrated from the reviewed legacy correction set",
                    "source": "legacy_manual_data_fixes",
                    "effective_from": None,
                    "effective_to": None,
                    "approved_by": "repository_legacy_policy",
                    "approved_at": "2026-08-09T00:00:00+00:00",
                }
            )
    return records


def apply_manual_data_fixes(df: pd.DataFrame) -> pd.DataFrame:
    """Apply legacy hardcoded corrections for compatibility readers only."""
    for condition, updates in legacy_data_fixes():
        game_id, drive_number, *play_number_list = condition
        play_number = play_number_list[0] if play_number_list else None

        if play_number is None:
            condition_mask = (df["game_id"] == game_id) & (
                df["drive_number"] == drive_number
            )
        else:
            condition_mask = (
                (df["game_id"] == game_id)
                & (df["drive_number"] == drive_number)
                & (df["play_number"] == play_number)
            )
        if condition_mask.any():
            for col, value in updates.items():
                df.loc[condition_mask, col] = value
    return df


def apply_data_corrections(df: pd.DataFrame, corrections: pd.DataFrame) -> pd.DataFrame:
    """Apply an explicit, versioned long-form correction dataset.

    Corrections are keyed by game and optional drive/play number. Each row changes
    exactly one field, making the old/new values and approval metadata catalogable.
    """
    required = {"record_key", "changed_field", "new_value"}
    missing = required - set(corrections.columns)
    if missing:
        raise ValueError(f"Data corrections are missing fields: {sorted(missing)}")
    result = df.copy()
    for row in corrections.to_dict("records"):
        field = str(row["changed_field"])
        if field not in result.columns:
            continue
        record_key = row.get("record_key", {})
        if isinstance(record_key, str):
            record_key = json.loads(record_key)
        if not isinstance(record_key, dict):
            raise ValueError("Correction record_key must be an object")
        keys = {
            key: row.get(key, record_key.get(key))
            for key in ("game_id", "drive_number", "play_number", "play_id")
        }
        if keys["game_id"] is None:
            raise ValueError("Correction record_key is missing game_id")
        mask = result["game_id"].eq(keys["game_id"])
        for key in ("drive_number", "play_number", "play_id"):
            value = keys[key]
            if value is not None and not pd.isna(value):
                if key not in result.columns:
                    raise ValueError(f"Correction references unavailable key: {key}")
                mask &= result[key].eq(value)
        matches = int(mask.sum())
        if matches == 0:
            continue
        if matches > 1:
            raise ValueError(
                f"Correction for game {keys['game_id']} field {field} matched "
                f"{matches} rows; expected exactly one"
            )
        old_value = row.get("old_value")
        if old_value is not None and not pd.isna(old_value):
            if isinstance(old_value, str):
                try:
                    old_value = json.loads(old_value)
                except json.JSONDecodeError:
                    pass
            actual = result.loc[mask, field].iloc[0]
            if str(actual) != str(old_value):
                raise ValueError(
                    f"Correction old-value mismatch for game {keys['game_id']} "
                    f"field {field}: expected {old_value!r}, got {actual!r}"
                )
        new_value = row["new_value"]
        if isinstance(new_value, str):
            try:
                new_value = json.loads(new_value)
            except json.JSONDecodeError:
                pass
        result.loc[mask, field] = new_value
    return result
