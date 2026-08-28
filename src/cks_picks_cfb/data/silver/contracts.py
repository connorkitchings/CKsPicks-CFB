"""Provider-neutral Silver contracts and dataset specifications."""

from __future__ import annotations

from dataclasses import dataclass


class SilverValidationError(ValueError):
    """Raised when provider data cannot satisfy a canonical Silver contract."""


# Canonical market datasets may only consume provider-native (timestamped)
# captures. legacy_market_references only consumes legacy exports. Every other
# dataset may consume both providers.
DATASET_PROVIDERS: dict[str, tuple[str, ...]] = {
    "market_quotes": ("cfbd", "the_odds_api"),
    "market_snapshots": ("cfbd", "the_odds_api"),
    "legacy_market_references": ("legacy_cfbd_export",),
}

LEGACY_TIMESTAMP_STATUS = "missing_authentic_timestamp"


@dataclass(frozen=True)
class SilverContract:
    dataset: str
    schema_version: str
    required_columns: frozenset[str]
    key_columns: tuple[str, ...]


SILVER_CONTRACTS: dict[str, SilverContract] = {
    "teams": SilverContract(
        "teams", "teams_v1", frozenset({"team_id", "team"}), ("team_id",)
    ),
    "team_aliases": SilverContract(
        "team_aliases",
        "team_aliases_v1",
        frozenset({"provider", "provider_name", "team"}),
        ("provider", "provider_name"),
    ),
    "venues": SilverContract(
        "venues", "venues_v1", frozenset({"venue_id", "name"}), ("venue_id",)
    ),
    "schedule_revisions": SilverContract(
        "schedule_revisions",
        "schedule_revisions_v1",
        frozenset({"season", "game_id", "kickoff_utc"}),
        ("season", "game_id", "captured_at"),
    ),
    "games": SilverContract(
        "games",
        "games_v2",
        frozenset(
            {
                "season",
                "game_id",
                "week",
                "provider_week",
                "kickoff_utc",
                "home_team",
                "away_team",
            }
        ),
        ("season", "game_id"),
    ),
    "schedule_week_policy": SilverContract(
        "schedule_week_policy",
        "schedule_week_policy_v1",
        frozenset(
            {"season", "game_id", "provider_week", "canonical_week", "kickoff_utc"}
        ),
        ("season", "game_id"),
    ),
    "game_outcomes": SilverContract(
        "game_outcomes",
        "game_outcomes_v1",
        frozenset(
            {
                "season",
                "game_id",
                "completed",
                "home_points",
                "away_points",
            }
        ),
        ("season", "game_id"),
    ),
    "plays": SilverContract(
        "plays",
        "plays_v1",
        frozenset({"season", "week", "game_id", "play_id"}),
        ("game_id", "play_id"),
    ),
    "team_game_stats": SilverContract(
        "team_game_stats",
        "team_game_stats_v1",
        frozenset({"season", "week", "game_id", "team"}),
        ("season", "game_id", "team"),
    ),
    "reconciled_team_game": SilverContract(
        "reconciled_team_game",
        "team_game_v1",
        frozenset({"season", "game_id", "team"}),
        ("season", "game_id", "team"),
    ),
    "byplay": SilverContract(
        "byplay",
        "byplay_v1",
        frozenset(
            {
                "season",
                "week",
                "game_id",
                "drive_number",
                "play_number",
                "offense",
                "defense",
            }
        ),
        ("game_id", "drive_number", "play_number"),
    ),
    "drives": SilverContract(
        "drives",
        "drives_v1",
        frozenset(
            {
                "season",
                "week",
                "game_id",
                "drive_number",
                "offense",
                "defense",
            }
        ),
        ("game_id", "drive_number", "offense", "defense"),
    ),
    "source_reconciliation": SilverContract(
        "source_reconciliation",
        "reconciliation_v1",
        frozenset(
            {
                "reconciliation_id",
                "season",
                "game_id",
                "classification",
                "blocking",
                "details",
                "policy_version",
            }
        ),
        ("reconciliation_id",),
    ),
    "market_quotes": SilverContract(
        "market_quotes",
        "market_quotes_v1",
        frozenset({"quote_id", "game_id", "provider", "captured_at"}),
        ("quote_id",),
    ),
    "market_snapshots": SilverContract(
        "market_snapshots",
        "market_snapshots_v1",
        frozenset({"market_snapshot_id", "game_id", "market_captured_at"}),
        ("market_snapshot_id",),
    ),
    "legacy_market_references": SilverContract(
        "legacy_market_references",
        "legacy_market_references_v1",
        frozenset(
            {
                "season",
                "game_id",
                "provider",
                "provider_week",
                "source_capture_id",
                "source_uri",
                "source_sha256",
                "timestamp_status",
                "exact_replay_eligible",
                "grading_eligible",
                "lean_eligible",
            }
        ),
        ("game_id", "provider", "source_capture_id"),
    ),
    "weather_observations": SilverContract(
        "weather_observations",
        "weather_v1",
        frozenset({"game_id", "observed_at"}),
        ("game_id", "observed_at"),
    ),
    "preseason_team_inputs": SilverContract(
        "preseason_team_inputs",
        "preseason_inputs_v1",
        frozenset({"season", "team", "as_of"}),
        ("season", "team", "as_of"),
    ),
    "data_corrections": SilverContract(
        "data_corrections",
        "data_corrections_v1",
        frozenset(
            {
                "correction_id",
                "dataset",
                "record_key",
                "changed_field",
                "old_value",
                "new_value",
                "reason",
                "source",
                "approved_by",
                "approved_at",
            }
        ),
        ("correction_id",),
    ),
}
