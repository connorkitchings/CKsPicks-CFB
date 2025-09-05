"""CI helper to verify [IMPL-task:X] etc. resolve."""

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"

parser = argparse.ArgumentParser(description="Validate specific anchor types.")
parser.add_argument(
    "--types",
    nargs="+",
    default=["IMPL-task", "PRD-decision", "KB", "QG", "LOG"],
    help="Anchor types to validate (default: all)",
)
args = parser.parse_args()

PATTERNS = []
if "IMPL-task" in args.types:
    PATTERNS.append(re.compile(r"\[IMPL-task:(\w+)\]"))
if "PRD-decision" in args.types:
    PATTERNS.append(re.compile(r"\[PRD-decision:(\d{4}-\d{2}-\d{2})\]"))
if "KB" in args.types:
    PATTERNS.append(re.compile(r"\[KB:([\w-]+)\]"))
if "QG" in args.types:
    PATTERNS.append(re.compile(r"\[QG:([\w-]+)\]"))
if "LOG" in args.types:
    PATTERNS.append(re.compile(r"\[LOG:(\d{4}-\d{2}-\d{2})\]"))


# Collect all markdown files
files = list(DOCS.rglob("*.md")) + [ROOT / "README.md"]
anchors = set()
for file in files:
    with open(file, encoding="utf-8") as f:
        for line in f:
            for pat in PATTERNS:
                for m in pat.finditer(line):
                    anchors.add(m.group(0))

# Build anchor index for each file (headings + explicit {#id})

def slugify(text: str) -> str:
    import re as _re
    t = text.strip().lower()
    t = _re.sub(r"[\s]+", "-", t)
    t = _re.sub(r"[^a-z0-9\-_]", "", t)
    return t

file_to_anchors: dict[Path, set[str]] = {}
for file in files:
    anchors_set: set[str] = set()
    with open(file, encoding="utf-8") as f:
        for line in f:
            # explicit anchors like {#id}
            for m in re.finditer(r"\{#([A-Za-z0-9\-_]+)\}", line):
                anchors_set.add(m.group(1))
            # headings -> slug
            if line.lstrip().startswith("#"):
                heading = line.lstrip("#").strip()
                if heading:
                    anchors_set.add(slugify(heading))
    file_to_anchors[file] = anchors_set

# Validate markdown links
link_pat = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
errors: list[str] = []

for file in files:
    content = file.read_text(encoding="utf-8")
    for m in link_pat.finditer(content):
        url = m.group(2)
        # Skip external and mail
        if url.startswith("http://") or url.startswith("https://") or url.startswith("mailto:"):
            continue
        # Handle same-file anchors
        if url.startswith("#"):
            anchor = url[1:]
            if anchor and anchor not in file_to_anchors.get(file, set()):
                errors.append(f"Missing anchor '#{anchor}' in {file.relative_to(ROOT)}")
            continue
        # Split path#anchor
        if "#" in url:
            path_part, anchor = url.split("#", 1)
        else:
            path_part, anchor = url, None
        target = (file.parent / path_part).resolve()
        if not target.exists():
            # Try adding .md if omitted
            if not target.suffix:
                alt = (file.parent / (path_part + ".md")).resolve()
                if alt.exists():
                    target = alt
                else:
                    errors.append(f"Broken link in {file.relative_to(ROOT)} -> {url}")
                    continue
            else:
                errors.append(f"Broken link in {file.relative_to(ROOT)} -> {url}")
                continue
        if anchor:
            if target.suffix.lower() == ".md":
                if anchor not in file_to_anchors.get(target, set()):
                    errors.append(
                        f"Missing anchor '#{anchor}' in {target.relative_to(ROOT)} (linked from {file.relative_to(ROOT)})"
                    )

if errors:
    print("Link check FAILED:")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)
else:
    print("Link check passed with no errors.")
