#!/usr/bin/env python3
"""Render website/content/*.md into the <!--md:NAME--> ... <!--/md--> slots of public/index.html.
The markdown files are the source of truth for the page text; run this after editing them."""
import re, pathlib, markdown
root = pathlib.Path(__file__).parent
index = root / "public" / "index.html"
html = index.read_text()
LINKS = {"04-appendix.md": "#appendix", "02-simulation.md": "#simulation", "03-jev.md": "#jev", "01-manifesto.md": "#manifesto"}
def render(name):
    md = (root / "content" / f"{name}.md").read_text()
    md = md.split("\n---\n")[0] if "\n---\n" in md else md          # drop the trailing design note ("Infographic: ...")
    if name == "03-jev":
        md = md.split("\n## Try it")[0]                              # replaced by the live test area
    for k, v in LINKS.items():
        md = md.replace(f"({k})", f"({v})")
    return markdown.markdown(md, extensions=["tables"])
def fill(m):
    name = m.group(1)
    body = render(name)
    if name == "02-simulation":
        body = re.sub(r"^<h1>.*?</h1>\s*", "", body)                 # the page has its own heading above the graph
    return f"<!--md:{name}-->{body}<!--/md-->"
html = re.sub(r"<!--md:([\w-]+)-->.*?<!--/md-->", fill, html, flags=re.S)
index.write_text(html)
print("built", [p.name for p in sorted((root / "content").glob("*.md"))])
