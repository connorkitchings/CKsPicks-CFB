# Hydra in Practice — A Concise Guide

Hydra is a Python framework for composing hierarchical configs, overriding them from the command line, and launching single or multi-run jobs. It builds on OmegaConf and is great for ML experiments, research apps, and any project with lots of knobs.

## Project Setup (cfb_model)

This repository manages dependencies with `uv`. Hydra (and the Optuna sweeper plugin) are already declared in `pyproject.toml`, so you only need to install the full toolchain once:

```bash
uv sync --extra dev
source .venv/bin/activate  # required while the environment investigates the `uv run` panic
```

After activation, all Hydra-aware scripts can be launched with `uv run` or the Python executable in `.venv/bin/python`. Avoid mixing in ad-hoc `pip install hydra-core`, which can create duplicate site-packages and drift from the lockfile.

### Repository Quick Start

Hydra looks for configuration files under `conf/`:

```
conf/
  config.yaml                 # top-level defaults (model + sweeper selection, Hydra dirs)
  model/                      # per-model configuration (spread, totals, points-for variants)
  hydra/sweeper/params/       # Optuna search spaces keyed by model name
  sweeper/optuna.yaml         # global Optuna sweeper settings (study name, direction, n_trials)
```

- `conf/config.yaml` composes the active model config and the matching sweeper parameter bundle (`hydra/sweeper/params: spread_elastic_net` by default). It also routes outputs into `artifacts/outputs/...` to keep Hydra artifacts with other project data.
- Files in `conf/model/` use `_target_`-free scalar configs to parameterize sklearn/xgboost estimators. Each file exposes `.type`, `.name`, and `.params` so that the optimization script can clone and tune the model.
- Files in `conf/hydra/sweeper/params/` define the Optuna search space for each model. For example, `spread_elastic_net.yaml` provides log-scaled `alpha` and continuous `l1_ratio`.
- `conf/sweeper/optuna.yaml` contains shared sweeper defaults (seed, number of trials, concurrency) and is referenced through the Defaults List.

Hydra entrypoints live in `scripts/`:

- `scripts/optimize_hyperparameters.py` tunes a selected model with Optuna + MLflow logging.
- `scripts/walk_forward_validation.py` performs walk-forward evaluation using the current defaults, logging metrics to MLflow.
- Traditional CLI wrappers (`scripts/training_cli.py`, etc.) keep argparse semantics for operations that are not yet Hydra-native.

## Your First Hydra App

**conf/config.yaml**

```yaml
db:
  driver: mysql
  user: omry
  password: secret
```

**app.py**

```python
from omegaconf import DictConfig, OmegaConf
import hydra

@hydra.main(version_base=None, config_path="conf", config_name="config")
def main(cfg: DictConfig):
    print(OmegaConf.to_yaml(cfg, resolve=True))

if __name__ == "__main__":
    main()
```

**Run:**

```bash
python app.py
python app.py db.user=alice db.driver=postgresql
```

Hydra finds `conf/`, loads `config.yaml`, and applies CLI overrides.

## Override Grammar (CLI & Programmatic)

Common moves:

- **Change a value:** `trainer.max_epochs=10`
- **Add a new key:** `++new_flag=true`
- **Delete a key:** `~obsolete_key`

Lists/dicts, quoting, casting, ranges, and functions are supported (see "extended syntax").

**Tip:** `--cfg job` shows the full composed config; add `--resolve` to evaluate interpolations. See Debug & Inspect below.

## Config Groups & the Defaults List

Organize swappable options as config groups:

```
conf/
  db/
    mysql.yaml
    postgresql.yaml
  server/
    apache.yaml
    nginx.yaml
  config.yaml
```

**db/mysql.yaml**

```yaml
# @package _group_
driver: mysql
user: root
```

**config.yaml**

```yaml
defaults:
  - db: mysql
  - server: nginx
  - _self_

debug: false
```

**Select alternatives:**

```bash
python app.py db=postgresql server=apache
```

The Defaults List controls which configs compose into the final object and in what order. Use `_self_` to decide whether a file's own values override or get overridden by its included defaults. Use `override` to change a group selection later; and you can override group choices from the CLI (`db=sqlite`).

## Multi-run Sweeps

Run a grid of configs locally:

```bash
# CLI switch
python app.py --multirun db=mysql,postgresql schema=warehouse,support

# or via mode
python app.py hydra.mode=MULTIRUN db=mysql,postgresql schema=warehouse,support
```

You can also define the sweep in config:

```yaml
# in config.yaml
hydra:
  sweeper:
    params:
      db: mysql,postgresql
      schema: warehouse,support,school
```

More sweep types: `x=range(1,10)`, `name=glob(*)`, `name=glob(*,exclude=foo*)`. Plugins provide smarter sweepers (e.g., Ax) and parallel launchers (e.g., Joblib).

## Running Project Scripts

Stay in the repository root so the relative `config_path="../conf"` used by the decorators resolves correctly:

```bash
# Optuna sweep for the spread Elastic Net (uses conf/hydra/sweeper/params/spread_elastic_net.yaml)
uv run python scripts/optimize_hyperparameters.py model=spread_elastic_net hydra/sweeper/params=spread_elastic_net

# Points-for ridge sweep with a different parameter group
uv run python scripts/optimize_hyperparameters.py model=points_for_ridge hydra/sweeper/params=points_for_ridge data.slice_path=data/processed/points_for/season_2024.csv

# Walk-forward validation with alternate adjustment depths
uv run python scripts/walk_forward_validation.py data.adjustment_iteration_offense=1 data.adjustment_iteration_defense=3
```

Helpful overrides:

- `model=<name>` switches the model configuration under `conf/model/`.
- `hydra/sweeper/params=<name>` swaps in a different Optuna search space.
- `hydra.sweeper.n_trials=40` increases trial budget; `hydra.sweeper.n_jobs=-1` parallelizes locally.
- `data.train_years=[2018,2019,2021,2022,2023]` provides explicit year lists (pay attention to YAML list syntax).

Run `uv run python scripts/optimize_hyperparameters.py --cfg job --resolve` to inspect the composed config before launching the sweep.

## Output Directories & Working Dir

`conf/config.yaml` directs Hydra outputs into `artifacts/outputs/${now:%Y-%m-%d}/`. Each run (or Optuna trial) lands in a subfolder named after the model and timestamp:

```
artifacts/outputs/2025-10-22/
  elastic_net_10-51-50_0/
    .hydra/
      config.yaml        # composed config for the trial
      hydra.yaml         # Hydra's runtime config
      overrides.yaml     # CLI + Defaults overrides that produced this run
    optimization_results.yaml  # (if emitted by the script)
    stdout.log
```

Access the runtime directory from code when you need to persist artifacts alongside the trial:

```python
from hydra.core.hydra_config import HydraConfig
run_dir = HydraConfig.get().runtime.output_dir
```

If your script depends on the working directory, opt in to Hydra's chdir behavior:

```bash
uv run python scripts/optimize_hyperparameters.py hydra.job.chdir=true
```

### Managing Sweep Outputs

- Group trials more tightly by updating `hydra.sweep.subdir` in the CLI, e.g., `hydra.sweep.subdir=${model.name}/${now:%H-%M-%S}_${hydra.job.num}` to bucket runs by model.
- Summaries such as MLflow metrics and Optuna best parameters live in each run directory (`optimization_results.yaml`, `metrics.csv`, etc.). Periodically aggregate them into a single CSV using a quick helper script or notebook that scans `artifacts/outputs/<date>/**/optimization_results.yaml`.
- Clean up stale run folders with `find artifacts/outputs -mindepth 2 -maxdepth 2 -mtime +14 -print` (and remove once verified) to keep the artifact tree manageable.
- For long sweeps, consider setting `hydra.sweeper.storage=sqlite:///path/to/study.db` in `conf/sweeper/optuna.yaml` so trial metadata persists outside the run folders.

## Extending Sweeper Parameter Coverage

To add a new search space or modify an existing one:

1. Create or edit `conf/hydra/sweeper/params/<model_name>.yaml`:

   ```yaml
   model.params.alpha: tag(log, interval(0.001, 1.0))
   model.params.l1_ratio: interval(0.1, 0.95)
   ```

2. Reference the parameter group from the command line (`hydra/sweeper/params=<model_name>`) or by updating the Defaults List in `conf/config.yaml`.
3. Keep the parameter keys aligned with `model.params` in the corresponding `conf/model/<model_name>.yaml` file so Hydra can inject trial values without errors.
4. When introducing new model configs, add both the model file and a matching parameter group to maintain sweep coverage.

## Logging

Hydra configures Python logging for you (INFO to console and file). Make loggers verbose with `hydra.verbose=true` or `hydra.verbose=[__main__,hydra]`. Disable with `hydra/job_logging=disabled`.

## Structured Configs (Type-safe Configs)

Describe your schema with dataclasses:

```python
from dataclasses import dataclass
from hydra.core.config_store import ConfigStore

@dataclass
class DB:
    driver: str = "mysql"
    user: str = "root"
    timeout: int = 10

cs = ConfigStore.instance()
cs.store(name="db_schema", node=DB)
```

You can associate structured schemas with YAML files and get runtime validation + IDE type hints. OmegaConf provides the underlying typed containers.

## Instantiating Objects from Config

Hydra can build objects directly from config using `_target_`:

**conf/model/resnet.yaml**

```yaml
_target_: torchvision.models.resnet18
pretrained: false
num_classes: 10
```

**Python**

```python
from hydra.utils import instantiate
model = instantiate(cfg.model)  # calls the target with the params
```

Use `instantiate()` for objects and `call()` for functions. You can control recursion with `_recursive_` and pass `_convert_` to control how containers are converted.

## Compose API (No @hydra.main)

If your entry point can't use the decorator (e.g., notebooks, unit tests, libraries), use the Compose API:

```python
from hydra import compose, initialize
from omegaconf import OmegaConf

with initialize(version_base=None, config_path="conf", job_name="demo"):
    cfg = compose(config_name="config", overrides=["db=postgresql","db.user=${env:USER}"])
print(OmegaConf.to_yaml(cfg, resolve=True))
```

Hydra auto-detects callers (scripts, modules, tests, notebooks). In notebooks specifically, prefer Compose API.

**Note:** Compose API differs from `@hydra.main` in lifecycle and what Hydra internals are initialized; use it when you must, otherwise prefer `@hydra.main`.

## Debug & Inspect

- **Show the composed config:** `--cfg job`, or `--cfg hydra`, or `--cfg all`
- **Show the Defaults Tree / final Defaults List:** `--info defaults-tree` / `--info defaults`
- **Add `--resolve`** to evaluate interpolations when printing configs
- **Enable tab completion** for groups/keys/values (`--hydra-help` prints setup; supports Bash, zsh, Fish)

## Packages & Namespacing

Use `# @package` at the top of a config to control where its keys land in the final object:

```yaml
# @package _group_         # default for config-group files in new versions
# @package _global_        # place keys at root
# @package db.replica      # place under db.replica
```

This keeps large trees tidy and avoids key collisions.

## Plugins (When You're Ready)

Hydra is extensible via plugins for:

- **Sweepers** (Ax, Optuna, etc.)
- **Launchers** (Joblib, Ray, Slurm/Submitit)
- **SearchPath/ConfigSource** (load configs from custom locations)

Install a plugin and select it via `hydra/launcher=...` or `hydra/sweeper=...`.

## OmegaConf Power-ups (Used by Hydra)

- **Interpolations & resolvers:** reference other keys (`${db.user}`) or register custom resolvers for logic (e.g., `${add:1,2,3}` after `OmegaConf.register_new_resolver("add", ...)`)
- **Structured configs:** dataclasses with runtime type safety

## Project Layout You Can Copy

```
your_project/
  conf/
    config.yaml           # defaults + top-level tweaks
    db/
      mysql.yaml
      postgresql.yaml
    model/
      resnet.yaml
      efficientnet.yaml
    experiment/
      baseline.yaml
      fast.yaml
  app.py
```

**Run a baseline:**

```bash
python app.py +experiment=baseline
```

**Switch DB:**

```bash
python app.py db=postgresql
```

**Sweep models × experiments:**

```bash
python app.py -m model=resnet,efficientnet experiment=baseline,fast
```

(Uses groups + Defaults List + multi-run.)

## Handy Snippets

**Access Hydra's output dir in code:**

```python
from hydra.core.hydra_config import HydraConfig
out = HydraConfig.get().runtime.output_dir
```

**Write artifacts in the run dir even if chdir=False:**

```python
from hydra.utils import to_absolute_path
open(to_absolute_path("metrics.json"), "w").write("{}")
```

**Make a logger "debuggy" without code changes:**

```bash
python app.py hydra.verbose=[__main__,hydra]
```

## Common Gotchas

- If a key doesn't exist, use `++new.key=value` to add it (plain `key=value` will error in strict schemas)
- Order matters in the Defaults List; `_self_` controls whether a file's own values override included ones
- Prefer `instantiate()` with `_target_` for creating objects from config (models, optimizers, datasets)
- In ≥1.2, Hydra doesn't chdir by default; set `hydra.job.chdir=True` if you depend on that behavior

## Further Reading (Official Docs)

- Getting started / tutorial pages: https://hydra.cc/docs/intro/
- Running apps: multi-run, logging, output dirs
- Reference: override grammar, Defaults List, packages
- Structured configs & Compose API
