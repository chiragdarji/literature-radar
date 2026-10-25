"""Load hand-collected India records (F28) from data/india/ctri.csv and cdsco.csv.

CTRI: Clinical Trials Registry - India. CDSCO: India's drug regulator; its Subject Expert
Committees (SEC) recommend whether trials or marketing should be allowed.
"""

from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from radar.config import ROOT
from radar.models import IndiaRecord

DATA_DIR = ROOT / "data" / "india"

DETAIL_COLUMNS = {
    "CTRI": ("phase", "sponsor", "status", "sites"),
    "CDSCO": ("decision_type", "applicant", "decision"),
}


def load_all(data_dir: Path = DATA_DIR) -> list[IndiaRecord]:
    records: list[IndiaRecord] = []
    for source in DETAIL_COLUMNS:
        path = data_dir / f"{source.lower()}.csv"
        if path.exists():
            records.extend(_load_csv(path, source))
    return records


def load_for_query(query: str, data_dir: Path = DATA_DIR) -> list[IndiaRecord]:
    """Records whose molecule or an alias appears as a whole word in the query."""
    q = query.lower()
    matched = []
    for rec in load_all(data_dir):
        names = (rec.molecule, *rec.aliases)
        if any(re.search(rf"\b{re.escape(n.lower())}\b", q) for n in names if n):
            matched.append(rec)
    return sorted(matched, key=lambda r: r.date or date.min, reverse=True)


def _load_csv(path: Path, source: str) -> list[IndiaRecord]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        IndiaRecord(
            source=source,
            record_id=row["record_id"].strip(),
            molecule=row["molecule"].strip().lower(),
            title=row["title"].strip(),
            date=_parse_date(row.get("date", "")),
            url=row["url"].strip(),
            details={c: row.get(c, "").strip() for c in DETAIL_COLUMNS[source]},
            aliases=tuple(a.strip() for a in row.get("aliases", "").split(";") if a.strip()),
        )
        for row in rows
        if row.get("record_id", "").strip()
    ]


def _parse_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None
