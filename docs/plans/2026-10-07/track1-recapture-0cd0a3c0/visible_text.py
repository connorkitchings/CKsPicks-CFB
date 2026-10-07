"""Extract the visible text of a saved HTML page (scripts, styles and SVG removed)."""

import re
import sys
from html.parser import HTMLParser

SKIPPED = {"script", "style", "noscript", "svg"}
BLOCKS = {"p", "h1", "h2", "h3", "li", "tr", "section", "div", "br", "td", "th"}


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in SKIPPED:
            self.skip_depth += 1
        if tag in BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag in SKIPPED and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip() + " ")


def main(source: str, target: str) -> None:
    parser = VisibleText()
    with open(source, errors="ignore") as handle:
        parser.feed(handle.read())
    text = re.sub(r"\n\s*\n+", "\n", "".join(parser.parts))
    with open(target, "w") as handle:
        handle.write(text)
    print(len(text), "chars")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
