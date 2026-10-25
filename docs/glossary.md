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

## Clinical trials (ClinicalTrials.gov)

- **ClinicalTrials.gov**: US NIH registry of clinical studies worldwide; API v2 at `/api/v2/studies`.
- **NCT ID**: ClinicalTrials.gov's study ID, "NCT" + 8 digits; cited as `[NCT…]`.
- **Interventional study**: participants are assigned a treatment by the protocol; these have phases.
- **Observational study**: researchers watch outcomes without assigning treatment; no phase (`phases` missing).
- **Early Phase 1 (Phase 0)**: tiny, short exposure in humans to check how a drug behaves, no therapeutic intent.
- **Phase 1**: first in humans, small groups; safety and dosing range.
- **Phase 2**: a few hundred patients; does it work, and at what dose; more safety data.
- **Phase 3**: large, often randomised versus standard care or placebo; the evidence for approval.
- **Phase 4**: after approval; long-term safety and real-world use.
- **Phase NA**: "not applicable" — device, behavioural or procedure studies without drug phases.
- **Overall status**: NOT_YET_RECRUITING, RECRUITING, ENROLLING_BY_INVITATION, ACTIVE_NOT_RECRUITING (running, enrolment closed), COMPLETED, SUSPENDED, TERMINATED (stopped early), WITHDRAWN (stopped before enrolling anyone), UNKNOWN (not updated past its due date).
- **Lead sponsor**: organisation responsible for the trial (company, university, hospital).
- **Last update post date**: when the record was last changed on the registry; used for the time window.
- **Brief summary**: the registry's short plain-language description of the study.
- **Placebo**: inactive look-alike treatment given to the control group.
- **Double-blinded**: neither participants nor investigators know who gets which treatment.

## Molecules and targets (cont.)

- **Denosumab**: monoclonal antibody against RANKL that slows bone breakdown; for osteoporosis and bone metastases; new biosimilar wave in India.
- **Tirzepatide**: dual GIP/GLP-1 receptor agonist; semaglutide's main competitor.
- **Biosimilar**: a near-identical copy of an approved biological drug, approved after the original's patents expire.

## India (CTRI, CDSCO)

- **CTRI (Clinical Trials Registry – India)**: India's official trial registry at ctri.nic.in; registration is mandatory for trials run in India. IDs look like `CTRI/2025/06/088110`.
- **CDSCO (Central Drugs Standard Control Organisation)**: India's national drug regulator, which approves new drugs, biosimilars and trials.
- **SEC (Subject Expert Committee)**: CDSCO's expert panel per therapy area (e.g. Endocrinology & Metabolism); it *recommends*, and CDSCO then decides. A recommendation is not an approval.
- **NDCT Rules 2019 (New Drugs and Clinical Trials Rules)**: the Indian law governing new-drug approval and trials.
- **Bioequivalence (BE) study**: shows a copy drug reaches the blood at the same rate and amount as the original; the usual evidence for generics.
- **Non-inferiority trial**: tests that a new treatment is not meaningfully worse than an existing one, rather than better.
- **PMS (post-marketing surveillance)**: safety monitoring after a drug is on sale; SECs often make it a condition of approval.
- **PSUR (Periodic Safety Update Report)**: a regular safety report the marketer must file after approval.
- **Subacute toxicity study**: an animal study of repeated doses over weeks, looking for organ damage before human trials.
- **Synthetic semaglutide**: made by chemical peptide synthesis rather than in engineered cells (recombinant), as Indian generics often are.
- **Pre-filled pen**: an injection device loaded with the drug, as used for Ozempic and Wegovy.
- **CKD-MBD**: chronic kidney disease–mineral and bone disorder; a label warning added for denosumab.
- **PK/PD study**: pharmacokinetics (what the body does to the drug) and pharmacodynamics (what the drug does to the body).

## Brief and verification

- **Grounding**: the model may use only the records it is given, each tagged with its ID.
- **Citation check (F6)**: code drops any claim whose ID is malformed or was not fetched.
- **Claim verification (F17)**: a second model labels each claim supported, partial or unsupported against its cited records; unsupported claims are removed.
- **Faithfulness (support rate)**: supported claims ÷ verified claims; the demo target is at least 90%.
