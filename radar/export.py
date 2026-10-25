"""Export a rendered brief as Markdown or PDF (F10).

Input is the rendered Markdown, which already carries the label line and contains
summaries, citations and links only, never abstracts (F26).
"""

from __future__ import annotations

import re

import markdown as md

from radar.render import LABEL_LINE

CSS = """
@page { size: A4; margin: 16mm 14mm; @bottom-right { content: counter(page) " / " counter(pages);
        font-size: 8pt; color: #666; } }
body { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 10pt; line-height: 1.45;
       color: #1a1a1a; }
h1 { font-size: 16pt; margin: 0 0 4pt; }
h2 { font-size: 12pt; margin: 14pt 0 4pt; border-bottom: 1px solid #ddd; padding-bottom: 2pt; }
p:first-of-type { margin-top: 0; }
blockquote { margin: 6pt 0; padding: 4pt 8pt; background: #fff6e0; border-left: 3px solid #e0a800; }
a { color: #0b5cad; text-decoration: none; }
table { border-collapse: collapse; width: 100%; font-size: 8pt; }
th, td { border: 1px solid #ddd; padding: 3pt 4pt; text-align: left; vertical-align: top; }
th { background: #f3f3f3; }
em { color: #555; }
"""


def to_markdown(brief_md: str) -> bytes:
    return _ensure_label(brief_md).encode("utf-8")


def to_html(brief_md: str) -> str:
    body = md.markdown(_ensure_label(brief_md), extensions=["tables", "sane_lists"])
    title = re.sub(r"<[^>]+>", "", brief_md.splitlines()[0].lstrip("# ")) if brief_md else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")


def to_pdf(brief_md: str) -> bytes:
    from weasyprint import HTML  # imported lazily: needs system Pango libraries

    return HTML(string=to_html(brief_md)).write_pdf()


def _ensure_label(brief_md: str) -> str:
    """Guardrail 5: the label is on every export, even if the input lost it."""
    return brief_md if LABEL_LINE in brief_md else f"{LABEL_LINE}\n\n{brief_md}"
