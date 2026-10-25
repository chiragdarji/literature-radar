"""Render a checked, verified brief as Markdown in the fixed PRD format.

Exports carry summaries, citations and links only, never abstracts (F26): nothing here
reads Paper.abstract or Trial.summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from radar.brief import Brief, Claim, Record
from radar.models import IndiaRecord, Paper, Trial
from radar.verify import VerifyStats

LABEL_LINE = "AI-generated from public sources. Verify before use."

HEADINGS = {
    "in_one_line": "In one line",
    "research": "What the new research says",
    "trials": "Clinical trial activity",
    "india": "India activity",
    "gaps": "Gaps and open questions",
    "next_questions": "Questions to explore next",
}
EMPTY = {
    "in_one_line": "_No single development is supported by the sources in this window._",
    "research": "_No supported findings from papers in this window._",
    "trials": "_No supported findings from trial records in this window._",
    "india": "_No India records (CTRI or CDSCO) found for this query._",
    "gaps": "_None noted._",
    "next_questions": "_None suggested._",
}


@dataclass
class RunStamp:
    """F24: when, what window, which sources and how many records, which models."""

    run_at: datetime
    months: int
    source_counts: dict[str, str]  # e.g. {"PubMed": "10 used of 1,455 found"}
    models: dict[str, str]  # role -> model id
    stats: VerifyStats | None = None
    notes: list[str] = field(default_factory=list)  # e.g. broad-query notice

    def line(self) -> str:
        sources = "; ".join(f"{k}: {v}" for k, v in self.source_counts.items())
        models = ", ".join(f"{role} {m}" for role, m in self.models.items())
        parts = [f"Run {self.run_at:%Y-%m-%d %H:%M %Z}".strip(),
                 f"window: last {self.months} months", f"sources: {sources}", f"models: {models}"]
        if self.stats and self.stats.total:
            parts.append(f"claims verified: {self.stats.supported} supported, "
                         f"{self.stats.partial} partly, {self.stats.unsupported} removed")
        return " · ".join(parts)


def render_markdown(query: str, brief: Brief, records: list[Record], stamp: RunStamp,
                    retracted: list[Paper] | None = None) -> str:
    by_id = {r.source_id: r for r in records}
    out = [f"# Literature Radar: {query} — last {stamp.months} months", LABEL_LINE, "",
           f"_{stamp.line()}_"]
    out += [f"> {note}" for note in stamp.notes]
    for section, heading in HEADINGS.items():
        out += ["", f"## {heading}"]
        claims = brief.sections.get(section, [])
        if not claims:
            out.append(EMPTY[section])
        elif section == "in_one_line":
            out.append(_claim_line(claims[0], by_id))
        elif section == "next_questions":
            out += [f"{n}. {_claim_line(c, by_id)}" for n, c in enumerate(claims, 1)]
        else:
            out += [f"- {_claim_line(c, by_id)}" for c in claims]
    out += ["", "## Sources", "", "| ID | Title | Journal or sponsor | Date | Link |",
            "| --- | --- | --- | --- | --- |"]
    out += [_source_row(r) for r in records]
    if retracted:
        out += ["", "## Retracted papers (excluded)",
                "> ⚠ These papers were retracted or are retraction notices. "
                "They were not used in this brief."]
        out += [f"- [{p.source_id}]({p.url}) {_cell(p.title)}" for p in retracted]
    return "\n".join(out) + "\n"


def _claim_line(claim: Claim, by_id: dict[str, Record]) -> str:
    cites = " ".join(f"[{i}]({by_id[i].url})" if i in by_id else f"[{i}]" for i in claim.ids)
    text = claim.text if claim.text.endswith((".", "?", "!")) else claim.text + "."
    line = f"{text} {cites}".rstrip()
    if claim.label == "partial":
        line += f" _(⚠ partly supported{': ' + claim.note if claim.note else ''})_"
    return line


def _source_row(rec: Record) -> str:
    if isinstance(rec, Paper):
        who, when = rec.journal, rec.pub_date
    elif isinstance(rec, Trial):
        who, when = rec.sponsor, rec.last_update
    else:
        assert isinstance(rec, IndiaRecord)
        who = rec.details.get("sponsor") or rec.details.get("applicant") or ""
        when = rec.date
    return (f"| {rec.source_id} | {_cell(rec.title)} | {_cell(who)} | {when or ''} | "
            f"[open]({rec.url}) |")


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "\\|").split())
