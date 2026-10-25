"""Literature Radar: one search box in, a cited and checked research brief out.

Run with:  streamlit run app.py
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from radar import export, india, pipeline
from radar.config import settings
from radar.llm import ModelError, ModelRefusal

EXAMPLES = ["semaglutide", "denosumab", "trastuzumab", "PCSK9", "dengue vaccine"]

st.set_page_config(page_title="Literature Radar", page_icon="📡", layout="centered")


@st.cache_data(show_spinner=False)
def pdf_bytes(markdown: str) -> bytes:
    return export.to_pdf(markdown)


def queue_run(query: str | None = None) -> None:
    """Button callback: optionally set the query, then run on this rerun."""
    if query is not None:
        st.session_state.query = query
    st.session_state.pending = True
    st.session_state.pop("ambiguous", None)


def run(query: str, months: int, refresh: bool) -> None:
    st.session_state.pop("result", None)
    status = st.status("Working…", expanded=True)
    try:
        with status:
            outcome = pipeline.get_brief(query, months, refresh=refresh, progress=status.write)
        status.update(label="Brief ready" if outcome.source == "live" else "Loaded from cache",
                      state="complete", expanded=False)
    except Exception as exc:  # noqa: BLE001 - every failure gets a message, unknown ones in full
        status.update(label="Stopped", state="error", expanded=False)
        explain_failure(exc, query, months)
        return
    st.session_state.result = {"query": query, "months": months, "outcome": outcome}


def explain_failure(exc: Exception, query: str, months: int) -> None:
    """Plain-language messages for expected failures (F12, F25)."""
    if isinstance(exc, pipeline.NoRecords):
        st.warning(f"Nothing found for **{query}** in the last {months} months. Try the 12-month "
                   "window, a broader term (the disease instead of a sub-type), or another name "
                   "for it: a brand name, a gene symbol or a drug code.")
    elif isinstance(exc, pipeline.SourcesDown):
        st.error(str(exc))
    elif isinstance(exc, ModelRefusal):
        st.error(f"The AI model declined this query ({exc.category or 'no category given'}). "
                 "Try rephrasing it as a molecule, target or disease name.")
    elif isinstance(exc, ModelError):
        st.error(f"The brief could not be written: {exc}. Please try again.")
    else:
        st.exception(exc)


def show_result(query: str, outcome: pipeline.Outcome) -> None:
    payload = outcome.payload
    if outcome.notice:
        (st.warning if outcome.source == "stale cache" else st.info)(outcome.notice)

    markdown = payload["markdown"]
    slug = "-".join(query.lower().split())
    left, right, _ = st.columns([1, 1, 2])
    left.download_button("Download Markdown", export.to_markdown(markdown),
                         file_name=f"literature-radar-{slug}.md", mime="text/markdown")
    right.download_button("Download PDF", pdf_bytes(markdown),
                          file_name=f"literature-radar-{slug}.pdf", mime="application/pdf")

    india_rows = payload["india"]
    tabs = st.tabs(["Brief", f"Sources ({len(payload['sources'])})",
                    f"India ({len(india_rows)})", "Run details"])
    with tabs[0]:
        st.markdown(markdown.split("\n## Sources\n")[0])  # the Sources tab shows the table
        if payload["retracted"]:
            with st.expander(f"⚠ {len(payload['retracted'])} retracted paper(s) excluded"):
                for r in payload["retracted"]:
                    st.markdown(f"- [{r['id']}]({r['url']}) {r['title']}")
    with tabs[1]:
        show_sources(payload["sources"])
    with tabs[2]:
        show_india(india_rows)
    with tabs[3]:
        show_run_details(payload["log"])


def show_sources(sources: list[dict[str, Any]]) -> None:
    st.caption("Records sent to the model, in ranked order. **Why this paper?** Score = 0.7 × "
               "relevance (BM25 on title and abstract, scaled 0–1) + 0.3 × recency (halves every "
               "180 days), then picked for variety so near-duplicates don't crowd the list.")
    df = pd.DataFrame(sources)[["rank", "id", "title", "score", "relevance", "recency", "cited",
                                "kind", "who", "date", "detail", "url"]]
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={
        "rank": st.column_config.NumberColumn("#", width="small"),
        "id": "ID", "kind": "Type", "title": st.column_config.TextColumn("Title", width="large"),
        "who": "Journal or sponsor", "date": "Date", "detail": "Type / status · phase",
        "cited": st.column_config.CheckboxColumn("Cited"),
        "relevance": st.column_config.ProgressColumn("Relevance", min_value=0, max_value=1),
        "recency": st.column_config.ProgressColumn("Recency", min_value=0, max_value=1),
        "score": st.column_config.NumberColumn("Score", format="%.2f"),
        "url": st.column_config.LinkColumn("Link", display_text="open"),
    })


def show_india(rows: list[dict[str, Any]]) -> None:
    if not rows:
        molecules = sorted({r.molecule for r in india.load_all()})
        st.info("No India records for this query. Curated CTRI and CDSCO records currently "
                f"cover: {', '.join(molecules)}.")
        return
    st.caption("Hand-collected from CTRI (trial registrations) and CDSCO Subject Expert "
               "Committee minutes. An SEC recommendation is not a final approval.")
    for source, label in (("CTRI", "CTRI trial registrations"),
                          ("CDSCO", "CDSCO / SEC recommendations")):
        part = [r for r in rows if r["source"] == source]
        if not part:
            continue
        st.subheader(label)
        cols = (["id", "title", "phase", "sponsor", "status", "sites", "date", "cited", "url"]
                if source == "CTRI" else
                ["id", "title", "applicant", "decision", "date", "cited", "url"])
        df = pd.DataFrame(part).reindex(columns=cols)
        if "sites" in df:
            df["sites"] = df["sites"].str.replace(";", ", ")
        st.dataframe(df, hide_index=True, use_container_width=True, column_config={
            "id": "ID", "title": st.column_config.TextColumn("Title", width="large"),
            "phase": "Phase", "sponsor": "Sponsor", "status": "Status", "sites": "Sites",
            "applicant": "Applicant", "decision": st.column_config.TextColumn("Decision",
                                                                              width="large"),
            "date": "Date", "cited": st.column_config.CheckboxColumn("Cited"),
            "url": st.column_config.LinkColumn("Link", display_text="open"),
        })


def show_run_details(log: dict[str, Any]) -> None:
    rate = log.get("support_rate")
    a, b, c, d = st.columns(4)
    a.metric("Time", f"{log['total_s']:.0f} s")
    b.metric("Cost", f"${log['cost_usd']:.3f}")
    c.metric("Claims supported", "–" if rate is None else f"{rate:.0%}",
             help=f"{log['supported']} supported, {log['partial']} partly, "
                  f"{log['unsupported']} removed, of {log['claims_verified']} checked")
    d.metric("Invalid citations dropped", log["invalid_citations"])
    st.caption(f"Fetch {log['fetch_s']} s · brief {log['brief_s']} s · verification "
               f"{log['verify_s']} s · {log['records_sent']} records sent to the model")
    if log["dropped"]:
        st.markdown("**Claims removed before display**")
        st.dataframe(pd.DataFrame(log["dropped"]), hide_index=True, use_container_width=True)
    st.markdown("**Tokens**")
    st.dataframe(pd.DataFrame(log["tokens"]), hide_index=True)


# --- Page ----------------------------------------------------------------------------------

st.title("📡 Literature Radar")
st.caption("Type a molecule, target or disease. Get a one-page brief from the latest papers "
           "and trials, with India's CTRI and CDSCO records, where every line is cited and "
           "checked against its source.")

cfg = settings()["brief"]
st.text_input("Molecule, target or disease", key="query", placeholder="e.g. semaglutide",
              on_change=queue_run)
example_cols = st.columns(len(EXAMPLES))
for col, example in zip(example_cols, EXAMPLES, strict=True):
    col.button(example, on_click=queue_run, args=(example,), use_container_width=True)

left, right = st.columns([3, 1])
months = left.radio("Time window", cfg["windows_months"], horizontal=True,
                    index=cfg["windows_months"].index(cfg["default_window_months"]),
                    format_func=lambda m: f"Last {m} months")
refresh = right.checkbox("Ignore cache", help="Run live even if this query ran in the last 24 h")
st.button("Generate brief", type="primary", on_click=queue_run)

query = st.session_state.get("query", "").strip()
if st.session_state.pop("pending", False) and query:
    if meanings := pipeline.ambiguous_meanings(query):
        st.session_state.ambiguous = (query, meanings)
        st.session_state.pop("result", None)  # don't leave the previous brief under the question
    else:
        run(query, months, refresh)

if ambiguous := st.session_state.get("ambiguous"):
    abbrev, meanings = ambiguous
    choice = st.radio(f"**{abbrev}** has several meanings. Which one?", meanings)
    st.button("Use this meaning", type="primary", on_click=queue_run, args=(choice,))

if result := st.session_state.get("result"):
    show_result(result["query"], result["outcome"])

st.divider()
st.caption("AI-generated from public sources. Verify before use. Not medical advice. "
           "Sources: PubMed, ClinicalTrials.gov, CTRI, CDSCO.")
