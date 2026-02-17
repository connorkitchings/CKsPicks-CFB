#!/usr/bin/env python3
"""Resume processed data migration."""

import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent

result = subprocess.run(
    [
        sys.executable,
        str(repo_root / "scripts/migration/migrate_to_cloud.py"),
        "--include",
        "processed/",
        "--exclude",
        ".DS_Store",
        "--exclude",
        "._",
        "--exclude",
        "__MACOSX",
        "--exclude",
        ".json",
    ],
    capture_output=True,
    text=True,
    cwd=str(repo_root),
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
print("Return code:", result.returncode)
