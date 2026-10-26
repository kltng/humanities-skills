---
name: mit-timdex
description: Search MIT Libraries through TIMDEX, MIT's official public GraphQL discovery API (no API key) — the MIT library catalog, DSpace@MIT theses and papers, MIT ArchivesSpace archival collections, MIT digital collections (images), GIS data, research databases, and LibGuides in one index. Use this skill whenever the user wants to find books or e-books at MIT, MIT theses or working papers, MIT archives, or MIT digital images; search by title, author, subject, or identifier; filter by source, language, or format; or run semantic (vector) search over MIT records.
version: 1.0.2
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# MIT TIMDEX Skill

Search MIT Libraries' catalog, repository, archives, and digital collections in one API. No API key needed.

## Overview

**TIMDEX** is MIT Libraries' official discovery API. It is a **GraphQL** API: you send one POST request to one URL, with a query that names the fields you want back.

```
POST https://timdex.mit.edu/graphql
{"query": "{ search(searchterm: \"明史\") { hits records { title sourceLink } } }"}
```

| Source (`--source`) | Content |
|---|---|
| `MIT Alma` | Library catalog: books, e-books, journals, media (~480,000 records) |
| `DSpace@MIT` | Theses, working papers, articles |
| `MIT ArchivesSpace` | Archival collections and finding aids |
| `Digital Collections` | Images (e.g. architecture and art slides) |
| `MIT GIS Resources` | Geospatial data |
| `Research Databases`, `LibGuides`, `MIT Libraries Website` | Guides and database listings |

## Critical: Things Claude Won't Know Without This Skill

### Prefer TIMDEX over Alma SRU for MIT

MIT also has an Alma SRU endpoint (see **alma-sru-catalogs**), but it finds far fewer records: 2 for `明史`, against 591 in TIMDEX. TIMDEX also covers DSpace and ArchivesSpace.

### Field names are exact and case-sensitive

GraphQL rejects unknown fields with an error such as `Field 'callNumber' doesn't exist on type 'Holding'` (it is `callnumber`). The script asks for a tested field list. Use `TimdexAPI.query()` for custom queries.

### Search arguments vs. filters

- **Search** (relevance-ranked): `searchterm` (all fields), `title`, `contributors`, `subjects`, `identifiers`, `locations`, `citation`.
- **Filters** (exact values from the facet counts): `source`, `content_type`, `language` (lowercase, e.g. `chinese`), `format`, `subject_filter`, `contributor_filter`, `place`, `literary_form`, `access`. Run with `--facets` to see the values.
- **Modes**: `keyword` (default), `semantic` (vector search, good for concepts like "Ming dynasty painting"), `hybrid`.
- **Words** are joined with OR by default. `--boolean AND` requires all words, but **only for `searchterm`**: field searches (`--title`, `--subjects`, …) ignore it (`title="Ming shi"` gives 1369 hits with or without AND).

### CJK and phrase searches

- A **title** search for a CJK term matches any one of its characters: `title="文廟"` returns 1122 records (华文文学, 文化文本, …), and AND cannot narrow it.
- Use `searchterm` with AND instead, then keep the titles that really contain the term with `phrase=True` (CLI `--phrase`). `明史` → 26 records with AND → 2 with the phrase filter (明史研究, 明史研究論叢). Even AND alone is not a phrase search: `searchterm="文廟"` with AND returns two titles without 文廟.
- `phrase=True` filters each page after the search, so `total` is the server's count and `returned` is the page size before filtering. Page through with `start` to scan more.
- Pinyin syllables stay ambiguous (`Ming shi` also matches *jian ming shi*). Check the records.

### Paging

`start` is a 0-based offset (`from` in GraphQL); `limit` is `perPage` (default 20).

## Quick Start

### CLI

```bash
python scripts/timdex_api.py search 明史 --limit 5 --facets
python scripts/timdex_api.py search 明史 --boolean AND --phrase --limit 50     # titles containing 明史
python scripts/timdex_api.py search --title "Ming shi" --source "MIT Alma" --language chinese
python scripts/timdex_api.py search "Ming dynasty painting" --mode semantic
python scripts/timdex_api.py search --subjects China --source "DSpace@MIT"
python scripts/timdex_api.py search --subjects China --source "MIT ArchivesSpace"
python scripts/timdex_api.py search --identifiers 9789863503996      # ISBN or OCLC number
python scripts/timdex_api.py record alma:9936111333206761
```

### Python

```python
from scripts.timdex_api import TimdexAPI

mit = TimdexAPI()
result = mit.search("明史", source="MIT Alma", language="chinese", limit=10, facets=True)
print(result["total"], result["facets"]["source"])
for rec in result["records"]:
    print(rec["title"], rec["publishers"], rec["url"])

mit.search("明史", boolean="AND", phrase=True, limit=50)   # titles containing 明史
mit.search("Ming shi", boolean="AND", start=20, limit=20)  # page 2 (AND works on searchterm only)
mit.get_record("alma:9936111333206761")
mit.query("{ search(title: \"Ming\") { hits } }")                # raw GraphQL
```

Each summary has `id`, `title`, `alternate_titles`, `source`, `content_type`, `format`, `languages`, `contributors`, `dates`, `publishers`, `edition`, `physical_description`, `summary`, `subjects`, `identifiers` (by kind, e.g. ISBN, OCLC Number), `call_numbers`, `holdings`, `links`, `citation`, and `url` (the record page in Primo, DSpace, or ArchivesSpace).

## Best Practices

1. **Filter by `source`** when you want only books (`MIT Alma`) or only theses (`DSpace@MIT`).
2. **Use `--facets` first** on broad searches to see sources, languages, and formats.
3. **Try semantic mode** for topical questions phrased in plain English.
4. **Wait 1 second between requests.** The script does this, and retries dropped connections, timeouts, and HTTP 429/5xx (waiting 5, 10, 20 s).

## Related Skills

- **alma-sru-catalogs**: the same search across 20 other research libraries (US, UK, Canada, Australia, Taiwan)
- **hathitrust-catalog**: digitized copies by OCLC or ISBN
- **arxiv-search**: preprints (MIT authors often post there)

## Resources

- `references/api_reference.md` — endpoint, arguments, filters, record fields, examples
- `scripts/timdex_api.py` — client and CLI (zero dependencies)
- `tests/test_timdex_api.py` — offline tests
- TIMDEX docs: https://mitlibraries.github.io/timdex/

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "mit-timdex"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[mit-timdex] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: mit-timdex* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
