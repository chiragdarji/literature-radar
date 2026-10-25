"""Fetch recent PubMed papers via NCBI E-utilities (esearch + efetch).

Follows the PubMed query rules in docs/PRD.md: tiab + MeSH search, publication-date
window, publication types for tagging, retractions split out (F23), broad-query rule (F25).
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from radar import http as rhttp
from radar.config import env, settings
from radar.models import Paper

# Publication types that mean "do not use": the retracted paper itself, or the notice.
RETRACTION_TYPES = {"Retracted Publication", "Retraction of Publication", "Retraction Notice"}
# CommentsCorrections links: RetractionIn = this paper was retracted;
# RetractionOf = this record is the notice.
RETRACTION_REFS = {"RetractionIn", "RetractionOf"}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
SEASONS = {"spring": 3, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}


@dataclass
class PubMedResult:
    papers: list[Paper]
    retracted: list[Paper]
    hit_count: int
    broad_query: bool  # hit_count above the F25 threshold; results sorted by relevance
    term: str
    errors: list[str] = field(default_factory=list)


def build_term(terms: Iterable[str]) -> str:
    """Each term searches title/abstract and MeSH; terms are OR-ed (ready for F15)."""
    parts = []
    for raw in terms:
        t = raw.strip().replace('"', "")
        if t:
            parts.append(f'("{t}"[tiab] OR "{t}"[MeSH Terms])')
    if not parts:
        raise ValueError("empty query")
    return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"


def _base_params() -> dict[str, Any]:
    params: dict[str, Any] = {"db": "pubmed", "tool": settings()["pubmed"]["tool"]}
    if email := env("NCBI_EMAIL"):
        params["email"] = email
    if key := env("NCBI_API_KEY"):
        params["api_key"] = key
    return params


def _delay() -> float:
    cfg = settings()["pubmed"]
    return cfg["delay_with_key_s"] if env("NCBI_API_KEY") else cfg["delay_no_key_s"]


def _get(endpoint: str, params: dict[str, Any], http: httpx.Client | None) -> httpx.Response:
    url = settings()["pubmed"]["base_url"] + endpoint
    return rhttp.get(url, {**_base_params(), **params}, min_interval_s=_delay(), http=http,
                     cache=True)


def esearch(
    term: str,
    days: int,
    *,
    retmax: int,
    sort: str = "pub_date",
    http: httpx.Client | None = None,
) -> tuple[int, list[str]]:
    """Return (hit count, PMIDs) for papers published in the last `days` days."""
    data = _get("esearch.fcgi", {
        "term": term,
        "retmax": retmax,
        "sort": sort,
        "datetype": "pdat",  # publication date
        "reldate": days,
        "retmode": "json",
    }, http).json()
    result = data["esearchresult"]
    if "ERROR" in result:
        raise RuntimeError(f"PubMed esearch error: {result['ERROR']}")
    return int(result.get("count", 0)), list(result.get("idlist", []))


def efetch(pmids: list[str], http: httpx.Client | None = None) -> list[Paper]:
    """Fetch full records for PMIDs, in the order given."""
    if not pmids:
        return []
    xml_text = _get("efetch.fcgi", {"id": ",".join(pmids), "retmode": "xml"}, http).text
    by_id = {p.pmid: p for p in parse_efetch(xml_text)}
    return [by_id[i] for i in pmids if i in by_id]


def search_pubmed(
    query: str | Iterable[str],
    days: int,
    *,
    http: httpx.Client | None = None,
) -> PubMedResult:
    """Search, fetch and split papers into usable and retracted (F23)."""
    terms = [query] if isinstance(query, str) else list(query)
    term = build_term(terms)
    cfg = settings()["fetch"]
    count, pmids = esearch(term, days, retmax=cfg["max_papers"], http=http)
    broad = count > cfg["broad_query_hits"]
    if broad:
        # F25: too many hits for "newest first" to be meaningful; take the top by relevance.
        count, pmids = esearch(term, days, retmax=cfg["max_papers"], sort="relevance", http=http)
    papers = efetch(pmids, http=http)
    return PubMedResult(
        papers=[p for p in papers if not p.retracted],
        retracted=[p for p in papers if p.retracted],
        hit_count=count,
        broad_query=broad,
        term=term,
    )


# --- XML parsing -------------------------------------------------------------------------


def parse_efetch(xml_text: str) -> list[Paper]:
    """Parse journal articles; PubmedBookArticle (NCBI Bookshelf chapters) is skipped."""
    root = ET.fromstring(xml_text)
    return [_parse_article(a) for a in root.iter("PubmedArticle")]


def _text(el: ET.Element | None) -> str:
    """All text inside an element, including inline markup such as <i> and <sup>."""
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _parse_article(article: ET.Element) -> Paper:
    citation = article.find("MedlineCitation")
    assert citation is not None
    art = citation.find("Article")
    assert art is not None

    pub_types = tuple(_text(t) for t in art.iterfind("PublicationTypeList/PublicationType"))
    corrections = citation.iterfind("CommentsCorrectionsList/CommentsCorrections")
    refs = {c.get("RefType") for c in corrections}

    return Paper(
        pmid=_text(citation.find("PMID")),
        title=_text(art.find("ArticleTitle")) or _text(art.find("VernacularTitle")),
        journal=_text(art.find("Journal/Title")),
        pub_date=_pub_date(art),
        first_author=_first_author(art),
        abstract=_abstract(art),
        publication_types=pub_types,
        retracted=bool(RETRACTION_TYPES.intersection(pub_types) or RETRACTION_REFS & refs),
    )


def _abstract(art: ET.Element) -> str:
    sections = []
    for part in art.iterfind("Abstract/AbstractText"):
        body = _text(part)
        if not body:
            continue
        label = part.get("Label")
        sections.append(f"{label}: {body}" if label else body)
    return "\n".join(sections)


def _first_author(art: ET.Element) -> str:
    author = art.find("AuthorList/Author")
    if author is None:
        return ""
    if (collective := author.find("CollectiveName")) is not None:
        return _text(collective)
    last = _text(author.find("LastName"))
    initials = _text(author.find("Initials"))
    return f"{last} {initials}".strip()


def _pub_date(art: ET.Element) -> date | None:
    """Earliest of the issue date and the electronic publication date.

    Issue dates are often months in the future (e.g. a December issue printed online in
    October), so the e-pub date, when earlier, better reflects when the paper appeared.
    """
    candidates = [
        _parse_date_el(art.find("Journal/JournalIssue/PubDate")),
        *(_parse_date_el(d) for d in art.iterfind("ArticleDate")),
    ]
    found = [d for d in candidates if d is not None]
    return min(found) if found else None


def _parse_date_el(el: ET.Element | None) -> date | None:
    if el is None:
        return None
    year_text = _text(el.find("Year"))
    month_text = _text(el.find("Month"))
    day_text = _text(el.find("Day"))
    if not year_text:
        # MedlineDate, e.g. "2026 Jan-Feb" or "2025 Winter"
        bits = _text(el.find("MedlineDate")).replace("-", " ").split()
        if not bits or not bits[0][:4].isdigit():
            return None
        year_text = bits[0][:4]
        month_text = bits[1] if len(bits) > 1 else ""
    try:
        return date(int(year_text), _month(month_text), int(day_text) if day_text.isdigit() else 1)
    except ValueError:
        return None


def _month(text: str) -> int:
    t = text.strip().lower()
    if t.isdigit():
        return int(t)
    return MONTHS.get(t[:3]) or SEASONS.get(t) or 1


# --- CLI -----------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Print recent PubMed papers for a query.")
    parser.add_argument("query")
    parser.add_argument("--days", type=int, default=180)
    args = parser.parse_args()

    result = search_pubmed(args.query, args.days)
    print(f"term: {result.term}")
    print(f"hits: {result.hit_count}  fetched: {len(result.papers)}  "
          f"retracted: {len(result.retracted)}  broad: {result.broad_query}\n")
    for p in result.papers:
        kind = ", ".join(p.publication_types) or "?"
        print(f"{p.source_id:<14} {p.pub_date!s:<10}  {p.first_author[:18]:<18}  "
              f"{p.journal[:28]:<28}  [{kind[:30]}]")
        print(f"{'':14} {p.title[:110]}")
    for p in result.retracted:
        print(f"RETRACTED {p.source_id}: {p.title[:100]}")


if __name__ == "__main__":
    main()
