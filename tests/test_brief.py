from datetime import date
from types import SimpleNamespace

import pytest

from radar import llm
from radar.brief import (
    BRIEF_SCHEMA,
    SECTIONS,
    Claim,
    build_context,
    check_citations,
    generate_brief,
    normalise_id,
    parse_claims,
)
from radar.models import IndiaRecord, Paper, Trial

PAPER = Paper("111", "GLP-1 and lean mass", "Diabetes Care", date(2026, 9, 1), "Lee K",
              "SECRET ABSTRACT TEXT about lean mass.", ("Journal Article", "Review"))
TRIAL = Trial("NCT07891156", "Semaglutide in T1D", "RECRUITING", ("PHASE2", "PHASE3"),
              "McGill", date(2026, 10, 23), "SECRET SUMMARY of the trial.")
CTRI = IndiaRecord("CTRI", "CTRI/2025/06/088110", "semaglutide", "Oral semaglutide vs Rybelsus",
                   date(2025, 6, 13), "https://ctri.nic.in/x",
                   {"phase": "Phase 3", "sponsor": "Dr. Reddy's"})
CDSCO = IndiaRecord("CDSCO", "SEC-ENDO-2025-12-09-06", "semaglutide", "Zydus Phase III report",
                    date(2025, 12, 9), "https://cdsco.gov.in/x.pdf",
                    {"decision_type": "SEC recommendation", "applicant": "Zydus"})
VALID = {PAPER.source_id, TRIAL.source_id, CTRI.source_id, CDSCO.source_id}


def _empty():
    return {s: [] for s in SECTIONS}


@pytest.mark.parametrize("raw,expected", [
    ("PMID:111", "PMID:111"),
    ("[PMID: 111]", "PMID:111"),
    ("pmid 111", "PMID:111"),
    ("nct07891156", "NCT07891156"),
    ("CTRI/2025/06/088110", "CTRI:CTRI/2025/06/088110"),
    ("CTRI:CTRI/2025/06/088110", "CTRI:CTRI/2025/06/088110"),
    ("SEC-ENDO-2025-12-09-06", "CDSCO:SEC-ENDO-2025-12-09-06"),
    ("cdsco:SEC-ENDO-2025-12-09-06", "CDSCO:SEC-ENDO-2025-12-09-06"),
    ("12345", "12345"),  # bare numbers are not guessed into PMIDs
])
def test_normalise_id(raw, expected):
    assert normalise_id(raw) == expected


def test_parse_claims_moves_inline_ids_and_keeps_chemistry():
    data = _empty()
    data["research"] = [
        {"text": "Lean mass fell [PMID:111; NCT07891156].", "ids": ["PMID:111"]},
        {"text": "[18F]FDG uptake was measured", "ids": ["PMID:111"]},
        {"text": "   ", "ids": ["PMID:111"]},
    ]
    claims = parse_claims(data)["research"]
    assert claims[0] == Claim("Lean mass fell.", ("PMID:111", "NCT07891156"))
    assert claims[1].text == "[18F]FDG uptake was measured"
    assert len(claims) == 2


def test_check_citations_rules():
    sections = {s: [] for s in SECTIONS}
    sections["research"] = [
        Claim("ok", ("PMID:111",)),
        Claim("invented", ("PMID:999",)),
        Claim("half invented", ("PMID:111", "PMID:999")),
        Claim("uncited", ()),
        Claim("malformed", ("PMID:abc",)),
    ]
    sections["india"] = [Claim("india ok", (CTRI.source_id, CDSCO.source_id))]
    sections["gaps"] = [Claim("no data on kids", ()), Claim("gap with bad id", ("NCT00000000",))]
    sections["next_questions"] = [Claim("What next?", ())]

    brief = check_citations(sections, VALID)
    assert [c.text for c in brief.sections["research"]] == ["ok"]
    assert [c.text for c in brief.sections["india"]] == ["india ok"]
    assert [c.text for c in brief.sections["gaps"]] == ["no data on kids"]
    assert [c.text for c in brief.sections["next_questions"]] == ["What next?"]
    reasons = {d.claim.text: d.reason for d in brief.dropped}
    assert reasons["invented"] == "unknown id: PMID:999"
    assert reasons["half invented"] == "unknown id: PMID:999"
    assert reasons["uncited"] == "no citation"
    assert reasons["malformed"] == "unknown id: PMID:abc"
    assert reasons["gap with bad id"] == "unknown id: NCT00000000"
    assert brief.invalid_citations == 5


def test_context_tags_every_record_and_marks_reviews():
    ctx = build_context("semaglutide", 6, [PAPER, TRIAL, CTRI, CDSCO])
    for rid in VALID:
        assert f"[{rid}]" in ctx
    assert "type: Journal Article, Review" in ctx
    assert "PHASE2/PHASE3" in ctx
    assert "<records>" in ctx and "last 6 months" in ctx


def test_generate_brief_call_and_check(fake_api):
    def responder(kwargs):
        data = _empty()
        data["in_one_line"] = [{"text": "Lean mass is a focus", "ids": ["PMID:111"]}]
        data["research"] = [{"text": "Made up", "ids": ["PMID:42"]}]
        data["india"] = [{"text": "Zydus recommended", "ids": ["SEC-ENDO-2025-12-09-06"]}]
        return data

    api = fake_api(responder)
    brief = generate_brief("semaglutide", 6, [PAPER], [TRIAL], [CTRI, CDSCO], api=api)

    (call,) = api.calls
    assert call["model"] == "claude-sonnet-5-5"
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["fallbacks"] == "default"
    assert call["output_config"]["format"]["schema"] == BRIEF_SCHEMA
    assert call["output_config"]["effort"] == "medium"
    assert "Never give clinical, dosing or treatment advice." in call["system"]
    assert brief.sections["in_one_line"][0].ids == ("PMID:111",)
    assert brief.sections["india"][0].ids == ("CDSCO:SEC-ENDO-2025-12-09-06",)
    assert brief.sections["research"] == [] and brief.invalid_citations == 1
    assert brief.usage[0].input_tokens == 1000
    assert brief.usage[0].cost_usd == pytest.approx((1000 * 2 + 200 * 10) / 1e6)


def test_generate_brief_needs_records(fake_api):
    with pytest.raises(ValueError):
        generate_brief("x", 6, [], [], [], api=fake_api(lambda k: _empty()))


def _response(stop_reason, category=None):
    return SimpleNamespace(
        model="claude-sonnet-5-5", stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category), content=[],
        usage=SimpleNamespace(input_tokens=10, output_tokens=0))


def test_refusal_and_truncation_raise(fake_api):
    with pytest.raises(llm.ModelRefusal) as exc:
        generate_brief("x", 6, [PAPER], [], [], api=fake_api(lambda k: _response("refusal", "bio")))
    assert exc.value.category == "bio"
    with pytest.raises(llm.ModelError):
        generate_brief("x", 6, [PAPER], [], [], api=fake_api(lambda k: _response("max_tokens")))
