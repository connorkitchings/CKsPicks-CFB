#!/usr/bin/env python3
"""Resume processed data migration."""

import subprocess
import sys

# Resume with same settings
result = subprocess.run(
    [
        sys.executable,
        "scripts/migration/migrate_to_cloud.py",
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
    cwd="/Users/connorkitchings/Desktop/Repositories/cfb_model",
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
print("Return code:", result.returncode)
