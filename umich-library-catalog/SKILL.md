---
name: umich-library-catalog
description: Search the University of Michigan Library catalog (Alma) through its public SRU interface for books, journals, manuscripts, microfilm, and e-resources, including its strong Asia Library holdings in Chinese, Japanese, and Korean. Use this skill whenever the user wants to look up items at U-M or "Michigan" libraries, check whether U-M holds a book and where it is shelved, search by title/author/subject/ISBN/OCLC/call number, read full MARC records with vernacular (880) script fields, or compare U-M holdings with Harvard, Columbia, or LOC. Returns call numbers, locations, availability, and online access.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# University of Michigan Library Catalog Skill

Search U-M Library's catalog (Alma) for print and online holdings. No API key needed.

## Overview

U-M runs its catalog on Ex Libris **Alma**. Alma has a public **SRU** interface (Search/Retrieve via URL, a library standard for searching catalogs over plain HTTP). Queries are written in **CQL** (Contextual Query Language, e.g. `alma.title="明史"`). Records come back as MARCXML.

```
https://umich.alma.exlibrisgroup.com/view/sru/01UMICH_INST
  ?version=1.2&operation=searchRetrieve&recordSchema=marcxml
  &query=alma.title="明史"&maximumRecords=10
```

## Critical: Things Claude Won't Know Without This Skill

### Do not use Library Search (search.lib.umich.edu) or the Spectrum MCP

U-M's public search site and its backend API (`search.lib.umich.edu/spectrum/...`) sit behind a Cloudflare bot check. Scripts get **HTTP 403** with a "Just a moment…" page. The `mlibrary/spectrum` repo has an MCP server, but it only runs inside U-M. Use Alma SRU instead. Use `search.lib.umich.edu/catalog/record/{mms_id}` only as a link for people to open in a browser.

### Holdings are in the AVA and AVE fields

Each MARC record includes Alma availability fields:

- **AVA** = print/physical copy. `$q` library name, `$c` location, `$d` call number, `$e` available/unavailable, `$f` item count, `$t` volume summary.
- **AVE** = online copy. `$m` collection, `$t` platform, `$e` Available.

The script reads both into `holdings.physical` and `holdings.electronic`.

### Chinese/Japanese/Korean script is in 880 fields

Like most US catalogs, the main fields (245 title, 100 author, 260/264 publisher) are **romanized** (pinyin, Hepburn, McCune-Reischauer). The original script is in a linked **880** field. The script pairs them, so `title` reads `八史經籍志 (Ba shi jing ji zhi)`.

You can search in either script. `alma.title="明史"` and `alma.title="Ming shi"` both work but return different sets, so try both for full coverage.

### Limits and quirks

- **50 records per request** at most (`maximumRecords`). Page with `startRecord` (1-based).
- **Sort** goes inside the CQL, not in a separate parameter: `... sortBy alma.main_pub_date/sort.descending`. The `sortKeys` parameter is ignored. Sortable: `title`, `creator`, `main_pub_date`.
- **Unknown index names** fail with a vague "Catalog search has encountered an error". Check the spelling against `references/api_reference.md`.
- **Encode the query** with normal URL encoding (`urllib.parse.quote`). Raw Chinese or quotes in the URL give HTTP 400.
- **Truncation**: `alma.lc_class_number=DS753*` (no quotes around the term).

## When to Use

- "Does Michigan have X?" / "Where is X shelved at U-M?"
- Finding Chinese, Japanese, or Korean books at the U-M Asia Library
- Finding rare or pre-modern editions (e.g. Ming/Qing imprints, microfilm in `FILM CS ...`)
- Getting MARC data (OCLC, LCCN, ISBN, subjects) for a known item
- Comparing holdings across Harvard, Columbia, LOC, and U-M

## Quick Start

### CLI

```bash
# Title search in Chinese, Chinese-language only, oldest first
python scripts/umich_api.py search --title 明史 --language chi --sort date_asc --limit 5

# Author search
python scripts/umich_api.py search --author "Brook, Timothy" --limit 10

# Raw CQL: pre-1700 imprints with 明史 in the title
python scripts/umich_api.py search --cql 'alma.title=明史 and alma.main_pub_date<1700'

# Call number range, JSON output
python scripts/umich_api.py search --call-number 'DS753*' --json

# One record by MMS ID; --raw for all MARC fields
python scripts/umich_api.py record 990023071550106381
python scripts/umich_api.py record 990023071550106381 --raw
```

### Python

```python
from scripts.umich_api import UMichCatalogAPI

um = UMichCatalogAPI()

result = um.search(title="明史", language="chi", sort="date_asc", limit=10)
print(result["total"])
for rec in result["records"]:
    print(rec["title"], rec["year"])
    for h in rec["holdings"]["physical"]:
        print("  ", h["library"], h["call_number"], h["availability"])

# Combine fields (AND) or add raw CQL
um.search(author="王守仁", subject="Philosophy, Chinese")
um.search(cql="alma.main_pub_date>=1600 and alma.main_pub_date<1700", keyword="王陽明")

# Identifier lookups
um.search(isbn="9787101003277")
um.search(oclc="424023")

# More than 50 results
records = um.search_all(subject="China History Ming dynasty", max_results=200)

# Single record
rec = um.get_record("990023071550106381")
marc = um.get_record("990023071550106381", raw=True)  # full MARC fields
```

Search field names: `keyword`, `title`, `author`, `subject`, `isbn`, `issn`, `oclc`, `lccn`, `publisher`, `series`, `call_number`, `language` (MARC code: `chi`, `jpn`, `kor`, `eng`), `mms_id`. Sort: `date_desc`, `date_asc`, `title`, `author`.

### Summary record shape

```json
{
  "mms_id": "990023071550106381",
  "title": "八史經籍志 (Ba shi jing ji zhi)",
  "titles": [{"romanized": "Ba shi jing ji zhi", "vernacular": "八史經籍志"}],
  "author": "",
  "publication": "[蘇州] : [振新印書社], 光緖8年 [1882] ([Suzhou] : ...)",
  "year": "1882",
  "language": "chi",
  "subjects": ["..."],
  "isbns": [], "oclc": ["..."], "lccn": [],
  "lc_call_number": "Z3102 .P15",
  "holdings": {
    "physical": [{"library": "Buhr Shelving Facility", "location": "Main",
                  "call_number": "Z 3102 .P15", "availability": "available",
                  "items_total": "2", "items_unavailable": "0", "summary": "(v.1-16 1883)"}],
    "electronic": []
  },
  "url": "https://search.lib.umich.edu/catalog/record/990023071550106381"
}
```

## Best Practices

1. **Search both scripts.** Run the Chinese-script and the romanized form of a title; records differ in how fully they are romanized or linked.
2. **Narrow with `language`** (`chi`, `jpn`, `kor`) when a title word is common in many languages.
3. **Use `oclc` or `isbn` to match** an item found in another catalog. These are exact.
4. **Give people the `url`** so they can see live circulation status, request items, or check "Get This" options in a browser.
5. **Respect the server.** The script waits 1 second between requests and backs off on HTTP 429/503 with `Retry-After`. Do not loop over thousands of pages.

## Related Skills

- **hathitrust-catalog**: U-M is HathiTrust's founding partner. Use OCLC numbers from here to find digitized copies.
- **harvard-library-catalog**, **columbia-clio**, **loc-catalog**: compare holdings across libraries
- **zotero-local**: save found records into Zotero
- **cbdb-local**: identify authors of Chinese works

## Resources

- `references/api_reference.md` — SRU parameters, CQL syntax, index list, MARC and AVA/AVE field guide
- `scripts/umich_api.py` — Python client and CLI (zero dependencies)
- `tests/test_umich_api.py` — offline tests (`python -m unittest discover -s tests`)
- Ex Libris SRU docs: https://developers.exlibrisgroup.com/alma/integrations/sru/

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "umich-library-catalog"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[umich-library-catalog] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: umich-library-catalog* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
