"""Render the repository manifesto into its static page, without build dependencies."""
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APPENDIX = 'https://github.com/Toivo31/cancer/blob/site/four-pages/website/content/04-appendix.md'

def render(text):
    # The trailing paragraph is an author's infographic instruction, not manifesto copy.
    text = text.split('\n---\n')[0]
    text = text.replace('its live test is on the JEV page', 'its live test is in [Decision Studio](#studio)')
    text = text.replace('(04-appendix.md)', '(' + APPENDIX + ')')
    blocks = []
    for paragraph in text.strip().split('\n\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        content = escape(paragraph)
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', content)
        if all(line.startswith('- ') for line in content.splitlines()):
            blocks.append('<ul>' + ''.join('<li>' + line[2:] + '</li>' for line in content.splitlines()) + '</ul>')
        elif content.startswith('## '):
            blocks.append('<h2>' + content[3:] + '</h2>')
        elif content.startswith('# '):
            blocks.append('<h1>' + content[2:] + '<span class="dot">.</span></h1>')
        else:
            blocks.append('<p>' + content + '</p>')
    return '\n'.join(blocks)

if __name__ == '__main__':
    page = ROOT / 'public/index.html'
    html = page.read_text()
    body = render((ROOT / 'content/manifesto.md').read_text())
    html = re.sub(r'<!--manifesto-content-->.*?<!--/manifesto-content-->',
                  lambda _: '<!--manifesto-content-->' + body + '<!--/manifesto-content-->', html, flags=re.S)
    page.write_text(html)
    print('Rendered manifesto')
