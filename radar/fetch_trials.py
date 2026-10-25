"""Fetch recently updated trials from the ClinicalTrials.gov API v2 /studies endpoint.

The time window filters on LastUpdatePostDate (docs/PLAN.md decision 1). There is no
filter.phase parameter: phases go through filter.advanced=AREA[Phase]… (CLAUDE.md).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

from radar import http as rhttp
from radar.config import settings
from radar.models import Trial

FIELDS = [
    "NCTId",
    "BriefTitle",
    "OverallStatus",
    "Phase",
    "LeadSponsorName",
    "LastUpdatePostDate",
    "BriefSummary",  # verifier context only (F17); never exported
]
NO_PHASE = {"NA"}  # "not applicable": device, behavioural or other non-drug studies


@dataclass
class TrialsResult:
    trials: list[Trial]
    total_count: int
    query: str


def advanced_filter(days: int | None, phases: list[str] | None = None,
                    today: date | None = None) -> str | None:
    """Build filter.advanced: last-update window AND any of the given phases."""
    parts = []
    if days is not None:
        start = (today or date.today()) - timedelta(days=days)
        parts.append(f"AREA[LastUpdatePostDate]RANGE[{start.isoformat()},MAX]")
    if phases:
        parts.append("(" + " OR ".join(f"AREA[Phase]{p}" for p in phases) + ")")
    return " AND ".join(parts) or None


def search_trials(
    query: str,
    days: int | None,
    *,
    phases: list[str] | None = None,
    http: httpx.Client | None = None,
) -> TrialsResult:
    """Return up to max_trials studies matching query, most recently updated first."""
    query = query.strip()
    if not query:
        raise ValueError("empty query")
    params: dict[str, Any] = {
        "query.term": query,
        "sort": "LastUpdatePostDate:desc",
        "pageSize": settings()["fetch"]["max_trials"],
        "fields": ",".join(FIELDS),
        "countTotal": "true",
    }
    if flt := advanced_filter(days, phases):
        params["filter.advanced"] = flt
    data = rhttp.get(settings()["trials"]["base_url"], params, http=http, cache=True).json()
    studies = data.get("studies", [])
    return TrialsResult(
        trials=[parse_study(s) for s in studies],
        total_count=int(data.get("totalCount", len(studies))),
        query=query,
    )


def parse_study(study: dict[str, Any]) -> Trial:
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status = proto.get("statusModule", {})
    phases = proto.get("designModule", {}).get("phases") or []
    return Trial(
        nct_id=ident.get("nctId", ""),
        title=ident.get("briefTitle", ""),
        status=status.get("overallStatus", "UNKNOWN"),
        phases=tuple(p for p in phases if p not in NO_PHASE),
        sponsor=proto.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
        last_update=_parse_date(status.get("lastUpdatePostDateStruct", {}).get("date")),
        summary=proto.get("descriptionModule", {}).get("briefSummary", "").strip(),
    )


def _parse_date(text: str | None) -> date | None:
    """Dates are 'YYYY-MM-DD' or, for some fields, 'YYYY-MM'."""
    if not text:
        return None
    bits = text.split("-")
    try:
        return date(int(bits[0]), int(bits[1]) if len(bits) > 1 else 1,
                    int(bits[2]) if len(bits) > 2 else 1)
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Print recently updated trials for a query.")
    parser.add_argument("query")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--phase", action="append", help="e.g. PHASE3; repeatable")
    args = parser.parse_args()

    result = search_trials(args.query, args.days, phases=args.phase)
    print(f"query: {result.query}  total: {result.total_count}  shown: {len(result.trials)}\n")
    for t in result.trials:
        phase = "/".join(t.phases) or "-"
        print(f"{t.nct_id}  {t.last_update!s:<10}  {t.status:<22} {phase:<14} {t.sponsor[:30]}")
        print(f"{'':11} {t.title[:110]}")


if __name__ == "__main__":
    main()
