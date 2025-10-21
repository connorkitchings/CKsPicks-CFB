# Knowledge Base

This document is a curated collection of reusable patterns, solutions, code snippets, and valuable
insights discovered during the project. Its purpose is to build "institutional memory" and accelerate
future development.

Use the format `[KB:PatternName]` to reference entries from other documents.

> **Note:** The source tree was flattened; modules formerly referenced as `src/cfb_model/...` now live directly under `src/...`.

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

## `[KB:AnalysisCLI]`

- **Context**: Multiple standalone analysis scripts (hit rates, thresholds, segmentation) created maintenance overhead.
- **Pattern**: Use `scripts/analysis_cli.py` with subcommands (`summary`, `segments`, `split`, `confidence`) to run those tasks from one entrypoint.
- **Usage**: `uv run python scripts/analysis_cli.py summary reports/2024/CFB_season_2024_all_bets_scored.csv`
- **Discovered In**: Refactor (2025-10-17)

---

## `[KB:TrainingCLI]`

- **Context**: Model training scripts proliferated (baseline, differential, experiments) with inconsistent flags.
- **Pattern**: Invoke `scripts/training_cli.py` subcommands (`train`, `differential`, etc.) to keep workflows consistent.
- **Usage**: `uv run python scripts/training_cli.py train --train-years 2019,2021,2022,2023 --test-year 2024`
- **Discovered In**: Refactor (2025-10-17)

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

---

## `[KB:LocalStorageWriteSignature]`

- **Context**: Writing data to a partitioned directory using the `LocalStorage` backend fails with a `TypeError` for an unexpected keyword argument.
- **Pattern**: The `LocalStorage.write()` method expects the data as a list of records (`df.to_dict(orient="records")`) and the partitioning scheme as a `Partition` object (from `cfb_model.data.storage.base`), not as a dictionary passed to a `partition_cols` argument.
- **Usage**: `from cfb_model.data.storage.base import Partition; partition = Partition({"year": Y, "week": W}); records = df.to_dict('records'); storage.write("entity", records, partition=partition)`
- **Discovered In**: `[LOG:2025-09-29]`

---

## `[KB:EntityPartitioningSpecificity]`

- **Context**: A data loading operation using `LocalStorage.read_index` fails with a "No data found" error, even though the data exists.
- **Pattern**: This often happens when the read filter is more specific than the actual directory structure. For example, the `games` entity is partitioned only by `year`, not by `week`. Attempting to read with a filter of `{"year": Y, "week": W}` will fail. The correct approach is to read with the broader, correct partition filter (`{"year": Y}`) and then filter the resulting DataFrame in memory.
- **Usage**: Instead of `storage.read_index("games", {"year": Y, "week": W})`, use `df = pd.DataFrame.from_records(storage.read_index("games", {"year": Y})); weekly_df = df[df["week"] == W]`.
- **Discovered In**: `[LOG:2025-09-29]`

---

## `[KB:PYTHONPATH-ISSUES]`

- **Context**: When running scripts from the command line that are part of a package, `ModuleNotFoundError` can occur.
- **Pattern**: It's crucial to ensure that the package's root directory is in the `PYTHONPATH`. This can be done by running the script as a module (`-m`), setting the `PYTHONPATH` environment variable, or by adding the path to `sys.path` within the script itself.
- **Usage**: `python3 -m src.cfb_model.scripts.generate_weekly_bets_clean` or `sys.path.insert(0, './src')`
- **Discovered In**: `[LOG:2025-09-30]`

---

## `[KB:ScalingForConvergence]`

- **Context**: An iterative model like `HuberRegressor` fails to converge, even after increasing `max_iter`.
- **Pattern**: The issue can often be resolved by scaling the input data. Wrapping the model in a `sklearn.pipeline.Pipeline` with a `StandardScaler` is a robust way to ensure data is scaled before fitting the model, which can significantly improve convergence.
- **Usage**: `pipeline = Pipeline([('scaler', StandardScaler()), ('model', HuberRegressor())])`
- **Discovered In**: `[LOG:2025-10-01]`

---

## `[KB:LargePrintsAndStreams]`

- **Context**: An automated script fails with a non-standard error like "invalid chunk" or "missing finish reason".
- **Pattern**: This can be caused by printing an extremely large, wide DataFrame or other large string to standard output. The process running the script may not be able to handle the large, uninterrupted block of text in the output stream, leading to corruption. Removing or modifying the large print statement can resolve the issue.
- **Usage**: Avoid `print(df.to_string())` on very wide DataFrames in automated scripts. If you need to inspect data, print a subset of columns or use a logger.
- **Discovered In**: `[LOG:2025-10-01]` 

## `[KB:EnsembleConfidenceFilter]`

- **Context**: A simple ensemble of models did not significantly improve performance or reduce variance. A method was needed to leverage the ensemble to improve bet selection.
- **Pattern**: Calculate the standard deviation of the predictions across all models in the ensemble for a given game. Use this standard deviation as a measure of the ensemble's "confidence" or agreement. Filter out bets where the standard deviation exceeds a specified threshold.
- **Usage**: Add a `--spread-std-dev-threshold` and `--total-std-dev-threshold` to the prediction script. In the betting policy, only consider bets where `prediction_std_dev <= threshold`.
- **Discovered In**: `[LOG:2025-10-01]`

---

## `[KB:UpstreamDependencyOrder]`

- **Context**: A script that consumes the output of another script fails with a key error, indicating a missing column.
- **Pattern**: This occurs when an upstream (producer) script is modified to change its output format, but is not re-run before executing the downstream (consumer) script. The consumer script fails because it receives an input file in the old, unexpected format. Always ensure the full pipeline is run in order after modifying the output of any script.
- **Usage**: After changing the output format of `generate_weekly_bets_clean.py`, it must be run again before `score_weekly_picks.py` is run.
- **Discovered In**: `[LOG:2025-10-03]`

---

## `[KB:FeatureSelectionValidation]`

- **Context**: A systematic, multi-stage feature selection process (filtering, embedded, and wrapper methods) was executed to reduce the feature set and potentially improve model performance.
- **Pattern**: The models trained on the smaller, selected feature set resulted in a lower hit rate (52.3%) on the holdout season compared to the models trained on the full feature set (54.6%). The changes were subsequently reverted.
- **Learning**: Feature selection is not a guaranteed improvement. It is a hypothesis that must be tested. Always validate the performance of models trained on a reduced feature set against the performance of models trained on the full set. A larger, and potentially noisier, set of features may contain more collective predictive power for an ensemble than a smaller, more refined set.
- **Discovered In**: `[LOG:2025-10-07/01]`

---

## `[KB:IsolateWithDiagnosticScript]`

- **Context**: A process is hanging or failing due to an issue with an external service (e.g., SMTP, API) or complex configuration (e.g., credentials in a .env file), making it difficult to debug within the main application.
- **Pattern**: Create a small, temporary, self-contained script that does nothing but connect to the external service or load the specific configuration in question. This isolates the problem from the main application's logic, allowing for quick and focused debugging.
- **Usage**: To debug a hanging SMTP login, create a `check_login.py` script that only loads credentials from the `.env` file and attempts to authenticate with the SMTP server, printing clear success or failure messages.
- **Discovered In**: `[LOG:2025-10-03]`

---

## `[KB:SchemaAwareParsing]`

- **Context**: A script processing generated reports fails due to schema changes between different years of data.
- **Pattern**: When reading generated files like `_scored.csv`, do not assume a fixed schema. Instead, programmatically check for the presence of expected columns and handle different versions of the schema gracefully. For example, if `home_points` is missing, try to derive it from other columns like `Spread Result` and `Total Result`.
- **Usage**: Before accessing a column, check if it exists in the DataFrame's columns. If not, try to derive it from other available columns.
- **Discovered In**: `[LOG:2025-10-04]`

---

## `[KB:ToolingIndentationIssues]`

- **Context**: A script fails with an `IndentationError` after being modified by a file writing tool.
- **Pattern**: Some file writing tools might introduce incorrect indentation, especially when replacing blocks of code. It is important to carefully review the indentation of the modified code and the surrounding lines. If the error persists, it might be necessary to reconstruct the file from a known good version and re-apply the changes with correct indentation.
- **Usage**: After using a file writing tool, visually inspect the indentation of the modified file or run a linter to catch any indentation errors.
- **Discovered In**: `[LOG:2025-10-07/03]`

---

## `[KB:PipelineDependency]`

- **Context**: A script fails because an upstream data processing step was not executed or completed correctly, leading to missing or outdated intermediate data.
- **Pattern**: Ensure all intermediate data generation steps (e.g., `preagg` for `team_game` data) are explicitly run or verified before downstream steps that depend on them (e.g., `cache_weekly_stats`). The weekly pipeline should include all necessary data preparation steps.
- **Usage**: If `cache_weekly_stats` fails due to missing `team_game` data, run `scripts/cli.py aggregate preagg` first.
- **Discovered In**: `[LOG:2025-10-07/03]`

---

## `[KB:EmailImageEmbedding]`

- **Context**: Embedding team logos or other images directly into HTML emails for visual appeal and branding.
- **Pattern**: Use `MIMEMultipart("related")` as the main message type. For each image, read its binary data, create a `MIMEImage` object, add a unique `Content-ID` header (e.g., `<logo_team_name>`), and attach it to the `MIMEMultipart("related")` message. In the HTML content, reference the image using `src="cid:logo_team_name"`.
- **Usage**: In `publish_picks.py`, collect unique team names, load their logos, create `MIMEImage` objects, and pass them to `send_email`. In `templates/email_weekly_picks.html`, use `<img src="cid:{{ r.team_logo_cid }}">`.
- **Discovered In**: `[LOG:2025-10-07/03]`

---

## `[KB:LintingIteration]

---

  - `[KB:HYDRA-INTERPOLATION]` Older versions of Hydra might not support the `${env:VAR}` syntax for environment variable interpolation. Use `${oc.env:VAR}` instead.
  - `[KB:PANDAS-COLUMN-NAMES]` Be aware that the column name for the game identifier in the raw `games` data is `id`, not `game_id`.
  - `[KB:LIST-DIRECTORY-IGNORES]` The `list_directory` tool respects `.gitignore` by default. Use `file_filtering_options=ListDirectoryFileFilteringOptions(respect_git_ignore=False)` to disable this behavior.
- **MLflow**
## `[KB:MLflowNestedRuns]`

- **Context**: When training an ensemble of models, it's useful to track both the performance of the overall ensemble and the individual performance of each component model.
- **Pattern**: Use nested MLflow runs. A parent run can track the overall experiment (e.g., ensemble performance, data versions), while nested child runs track the parameters, metrics, and artifacts for each individual model in the ensemble.
- **Usage**: `with mlflow.start_run(run_name="Parent_Run"): ... with mlflow.start_run(run_name="Child_Model_1", nested=True): ...`
- **Discovered In**: `[LOG:2025-10-10/02]``

- **Context**: Resolving linting errors, especially those related to variable naming (`N806`) and undefined names (`F821`), often requires multiple iterations of fixes and re-checks.
- **Pattern**: When renaming variables (e.g., from `X` to `x`), ensure all usages of the old variable name are also updated. `ruff check --fix` can help with some issues, but manual `replace` calls might be necessary for all occurrences. Re-run lint checks after each set of changes to catch cascading errors.


---

## `[KB:HydraMultiRunConfig]` *(archived for future migration)*

- **Context**: Planned Hydra + Optuna integration (see roadmap) will likely require passing the search space via CLI in multirun mode.
- **Pattern**: If/when Hydra is reintroduced, prefer defining the Optuna search space with the `+` CLI syntax to avoid sweeper `AssertionError`s.
- **Usage**: Example command (when Hydra is in place): `uv run python scripts/optimize_hyperparameters.py -m "+model.alpha=choice(0.1,0.5,1.0)"`
- **Status**: Hydra is currently paused; retain this note for the eventual migration.
- **Discovered In**: `[LOG:2025-10-11]`

---

## `[KB:ShellQuoting]`

- **Context**: Passing complex arguments with parentheses or other special characters to a shell command can cause syntax errors.
- **Pattern**: Always quote complex arguments to prevent the shell from interpreting them.
- **Usage**: `uv run python script.py -m 'model.param=choice(a,b,c)'`
- **Discovered In**: `[LOG:2025-10-11]`

---

## `[KB:ImputeNaNs]`

- **Context**: Scikit-learn models like Ridge regression do not accept `NaN` values in the input data.
- **Pattern**: Before training a model, ensure that any `NaN` values in your feature matrix are handled. A simple strategy is to fill them with 0 using `.fillna(0)`.
- **Usage**: `x_train = train_df[feature_list].astype(float).fillna(0)`
- **Discovered In**: `[LOG:2025-10-11]`

---

## `[KB:EXPLICIT-DATA-ROOT]`

- **Context**: Scripts were silently creating a local `data/` directory when an environment variable for the data root was not properly loaded, leading to confusion and validation errors against the wrong data source.
- **Pattern**: Modify storage classes (like `LocalStorage`) to remove automatic directory creation (`mkdir(exist_ok=True)`). Instead, the class should assume the path provided to it exists and fail explicitly with a `StorageError` or `FileNotFoundError` if it does not. This makes path resolution failures loud and immediate, preventing the pipeline from running with an incorrect configuration.
- **Usage**: In `src/utils/local_storage.py`, the `__init__` method was changed to remove the `root.mkdir()` call and only check `if not root.is_dir()`.
- **Discovered In**: `[LOG:2025-10-18/03]`

---

## `[KB:MLFLOW-CONFIG]`

- **Context**: When running MLflow, the default tracking URI is `mlruns`. This can be changed to a different location.
- **Pattern**: Use `mlflow.set_tracking_uri()` to set the tracking URI to a different location. This is useful for organizing project outputs.
- **Usage**: `mlflow.set_tracking_uri("file:./artifacts/mlruns")`
- **Discovered In**: `[LOG:2025-10-19/01]`

---

## `[KB:GIT-ARTIFACTS]`

- **Context**: Directories containing generated artifacts and experiment tracking data (e.g., `mlruns`, `artifacts`) should not be committed to the git repository.
- **Pattern**: Add the paths to these directories to the `.gitignore` file.
- **Usage**: Add `/artifacts/` and `/mlruns/` to the `.gitignore` file.
- **Discovered In**: `[LOG:2025-10-19/01]`

---

## `[KB:UV-RUN-MODULE]`

- **Context**: When a package's executable is not found in the path, it can be run as a module.
- **Pattern**: Use `uv run python -m <module_name>` to run the module.
- **Usage**: `uv run python -m mkdocs build --quiet`
- **Discovered In**: `[LOG:2025-10-19/01]`

---

## `[KB:PERFORMANCE-BOTTLENECK]`

- **Context**: A time-series validation script was unacceptably slow, taking hours to run.
- **Pattern**: The cause was identified as a feature generation function that recalculated complex stats (like opponent adjustments) from raw data on every iteration. The solution is to ensure such processes use pre-calculated, cached data. For this project, the `walk_forward_validation.py` script was refactored to load weekly data from the `processed/team_week_adj/` cache instead of regenerating it.
- **Usage**: When building iterative validation tools, always check if intermediate, pre-calculated data can be used instead of re-running expensive calculations in a loop.
- **Discovered In**: `[LOG:2025-10-20/05]`

---

## `[KB:REFACTORING-IMPORTS]`

- **Context**: Deleting a function caused `ImportError`s in multiple, seemingly unrelated parts of the application, which were only caught by the test suite.
- **Pattern**: When a function is removed or refactored, it is crucial to perform a project-wide search for its usages to prevent leaving dangling imports. The test suite, especially tests that simply try to import all modules (like `tests/test_imports.py`), is an invaluable safety net for catching these errors.
- **Usage**: Before considering a refactoring task complete, run the full test suite to ensure no import errors have been introduced.
- **Discovered In**: `[LOG:2025-10-20/05]`

---

## `[KB:TYPER-CLI-STRUCTURE]`

- **Context**: A main CLI script that aggregates other Typer apps (e.g., `scripts/cli.py`) failed with an `AttributeError` because it could not find the `app` object in a sub-command module.
- **Pattern**: If a Python script defines a Typer application and is also intended to be imported as a module by another script, it must maintain its top-level `app = typer.Typer()` definition. Accidentally removing this during a refactor will break the import chain.
- **Usage**: Ensure that any script providing a Typer app for aggregation defines the `app` object at the module level.
- **Discovered In**: `[LOG:2025-10-20/05]`