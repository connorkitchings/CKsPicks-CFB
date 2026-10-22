"""Keep the environment examples honest: no values, no stale names."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [ROOT / ".env.example", ROOT / "web" / ".env.example"]
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".mjs", ".sh", ".yml", ".yaml", ".json"}
# Names assembled at runtime (f"{prefix}_BUCKET"); the literal prefixes are checked instead.
DYNAMIC_R2 = re.compile(
    r"CFB_R2_(PREVIEW_|LAB_|LAB_SOURCE_)?(BUCKET|ACCOUNT_ID|ACCESS_KEY|SECRET_KEY|ENDPOINT)"
)
ASSIGNMENT = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


def _assignments(path: Path) -> list[tuple[str, str]]:
    return [
        (match.group(1), match.group(2))
        for line in path.read_text().splitlines()
        if (match := ASSIGNMENT.match(line))
    ]


def _tracked_sources() -> str:
    files = subprocess.run(
        ["git", "ls-files", "src", "scripts", "web", "tests", "Makefile", ".github"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return "\n".join(
        (ROOT / name).read_text(errors="ignore")
        for name in files
        if (ROOT / name).is_file()
        and ((ROOT / name).suffix in SOURCE_SUFFIXES or name == "Makefile")
        and not name.endswith(("package-lock.json", "test_env_example.py"))
    )


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: str(p.relative_to(ROOT)))
def test_example_has_no_values(path: Path) -> None:
    filled = [name for name, value in _assignments(path) if value.strip()]
    assert _assignments(path)
    assert filled == []


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: str(p.relative_to(ROOT)))
def test_example_has_no_stale_names(path: Path) -> None:
    sources = _tracked_sources()
    stale = [
        name
        for name, _ in _assignments(path)
        if not DYNAMIC_R2.fullmatch(name) and name not in sources
    ]
    assert stale == []


def test_dynamic_r2_prefixes_still_exist() -> None:
    sources = _tracked_sources()
    for literal in ("CFB_R2_PREVIEW", '"CFB_R2"', "CFB_R2_LAB_", "CFB_R2_LAB_SOURCE_"):
        assert literal in sources


def test_every_cfb_variable_read_in_src_is_documented() -> None:
    documented = {name for name, _ in _assignments(ROOT / ".env.example")}
    read: set[str] = set()
    for path in (ROOT / "src").rglob("*.py"):
        read |= set(
            re.findall(
                r"(?:getenv\(|environ\.get\(|environ\[)\s*[\"'](CFB_[A-Z0-9_]+)[\"']",
                path.read_text(),
            )
        )
    assert sorted(read - documented) == []
