from radar.models import IndiaRecord, Paper, Trial


def test_source_ids_and_urls():
    paper = Paper("123", "t", "j", None, "a", "")
    trial = Trial("NCT01234567", "t", "RECRUITING", ("PHASE3",), "s", None)
    india = IndiaRecord("CTRI", "CTRI/2024/01/012345", "semaglutide", "t", None, "https://ctri.nic.in")

    assert paper.source_id == "PMID:123"
    assert paper.url == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert trial.source_id == "NCT01234567"
    assert trial.url == "https://clinicaltrials.gov/study/NCT01234567"
    assert india.source_id == "CTRI:CTRI/2024/01/012345"
