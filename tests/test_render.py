from datetime import UTC, datetime

from radar.brief import SECTIONS, Brief, Claim
from radar.models import Paper
from radar.render import LABEL_LINE, RunStamp, render_markdown
from radar.verify import VerifyStats
from tests.test_brief import CDSCO, CTRI, PAPER, TRIAL

STAMP = RunStamp(
    run_at=datetime(2026, 10, 25, 18, 0, tzinfo=UTC),
    months=6,
    source_counts={"PubMed": "1 used of 1,455 found", "ClinicalTrials.gov": "1 used of 315 found"},
    models={"brief": "claude-sonnet-5-5", "verification": "claude-haiku-5-5"},
    stats=VerifyStats(total=3, supported=2, partial=1, unsupported=0),
)


def _brief():
    s = {k: [] for k in SECTIONS}
    s["in_one_line"] = [Claim("Lean mass is the new focus", ("PMID:111",), "supported")]
    s["research"] = [Claim("A review covers it.", ("PMID:111",), "partial", "overstates")]
    s["trials"] = [Claim("One Phase 2/3 trial recruits", ("NCT07891156",), "supported")]
    s["next_questions"] = [Claim("Does lean mass recover?", ()), Claim("In India?", ())]
    return Brief(sections=s)


def test_render_format():
    retracted = [Paper("41532579", "RETRACTION: a | b", "J", None, "X", "abs", (), True)]
    md = render_markdown("semaglutide", _brief(), [PAPER, TRIAL, CTRI, CDSCO], STAMP, retracted)
    lines = md.splitlines()

    assert lines[0] == "# Literature Radar: semaglutide — last 6 months"
    assert lines[1] == LABEL_LINE
    assert "window: last 6 months" in lines[3] and "claude-haiku-5-5" in lines[3]
    assert "2 supported, 1 partly, 0 removed" in lines[3]
    assert ("Lean mass is the new focus. [PMID:111](https://pubmed.ncbi.nlm.nih.gov/111/)"
            in md)
    assert "_(⚠ partly supported: overstates)_" in md
    assert "[NCT07891156](https://clinicaltrials.gov/study/NCT07891156)" in md
    assert "_No India records (CTRI or CDSCO) found for this query._" in md
    assert "1. Does lean mass recover?" in md and "2. In India?" in md
    assert "| CDSCO:SEC-ENDO-2025-12-09-06 | Zydus Phase III report | Zydus |" in md
    assert "| CTRI:CTRI/2025/06/088110 | Oral semaglutide vs Rybelsus | Dr. Reddy's |" in md
    assert "## Retracted papers (excluded)" in md and "RETRACTION: a \\| b" in md


def test_render_never_includes_abstracts_or_summaries():
    md = render_markdown("semaglutide", _brief(), [PAPER, TRIAL], STAMP)
    assert "SECRET ABSTRACT" not in md and "SECRET SUMMARY" not in md
