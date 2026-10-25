from datetime import date

from radar.india import load_all, load_for_query

CTRI_CSV = """record_id,molecule,aliases,title,phase,sponsor,status,sites,date,url
CTRI/2025/06/088110,semaglutide,Ozempic;Wegovy;Rybelsus,"Oral semaglutide vs Rybelsus, phase III",Phase 3,Dr. Reddy's,Not yet recruiting,Pune;Mumbai,2025-06-13,https://ctri.nic.in/a
CTRI/2017/06/008830,semaglutide,Ozempic,Older trial,Phase 3,Novo Nordisk,Completed,Delhi,2017-06-15,https://ctri.nic.in/b
"""
CDSCO_CSV = """record_id,molecule,aliases,title,decision_type,applicant,decision,date,url
SEC-ANRH-2025-06-24-04,denosumab,Prolia;Xgeva,Denosumab Phase I report,SEC recommendation,Intas,Noted,2025-06-24,https://cdsco.gov.in/x.pdf
"""


def _write(tmp_path):
    (tmp_path / "ctri.csv").write_text(CTRI_CSV, encoding="utf-8")
    (tmp_path / "cdsco.csv").write_text(CDSCO_CSV, encoding="utf-8")
    return tmp_path


def test_load_all_parses_rows(tmp_path):
    records = load_all(_write(tmp_path))
    assert len(records) == 3
    ctri = records[0]
    assert ctri.source_id == "CTRI:CTRI/2025/06/088110"
    assert ctri.title == "Oral semaglutide vs Rybelsus, phase III"  # quoted comma kept
    assert ctri.aliases == ("Ozempic", "Wegovy", "Rybelsus")
    assert ctri.details["sites"] == "Pune;Mumbai"
    assert ctri.date == date(2025, 6, 13)
    assert records[2].source_id == "CDSCO:SEC-ANRH-2025-06-24-04"
    assert records[2].details["decision_type"] == "SEC recommendation"


def test_match_by_molecule_alias_and_whole_word(tmp_path):
    d = _write(tmp_path)
    assert [r.record_id for r in load_for_query("Semaglutide", d)] == [
        "CTRI/2025/06/088110", "CTRI/2017/06/008830"]  # newest first
    assert [r.molecule for r in load_for_query("oral wegovy", d)] == ["semaglutide"]
    assert [r.molecule for r in load_for_query("Prolia biosimilar", d)] == ["denosumab"]
    assert load_for_query("PCSK9", d) == []
    assert load_for_query("semaglutides", d) == []  # whole word only


def test_missing_files(tmp_path):
    assert load_all(tmp_path) == []


def test_repo_data_loads():
    records = load_all()
    assert {r.source for r in records} == {"CTRI", "CDSCO"}
    assert all(r.url.startswith("https://") and r.date for r in records)
