# Glossary

Domain terms met while building, one line each. Add to it every session.

## Literature (PubMed)

- **PubMed**: free search engine over MEDLINE and other biomedical literature, run by the US National Library of Medicine (NLM).
- **PMID**: PubMed's unique numeric ID for a record; cited in briefs as `[PMID:…]`.
- **E-utilities**: NCBI's public HTTP API for PubMed; `esearch` returns PMIDs, `efetch` returns full records.
- **MeSH (Medical Subject Headings)**: NLM's controlled vocabulary; indexers tag each paper with MeSH terms, so a MeSH search finds papers that use other words for the same concept.
- **[tiab]**: PubMed field tag meaning "title or abstract".
- **pdat / reldate**: publication-date field, and "published within the last N days".
- **Publication type**: NLM label for what kind of record a paper is (Journal Article, Review, Meta-Analysis, Randomized Controlled Trial, Retracted Publication…); used for tagging instead of guessing from text.
- **Review**: summarises earlier studies rather than reporting new data.
- **Systematic review**: a review that searches and selects studies by a predefined, reproducible method.
- **Meta-analysis**: statistically pools results from several studies into one estimate.
- **Retracted publication**: a paper withdrawn by its journal (error, misconduct, duplication); excluded from briefs (F23).
- **Retraction notice**: the separate record announcing a retraction; linked via `RetractionIn` / `RetractionOf`.
- **Structured abstract**: abstract split into labelled parts such as BACKGROUND, METHODS, RESULTS, CONCLUSIONS.
- **E-pub date**: date a paper appeared online (`ArticleDate`), often months before the journal issue date.
- **MedlineDate**: free-text date used when a journal issue spans months or seasons, e.g. "2026 Jan-Feb".
- **Collective author**: a group credited as author, e.g. a trial's investigators.

## Molecules and targets

- **Semaglutide**: GLP-1 receptor agonist used for type 2 diabetes and obesity; India patent expired March 2026.
- **GLP-1 receptor agonist**: drug that mimics the gut hormone GLP-1, raising insulin release and reducing appetite.
- **Liraglutide**: an older, daily GLP-1 receptor agonist; semaglutide's usual comparator.
- **PCSK9**: liver protein that lowers LDL-receptor numbers; blocking it lowers LDL ("bad") cholesterol.
- **LDL-C**: low-density lipoprotein cholesterol.
