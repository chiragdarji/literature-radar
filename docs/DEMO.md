# STBI demo runbook

A 10-minute meeting with a live run in the middle (script from docs/PRD.md).

## Setup (once)

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
cp .env.example .env    # then fill in ANTHROPIC_API_KEY, NCBI_API_KEY, NCBI_EMAIL
.venv/bin/streamlit run app.py
```

The app opens at http://localhost:8501. PDF export needs Pango (`brew install pango`).

## The morning of the demo

1. Run the evaluation, which also refreshes the saved briefs (about 5 minutes, about $0.50):
   `.venv/bin/python -m radar.evaluate`. Every query should show ✓.
2. In the app, run the three demo queries live (tick **Run live**): **semaglutide**,
   **denosumab**, and the STBI incubatee's target if you know it.
3. Read each brief once. Click two citations in each to check they open.
4. Offline check: turn Wi-Fi off, open each demo search from the **Search history** sidebar.
   It must appear instantly with "The saved brief from …". Turn Wi-Fi back on.
5. Set a monthly spend cap in the Anthropic Console before sharing any link (F22).

## In the meeting

| Minute | What | In the app |
| --- | --- | --- |
| 0–2 | Ask how their startups track new research today. Listen. | — |
| 2–3 | One line on Prowonix AI Lab and Literature Radar. | Home page |
| 3–7 | Live run | Type **semaglutide** (Run live ticked) → wait ~20 s for the progress steps → read *In one line* → click two citations → open the **India** tab (CDSCO SEC recommendations for Sun, Alkem, Zydus; Biocon and Dr. Reddy's trials) → **Run details** (support %, cost ≈ $0.05). Then ask for their target and run it. |
| 7–9 | The bigger picture: patents, weekly watch reports, QA document work. | **Sources** tab: "Why this paper?" scores |
| 9–10 | The ask: an Idea Doodle Lab place and introductions to three incubatees. | Download the PDF and offer to send it |

Demo line: "A chatbot gives you an answer. Literature Radar gives you a checked answer,
the India picture global tools miss, and the sources behind every line."

## If something goes wrong

- **Wi-Fi or an API is down:** run the query anyway. The app shows the last saved brief with
  a "Live sources are unreachable" note. Or open it from the history sidebar.
- **Their target finds nothing:** switch to the 12-month window, or try a brand name or gene
  symbol. The app suggests this itself.
- **An abbreviation like "MS" or "PD":** the app asks which meaning; pick one.
- **A claim shows ⚠ partly supported:** that is the verifier working. Say so; it is the point.

## Numbers to quote (evaluation of 25 Oct 2026, docs/eval/2026-10-25-after-search-fix.md)

- 10 queries: 0 invalid citations; 97% of claims supported; median 16 s per brief; about
  $0.047 per brief.
- Verifier probe: caught 8 of 8 deliberately wrong claims, passed 6 of 6 true ones.
