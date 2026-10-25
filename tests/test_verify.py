import pytest

from radar.brief import SECTIONS, Brief, Claim
from radar.verify import build_section_prompt, verify_brief
from tests.test_brief import CTRI, PAPER, TRIAL

RECORDS = {r.source_id: r for r in (PAPER, TRIAL, CTRI)}


def _brief():
    sections = {s: [] for s in SECTIONS}
    sections["research"] = [Claim("A", ("PMID:111",)), Claim("B", ("PMID:111",)),
                            Claim("C", ("PMID:111",))]
    sections["trials"] = [Claim("T", ("NCT07891156",))]
    sections["gaps"] = [Claim("G", ())]
    return Brief(sections=sections)


def test_section_prompt_contains_only_cited_records():
    prompt = build_section_prompt("trials", _brief(), RECORDS)
    assert "[NCT07891156]" in prompt and "SECRET SUMMARY" in prompt
    assert "[PMID:111]" not in prompt and "[CTRI:" not in prompt
    assert "0. T (cites: NCT07891156)" in prompt


def test_labels_applied_unsupported_removed_missing_fails_closed(fake_api):
    def responder(kwargs):
        if "0. T (cites" in kwargs["messages"][0]["content"]:
            return {"results": [{"claim": 0, "label": "supported", "note": ""}]}
        return {"results": [
            {"claim": 0, "label": "supported", "note": ""},
            {"claim": 1, "label": "partial", "note": "sample size not stated"},
            {"claim": 7, "label": "supported", "note": "out of range, ignored"},
        ]}  # claim 2 missing

    api = fake_api(responder)
    brief, stats = verify_brief(_brief(), RECORDS, api=api)

    assert len(api.calls) == 2  # one batched call per factual section with claims
    assert all(c["model"] == "claude-haiku-5-5" and "fallbacks" not in c for c in api.calls)
    research = brief.sections["research"]
    assert [(c.text, c.label) for c in research] == [("A", "supported"), ("B", "partial")]
    assert research[1].note == "sample size not stated"
    assert brief.sections["gaps"][0].label is None  # open sections are not verified
    dropped = {d.claim.text: d.reason for d in brief.dropped}
    assert dropped["C"].startswith("unsupported: verifier returned no result")
    assert (stats.total, stats.supported, stats.partial, stats.unsupported) == (4, 2, 1, 1)
    assert stats.support_rate == pytest.approx(0.5)
    assert len(brief.usage) == 2


def test_nothing_to_verify(fake_api):
    empty = Brief(sections={s: [] for s in SECTIONS})
    brief, stats = verify_brief(empty, RECORDS, api=fake_api(lambda k: pytest.fail("no call")))
    assert stats.total == 0 and stats.support_rate is None
