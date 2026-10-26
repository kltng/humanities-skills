---
name: yale-library-catalog
description: Search the Yale University Library catalog (Alma) through its public SRU interface, and Yale LUX (libraries, museums, and archives) through its JSON API. Use this skill whenever the user wants to look up items at Yale, check whether Yale holds a book and where it is shelved, search by title/author/subject/ISBN/OCLC/call number, read MARC records with vernacular (880) script fields, find Yale museum objects, archives, people, or places in LUX, or compare Yale holdings with other libraries. Returns call numbers, locations, availability, and online access links.
version: 1.0.1
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# Yale University Library Catalog Skill

Search Yale's library catalog (Alma) for print and online holdings. No API key needed.

## Overview

Yale runs its catalog on Ex Libris **Alma**. Alma has a public **SRU** interface (Search/Retrieve via URL, a library standard for searching catalogs over plain HTTP). Queries are written in **CQL** (Contextual Query Language, e.g. `alma.title="明史"`). Records come back as MARCXML; the script turns them into simple JSON.

```
https://yale.alma.exlibrisgroup.com/view/sru/01YALE_INST
  ?version=1.2&operation=searchRetrieve&recordSchema=marcxml
  &query=alma.title="明史"&maximumRecords=10
```

## Critical: Things Claude Won't Know Without This Skill

### Use Alma SRU for the catalog, not Quicksearch

Yale's Quicksearch site (search.library.yale.edu) answers scripts with an empty HTTP 202 bot-check response. Yale also has an official "AI Connector" MCP server (announced 15 October 2026), but it is in beta for the Yale community only. Alma SRU is open and needs no key. Give people `search.library.yale.edu/catalog/{mms_id}` links to open in a browser.

### Online holdings include direct links

Yale's AVE fields carry `$u`, an access link (OpenURL). The script returns it as `holdings.electronic[].url`. Access still needs a Yale login.

### LUX: Yale's libraries, museums, and archives together

LUX (lux.collections.yale.edu) searches the library catalog together with the Yale art galleries, Peabody Museum, Beinecke, and archives. It returns Linked Art JSON-LD. Use it for objects, artworks, people, places, and archival collections. Use Alma SRU for book holdings and call numbers.

- Search returns only entity URIs; `scripts/lux_api.py` fetches each one and summarizes it (one extra request per result).
- Scopes: `item` (physical/digital objects), `work` (texts, images), `agent` (people, groups), `place`, `concept`, `event`, `set` (collections).
- Queries are JSON: `{"text": "明史"}`, `{"name": "Wen Zhengming"}`, `{"AND": [{"text": "Ming"}, {"producedBy": {"name": "Wen Zhengming"}}]}`.
- `GET /api/search-info` lists every search term per scope; `GET /api/translate/{scope}?q=...` turns plain words into a JSON query.
- Agent records give many name forms (e.g. 文徵明, Wen Zhengming, Wen, Cheng-ming, 衡山居士), which helps match names across catalogs.

### Holdings are in the AVA and AVE fields

- **AVA** = print/physical copy. `$q` library name, `$c` location, `$d` call number, `$e` available/unavailable, `$f` item count, `$t` volume summary.
- **AVE** = online copy. `$m` collection, `$t` interface (platform), `$e` Available, `$n` note, `$u` access link (when supplied).

The script reads both into `holdings.physical` and `holdings.electronic`. Keys: `holdings.physical[]` has `library`, `location`, `call_number`, `availability`, `items_total`, `items_unavailable`, `summary`; `holdings.electronic[]` has `collection`, `interface`, `availability`, `note`, `url`. Much of Yale's print collection is at the Library Shelving Facility (`$q` = `Library Shelving Facility`); people request those items for use at any Yale library.

### Chinese/Japanese/Korean script is in 880 fields

The main fields (245 title, 100 author, 260/264 publisher) are **romanized** (pinyin, Hepburn, McCune-Reischauer). The original script is in a linked **880** field. The script pairs them, so `title` reads like `明史 (Ming shi)`. Search in both scripts: `alma.title="明史"` and `alma.title="Ming shi"` return different sets.

### Title searches match words, not phrases

- `alma.title="shi dian"` matches records with *shi* and *dian* anywhere in the title (353 hits at U-M, including a Shenyang phone book). Quotes and `adj` change nothing; `==` matches the whole title field exactly.
- Use `phrase=True` (CLI `--phrase`) to keep only titles that contain the term as one connected phrase. It filters each page after the search, so `total` is still the server's count; use `search_all(..., phrase=True)` to scan every page.
- Pinyin syllables stay ambiguous: `shi dian` also matches 知识典籍 (*zhi shi dian ji*), and `ji qi` is 機器 as well as 祭器. After a romanized search, keep the records whose vernacular title has the characters you want.
- **A CJK title search can also miss titles that contain the term.** Alma splits CJK titles into words with a dictionary: 文廟祀典考 is indexed as 文 / 廟祀 / 典考, so `alma.title="文廟"` misses it at U-M and Princeton (Yale finds it). The romanized `Wen miao` finds it.
- So never treat one CJK title search as complete. Search the traditional, simplified, and romanized forms (文廟, 文庙, Wen miao) and merge the results by `mms_id`.

### Limits and quirks

- **50 records per request** at most. Page with `startRecord` (1-based); `search_all()` does this for you.
- **Sort** goes inside the CQL: `... sortBy alma.main_pub_date/sort.descending`. The `sortKeys` parameter is ignored. Records with unknown dates (`uuuu`) sort first in ascending order; add `cql="alma.main_pub_date>=1000"` to drop them.
- **Default order is not relevance ranking.** Narrow the query (title + language, or a date range) rather than relying on the first results.
- **Subject headings:** write LCSH as plain words, without ` -- `, in LC's inverted form. `alma.subjects="Confucius Cult"` works; `"Confucius -- Cult"` gives 0. `"Temples, Confucian"` works; `"Confucian temples"` gives 0.
- **Unknown index names** fail with a vague "Catalog search has encountered an error". Check the spelling against `references/api_reference.md`.
- **Encode the query** with normal URL encoding. Raw Chinese or quotes in the URL give HTTP 400.

## When to Use

- "Does Yale have X?" / "Where is X shelved at Yale?"
- Finding Chinese, Japanese, or Korean books in Yale's East Asian collections
- Finding pre-modern editions with a date range (`alma.main_pub_date<1900`)
- Getting MARC data (OCLC, LCCN, ISBN, subjects) for a known item
- Comparing holdings across libraries

## Quick Start

### CLI

```bash
python scripts/yale_api.py search --title 明史 --language chi --limit 5
python scripts/yale_api.py search --author "Spence, Jonathan D." --sort date_desc
python scripts/yale_api.py search --cql 'alma.title=明史 and alma.main_pub_date<1900' --sort date_asc
python scripts/yale_api.py search --call-number 'DS753*' --json
python scripts/yale_api.py record 99129140223408651
python scripts/yale_api.py record 99129140223408651 --raw   # all MARC fields
```

### Python

```python
from scripts.yale_api import YaleCatalogAPI

lib = YaleCatalogAPI()
result = lib.search(title="明史", language="chi", sort="date_asc",
                    cql="alma.main_pub_date>=1000", limit=10)
print(result["total"])
for rec in result["records"]:
    print(rec["title"], rec["year"])
    for h in rec["holdings"]["physical"]:
        print("  ", h["library"], h["call_number"], h["availability"])

lib.search(oclc="424023")                        # exact identifier lookups
lib.search(isbn="9787101003277")
lib.search_all(subject="China History Ming dynasty", max_results=200)
lib.get_record("99129140223408651")                 # one record by MMS ID
```

Search fields: `keyword`, `title`, `author`, `subject`, `isbn`, `issn`, `oclc`, `lccn`, `publisher`, `series`, `call_number`, `language` (MARC code: `chi`, `jpn`, `kor`, `eng`), `mms_id`. Sort: `date_desc`, `date_asc`, `title`, `author`.

Each summary has `mms_id`, `title`, `titles` (romanized + vernacular), `author`, `authors`, `contributors`, `edition`, `publication`, `year`, `language`, `physical_description`, `series`, `subjects`, `isbns`, `oclc`, `lccn`, `lc_call_number`, `holdings`, and `url` (the public record page).

### LUX (libraries, museums, archives)

```bash
python scripts/lux_api.py search 明史 --scope work --limit 5
python scripts/lux_api.py search "Wen Zhengming" --scope agent --field name
python scripts/lux_api.py search --scope item --query '{"AND":[{"text":"Ming"},{"producedBy":{"name":"Wen Zhengming"}}]}'
python scripts/lux_api.py get https://lux.collections.yale.edu/data/person/7ffd4495-8917-4e92-b30d-fc3cd1d38c2b
```

```python
from scripts.lux_api import LuxAPI
lux = LuxAPI()
res = lux.search("文徵明", scope="item", limit=5)   # fetches each result
for r in res["results"]:
    print(r["label"], r["classified_as"], r["links"])
```

Each LUX summary has `id`, `type`, `label`, `names`, `identifiers`, `classified_as`, `languages`, `makers`, `dates`, `member_of`, `notes`, `equivalent` (links to other databases), and `links` (e.g. the Yale catalog record).

## Best Practices

1. **Search both scripts** (Chinese characters and romanization) for full coverage.
2. **Narrow with `language`** (`chi`, `jpn`, `kor`) when a title word is common.
3. **Match across catalogs with `oclc` or `isbn`.** These are exact.
4. **Give people the `url`** so they can see live status and request items in a browser.
5. **Respect the server.** The script waits 1 second between requests and backs off on HTTP 429/503 with `Retry-After`. Do not page through thousands of records.

## Related Skills

- **alma-sru-catalogs**: search this library and 14 others (Oxford, Cambridge, Toronto, Berkeley, …) in one call
- **umich-library-catalog**, **princeton-library-catalog**, **yale-library-catalog**, **pitt-library-catalog**: the same Alma SRU method at other libraries
- **harvard-library-catalog**, **columbia-clio**, **loc-catalog**: other catalogs to compare holdings
- **hathitrust-catalog**: use OCLC numbers from here to find digitized copies
- **zotero-local**: save found records into Zotero

## Resources

- `references/api_reference.md` — SRU parameters, CQL syntax, index list, MARC and AVA/AVE field guide
- `scripts/yale_api.py` — Alma SRU client and CLI (zero dependencies)
- `tests/test_yale_api.py` — offline tests (`python -m unittest discover -s tests`)
- `scripts/lux_api.py` — LUX client and CLI (zero dependencies)
- `tests/test_lux_api.py` — offline LUX tests
- LUX API docs: https://github.com/project-lux/lux-middletier/blob/main/docs/api-endpoints.md
- Ex Libris SRU docs: https://developers.exlibrisgroup.com/alma/integrations/sru/

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "yale-library-catalog"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[yale-library-catalog] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: yale-library-catalog* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
