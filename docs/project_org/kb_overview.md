# Knowledge Base

This document is a curated collection of reusable patterns, solutions, code snippets, and valuable
insights discovered during the project. Its purpose is to build "institutional memory" and accelerate
future development.

Use the format `[KB:PatternName]` to reference entries from other documents.

---

## `[KB:DataStoragePattern]`

- **Context**: Efficient and organized storage of raw and processed College Football Data API data locally.
- **Pattern**: Both raw and processed datasets are stored in CSV format for easier inspection and
   portability. Data is partitioned by `year`, `week`, and `game_id` for plays and plays-derived
   outputs; by `year` for other entities. Folder names are simplified (e.g., `2024/1/401628319`).
- **Usage**: The `LocalStorage` class handles the read/write operations and manages the folder
  structure. Ingesters and aggregations use this storage backend with `file_format="csv"`.
- **Discovered In**: `[LOG:2025-08-14_02]`

---

## `[KB:PythonModuleExecution]`

- **Context**: A script inside a Python package fails with an
  `ImportError: attempted relative import with no known parent package` because it is being run as
  a top-level file.
- **Pattern**: Run the script as a module from the project's root directory using the `-m` flag.
  This allows the Python interpreter to correctly recognize the package structure and resolve
  relative imports.
- **Usage**: Instead of `python src/cfb_model/data/validation.py`, use `python -m src.cfb_model.data.validation`.
- **Discovered In**: `[LOG:2025-08-15]`

---

## `[KB:DataframeColumnTrace]`

- **Context**: Debugging a pandas pipeline where necessary columns (e.g., for logging) are missing
in later stages.
- **Pattern**: Instead of passing columns through every transformation step (where they might be
  dropped), create a lookup map (e.g., a dictionary) from the initial, raw DataFrame. Use this map
  in later stages to retrieve the necessary data via a common key like `game_id`.
- **Usage**: `game_to_teams_map = raw_df[['game_id', 'home', 'away']].drop_duplicates().set_index('game_id').to_dict('index')`
- **Discovered In**: `[LOG:2025-08-15]`

---

## `[KB:RuffLintConfigPolicy]`

- **Context**: Notebook code churn and long CLI/docstrings generate noisy lint failures.
- **Pattern**: Exclude notebooks from lint (extend-exclude + force-exclude) and ignore E501 globally.
- **Usage**: Configure in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`.
- **Discovered In**: `[LOG:2025-09-05]`

---

## `[KB:DeepValidationThresholds]`

- **Context**: Comparing processed team_game metrics to CFBD advanced box score data.
- **Pattern**: Adopt absolute thresholds: plays WARN>3/ERROR>8; ypp WARN>0.20/ERROR>0.50; sr WARN>0.02/ERROR>0.05.
- **Usage**: See `validate_team_game_vs_boxscore` in `src/cfb_model/data/validation.py`.
- **Discovered In**: `[LOG:2025-09-05]`

---

## `[KB:TestWithSyntheticData]`

- **Context**: Writing unit tests for data transformation pipelines without requiring access to a full dataset.
- **Pattern**: Use small, synthetic `pandas` DataFrames to create targeted test cases that verify specific logic and edge cases (e.g., empty inputs, specific value calculations).
- **Usage**: See `tests/test_aggregations_core.py` for examples.
- **Discovered In**: `[LOG:2025-09-22]`

---

## `[KB:DirectScriptImports]`

- **Context**: A script in a subdirectory (e.g., `scripts/`) fails with `ModuleNotFoundError` when trying to import from a sibling directory (e.g., `src/`).
- **Pattern**: To make the script runnable directly, insert the path to the parent of the source directory (e.g., `src/`) at the beginning of `sys.path`.
- **Usage**: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))`
- **Discovered In**: `[LOG:2025-09-22]`

---

## `[KB:ScopedDataLoading]`

- **Context**: A script that reads partitioned data is unexpectedly slow, taking several minutes to load data for even a small query.
- **Pattern**: The root cause is often an inefficient data loading function that scans a large number of directories and files. Instead of loading data for a whole year when only a week is needed, ensure the read function is filtered as specifically as possible (e.g., by both `year` and `week`). This drastically reduces I/O and improves performance.
- **Usage**: Modify `read_index("games", {"year": Y})` to `read_index("games", {"year": Y, "week": W})` to limit the file system scan to the relevant partition.
- **Discovered In**: `[LOG:2025-09-25]`

---

## `[KB:DebugByAddition]`

- **Context**: A data processing pipeline is filtering out all data, but the reason is not obvious from the final output.
- **Pattern**: Modify the script that generates the intermediate data file to include the columns that are being used in the filtering logic. By inspecting the intermediate file with these diagnostic columns, you can quickly identify why rows are being excluded.
- **Usage**: To debug a betting policy that filters based on `games_played`, modify the prediction script to include the `home_games_played` and `away_games_played` columns in the output CSV.
- **Discovered In**: `[LOG:2025-09-25]`
