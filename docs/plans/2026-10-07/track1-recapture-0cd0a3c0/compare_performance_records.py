"""Compare the graded-picks audit records of two saved /performance text captures, game by game."""

import re
import sys


def records(path: str) -> list[tuple[str, ...]]:
    text = open(path).read()
    text = re.sub(
        r"(Price: \w+) (?=\S[^\n]* @ )", r"\1\n", text
    )  # split glued next title
    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip() and "Freeze evidence SHA-256" not in line
    ]
    found, i = [], 0
    while i < len(lines):
        if (
            " @ " in lines[i]
            and i + 1 < len(lines)
            and re.match(r"Week \d", lines[i + 1])
        ):
            found.append(tuple(lines[i : i + 5]))
            i += 5
        else:
            i += 1
    return found


a, b = records(sys.argv[1]), records(sys.argv[2])
print("records:", len(a), len(b))
print("same set of game records (freeze-hash lines excluded):", sorted(a) == sorted(b))
print("same order:", a == b)
