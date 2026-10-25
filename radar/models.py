"""Record types shared across fetchers, ranker and brief."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Paper:
    """A PubMed record."""

    pmid: str
    title: str
    journal: str
    pub_date: date | None
    first_author: str
    abstract: str  # copyright of the publisher: local cache only, never exported (F26)
    publication_types: tuple[str, ...] = ()
    retracted: bool = False

    @property
    def source_id(self) -> str:
        return f"PMID:{self.pmid}"

    @property
    def url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"

    @property
    def is_review(self) -> bool:
        return any(t in {"Review", "Systematic Review", "Meta-Analysis"}
                   for t in self.publication_types)


@dataclass(frozen=True)
class Trial:
    """A ClinicalTrials.gov study."""

    nct_id: str
    title: str
    status: str  # OverallStatus, e.g. RECRUITING, COMPLETED
    phases: tuple[str, ...]  # e.g. ("PHASE2", "PHASE3"); empty when not applicable
    sponsor: str
    last_update: date | None
    summary: str = ""  # BriefSummary: verifier context only (F17), never exported

    @property
    def source_id(self) -> str:
        return self.nct_id

    @property
    def url(self) -> str:
        return f"https://clinicaltrials.gov/study/{self.nct_id}"


@dataclass(frozen=True)
class IndiaRecord:
    """A hand-collected CTRI trial or CDSCO approval/SEC recommendation (F28)."""

    source: str  # "CTRI" or "CDSCO"
    record_id: str  # e.g. CTRI/2024/01/012345
    molecule: str
    title: str
    date: date | None
    url: str
    details: dict[str, str] = field(default_factory=dict)  # phase, sponsor, status, sites…
    aliases: tuple[str, ...] = ()

    @property
    def source_id(self) -> str:
        return f"{self.source}:{self.record_id}"
