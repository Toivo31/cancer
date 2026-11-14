#!/usr/bin/env python3
"""Refresh the offline copy of the bundle embedded in demo/index.html.

Usage: python demo/embed_bundle.py [bundle.json]
Default bundle: demo/data/demo_bundle.json if it exists, else the fixture.
"""
import json
import re
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent
PATTERN = re.compile(r'(<script id="bundle" type="application/json">\n)(.*?)(\n</script>)', re.S)


def main() -> None:
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        src = DEMO / "data" / "demo_bundle.json"
        if not src.exists():
            src = DEMO / "data" / "demo_bundle.fixture.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    # "</" would end the script tag early; JSON allows the escaped form.
    text = json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")
    html_path = DEMO / "index.html"
    html = html_path.read_text(encoding="utf-8")
    new, n = PATTERN.subn(lambda m: m.group(1) + text + m.group(3), html, count=1)
    if n != 1:
        sys.exit("embedded <script id=\"bundle\"> block not found in index.html")
    html_path.write_text(new, encoding="utf-8")
    print(f"embedded {src} into {html_path}")


if __name__ == "__main__":
    main()
