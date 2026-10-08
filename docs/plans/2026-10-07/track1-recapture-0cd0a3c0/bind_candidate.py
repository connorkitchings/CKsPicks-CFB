"""Hash the committed blobs of the Track 1 candidate at an exact commit (read-only)."""

import hashlib
import json
import subprocess
import sys

SHA = sys.argv[1]
ORIGINAL = "docs/plans/2026-10-07/track1-evidence/candidate-files.json"


def git(*a):
    return subprocess.check_output(["git", *a])


full = git("rev-parse", SHA).decode().strip()
orig = json.load(open(ORIGINAL))["files"]
web = (
    git("diff", "--name-only", "--diff-filter=ACMR", f"main..{full}", "--", "web")
    .decode()
    .split()
)
batch = [
    ".github/workflows/ci.yml",
    "Makefile",
    "scripts/pipeline/freeze_week.py",
    "scripts/pipeline/select_v5_intended_update_batch.py",
    "tests/test_data_first_possession_rating_runner.py",
    "tests/test_freeze_week_deadline.py",
]
paths = sorted(set(orig) | set(web) | set(batch))
files = {}
for p in paths:
    try:
        files[p] = hashlib.sha256(git("show", f"{full}:{p}")).hexdigest()
    except subprocess.CalledProcessError:
        files[p] = None
out = {
    "candidate_commit": full,
    "main_at_capture": git("rev-parse", "main").decode().strip(),
    "scope": "original Track 1 candidate files + every web/ file differing from main + this session's batch",
    "original_manifest_entries": len(orig),
    "original_hashes_unchanged": sorted(p for p in orig if files.get(p) == orig[p]),
    "original_hashes_changed": sorted(p for p in orig if files.get(p) != orig[p]),
    "files_not_in_original_manifest": sorted(set(paths) - set(orig)),
    "files": files,
}
print(json.dumps(out, indent=1))
