"""The season CLI refuses ambiguous, mismatched or uncommitted release operations."""

from __future__ import annotations

import contextlib
import importlib.util
from pathlib import Path

import pytest

from cks_picks_cfb.season import release

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "run_season", ROOT / "scripts/pipeline/run_season.py"
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

RUN_ID = "season-2026-" + "a" * 24
ROLLBACK = ["rollback", "--release-id", RUN_ID, "--decision-ref", "decision-1"]


@pytest.fixture
def git(monkeypatch):
    """Fake git: a clean tree at a fixed HEAD unless ``state["dirty"]``."""
    state = {"dirty": False}

    def check_output(command, text):
        if command[:2] == ["git", "status"]:
            return " M src/file.py\n" if state["dirty"] else ""
        return "f" * 40 + "\n"

    monkeypatch.setattr(cli.subprocess, "check_output", check_output)
    return state


@pytest.fixture
def preview_env(monkeypatch):
    monkeypatch.setenv("CFB_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("CFB_ARTIFACT_ENV", "preview")
    monkeypatch.delenv("PREVIEW_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["prepare", "--through-week", "7"],
        ["status"],
        ["release", "--environment", "preview", "--initial"],
        ["rollback", "--environment", "preview", "--initial"],
        [*ROLLBACK, "--environment", "staging", "--initial"],
    ],
)
def test_incomplete_or_unknown_arguments_exit_with_usage(argv):
    with pytest.raises(SystemExit) as raised:
        cli.main(argv)
    assert raised.value.code == 2


@pytest.mark.parametrize(
    "selection",
    [[], ["--initial", "--expected-previous-release-id", f"preview-{RUN_ID}"]],
    ids=["neither", "both"],
)
def test_initial_and_expected_previous_are_exclusive(git, preview_env, selection):
    with pytest.raises(ValueError, match="choose --initial"):
        cli.main([*ROLLBACK, "--environment", "preview", *selection])


def test_environment_mismatch_is_refused(git, preview_env):
    with pytest.raises(ValueError, match="matching explicit R2 environment"):
        cli.main([*ROLLBACK, "--environment", "production", "--initial"])


@pytest.mark.parametrize("artifact_env", [None, "production"])
def test_rollback_requires_matching_artifact_environment(
    git, preview_env, monkeypatch, artifact_env
):
    if artifact_env is None:
        monkeypatch.delenv("CFB_ARTIFACT_ENV")
    else:
        monkeypatch.setenv("CFB_ARTIFACT_ENV", artifact_env)
    with pytest.raises(ValueError, match="matching explicit R2 environment"):
        cli.main([*ROLLBACK, "--environment", "preview", "--initial"])


def test_release_refuses_a_dirty_tree(git, preview_env):
    git["dirty"] = True
    with pytest.raises(ValueError, match="clean committed code"):
        cli.main([*ROLLBACK, "--environment", "preview", "--initial"])


def test_prepare_refuses_a_dirty_tree(git, preview_env, tmp_path):
    git["dirty"] = True
    with pytest.raises(ValueError, match="clean committed code"):
        cli.main(
            [
                "prepare",
                "--model-manifest",
                "model.json",
                "--revision-manifest",
                "revision.json",
                "--through-week",
                "7",
                "--as-of",
                "2026-10-13T18:00:00Z",
                "--output",
                str(tmp_path),
                "--environment",
                "preview",
            ]
        )


@pytest.mark.parametrize(
    "given, expected",
    [
        (RUN_ID, f"preview-{RUN_ID}"),
        (f"preview-{RUN_ID}", f"preview-{RUN_ID}"),
        (None, None),
    ],
    ids=["bare", "prefixed", "absent"],
)
def test_release_ids_gain_their_environment_prefix(given, expected):
    assert cli.database_release_id(given, "preview") == expected


@pytest.mark.parametrize("given", [f"production-{RUN_ID}", "v5-legacy-run"])
def test_mismatched_or_unknown_release_ids_are_refused(given):
    with pytest.raises(ValueError, match="does not belong|unrecognized"):
        cli.database_release_id(given, "preview")


def test_rollback_passes_database_release_ids(git, preview_env, monkeypatch):
    monkeypatch.setenv("PREVIEW_DATABASE_URL", "postgresql://preview")
    calls = {}

    class Connection:
        def commit(self):
            calls["committed"] = True

    monkeypatch.setattr(
        "psycopg.connect", lambda url: contextlib.nullcontext(Connection())
    )
    monkeypatch.setattr(
        release, "rollback_release", lambda conn, **kwargs: calls.update(kwargs) or {}
    )
    previous = "season-2026-" + "b" * 24
    cli.main(
        [
            *ROLLBACK,
            "--environment",
            "preview",
            "--expected-previous-release-id",
            previous,
        ]
    )
    assert calls["release_id"] == f"preview-{RUN_ID}"
    assert calls["expected_previous_release_id"] == f"preview-{previous}"
    assert calls["committed"] is True


def test_rollback_refuses_another_environments_release_id(git, preview_env):
    with pytest.raises(ValueError, match="does not belong to preview"):
        cli.main(
            [
                "rollback",
                "--release-id",
                f"production-{RUN_ID}",
                "--decision-ref",
                "decision-1",
                "--environment",
                "preview",
                "--initial",
            ]
        )
