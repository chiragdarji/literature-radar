from radar.export import to_html, to_markdown, to_pdf
from radar.render import LABEL_LINE

BRIEF = f"""# Literature Radar: PCSK9 — last 6 months
{LABEL_LINE}

## In one line
A meta-analysis found plaque improved. [PMID:1](https://pubmed.ncbi.nlm.nih.gov/1/)

## Sources

| ID | Title | Journal or sponsor | Date | Link |
| --- | --- | --- | --- | --- |
| PMID:1 | Plaque | J | 2026-10-01 | [open](https://pubmed.ncbi.nlm.nih.gov/1/) |
"""


def test_markdown_and_html_keep_label_and_links():
    assert to_markdown(BRIEF).decode().splitlines()[1] == LABEL_LINE
    html = to_html(BRIEF)
    assert LABEL_LINE in html and "<table>" in html
    assert '<a href="https://pubmed.ncbi.nlm.nih.gov/1/">PMID:1</a>' in html
    assert "<title>Literature Radar: PCSK9 — last 6 months</title>" in html


def test_label_added_if_missing():
    assert to_markdown("# x\n").decode().startswith(LABEL_LINE)


def test_pdf_renders():
    pdf = to_pdf(BRIEF)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
