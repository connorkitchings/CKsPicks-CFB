# Transformed Drives Schema

This schema describes the drives dataset, which is created by aggregating the processed `byplay` data to the drive level.

**Derived From:** `transformed/plays.md`

## Schema

The key for this dataset is `(game_id, drive_number, offense, defense)`.

```python
[
    "game_id",
    "drive_number",
    "offense",
    "defense",
    "drive_plays",              # Number of countable plays in the drive
    "drive_yards",              # Total yards gained in the drive
    "drive_time",               # Total duration of the drive in seconds
    "drive_start_period",       # Quarter the drive started
    "drive_end_period",         # Quarter the drive ended
    "start_time_remain",        # Time remaining in game when drive started
    "end_time_remain",          # Time remaining in game when drive ended
    "start_yards_to_goal",      # Yard line at the start of the drive
    "end_yards_to_goal",        # Yard line at the end of the drive
    "is_eckel_drive",           # Flag indicating if the drive was an "Eckel" drive
    "had_scoring_opportunity",  # Flag indicating if the drive had a 1st down inside the opponent's
                                # 40-yard line
    "points",                   # Points scored on the drive
    "points_on_opps",            # Points scored on drives that had a scoring opportunity
    "is_successful_drive",      # Flag indicating if the drive was successful
    "is_busted_drive",          # Flag indicating if the drive was a bust
    "is_explosive_drive",       # Flag indicating if the drive was explosive
]
```
