---
name: harvard-library-catalog
description: Search Harvard Library's 13M+ bibliographic records via LibraryCloud and retrieve MARC/MODS data via PRESTO. Use this skill whenever the user wants to look up books, manuscripts, finding aids, or other items in Harvard's library catalog, verify bibliographic information (title, author, ISBN, publication date), find digital collections, or retrieve detailed catalog records. Also triggers when a user extracts a book title from a document and wants to find its full bibliographic metadata.
version: 1.0.3
---

# Harvard Library API Skill

Search and retrieve bibliographic records from Harvard Library's catalog of 13M+ items.

## Critical: Things Claude Won't Know Without This Skill

### LibraryCloud field-based search uses query parameters, NOT Solr syntax

The Item API uses **field names as query parameters** — not `q=field:value` Solr syntax.

```
CORRECT:   https://api.lib.harvard.edu/v2/items.json?title=hamlet&name=shakespeare
WRONG:     https://api.lib.harvard.edu/v2/items?q=title:hamlet
```

The `q=` parameter is for **keyword search across all fields**. Field-specific search uses dedicated parameters like `title=`, `name=`, `subject=`, `identifier=`, etc.

### Search CJK and romanized titles differently

Field searches treat CJK text and romanized (pinyin, Hepburn, etc.) text differently. Counts below were measured on 26 October 2026.

**CJK: put the term in double quotes.** Unquoted CJK is split into single characters and any character can match.

| Query | Results |
|---|---|
| `title=天工開物` | 88,962 (noise) |
| `title="天工開物"` | 16 (all relevant) |
| `title=文廟` | 168,900 (top hit is a book on 聖母廟) |
| `title="文廟"` | 47 |

A quoted CJK term also matches inside longer words: `title="明史"` (700) finds 日本文明史 too. Check the titles you get back.

**Romanized words: do not quote them.** Plain words are already ANDed (all words must appear, in any order). Quoted pinyin phrases of three or more syllables return 0, and two-syllable quotes match across word breaks (`"wen miao"` finds *Shen Congwen miao yu lu*).

| Query | Results |
|---|---|
| `title=tian gong kai wu` (same as `tian AND gong AND kai AND wu`) | 22 |
| `title_exact=Tian gong kai wu` (the words as one phrase) | 5 |
| `title="tian gong kai wu"` | 0 |
| `title="si ku quan shu"` / `title="Hui zhou fu zhi"` | 0 / 0 |
| `title=Hui zhou fu zhi` | 48 (loose: any title with all four syllables) |
| `title="great gatsby"` | 0 |
| `title=great gatsby` / `title_exact=great Gatsby` | 116 / 16 |

So: for a known Chinese, Japanese or Korean title, search the original script in quotes first. With only a romanized title, use plain words, then `title_exact` to narrow. Pinyin syllables are ambiguous, so check the original-script title of each hit (`get_title()` shows it, see below).

For subject headings, use `subject_exact` with the heading as written, without quotes: `subject_exact=Temples, Confucian` → 65 (`subject=Temples, Confucian` → 176 loose matches; `subject="Temples, Confucian"` → 0).

```python
api.search(title='"文廟"')                       # CJK: the quotes are part of the value
api.search(title="tian gong kai wu")             # romanized: no quotes
api.search(title_exact="Tian gong kai wu")       # romanized phrase
api.search(subject_exact="Temples, Confucian")
```

### MODS fields can be a string, a dict, or a list

LibraryCloud converts MODS XML to JSON, so the same field takes different shapes: `"text"`, `{"#text": "text", "@type": ...}`, or a list of either. `titleInfo.subTitle` can be `["8 juan"]`, `originInfo.publisher` a list of two publishers, `relatedItem.titleInfo.partNumber` `[1]`. Do not call `.strip()` on a raw field. Use `mods_text()` (also `api.text()`), which turns any of these into one string, or the `get_*`/`summarize()` helpers, which use it:

```python
from scripts.harvard_api import mods_text
mods_text(record["titleInfo"][0].get("subTitle"))   # '8 juan'
```

### Original-script titles

For CJK and other non-Latin books, `titleInfo` is a list. The romanized title and the original-script title share one `@altRepGroup`:

```
[{"@altRepGroup": "02", "title": "Tian gong kai wu", "subTitle": "3 juan"},
 {"@altRepGroup": "02", "title": "天工開物", "subTitle": "三卷"}]
```

`get_title()` shows both, original script first: `天工開物 : 三卷 (Tian gong kai wu : 3 juan)`. `get_title(record, original=False)` gives only the romanized form. `get_original_title()` gives only the original script (empty if there is none). `summarize()` returns `title`, `title_romanized` and `title_original`.

### JSON requires `.json` in the URL path

Responses are XML by default. To get JSON, append `.json` before the query string:

```
JSON:        https://api.lib.harvard.edu/v2/items.json?title=hamlet
Dublin Core: https://api.lib.harvard.edu/v2/items.dc.json?title=hamlet
Default XML: https://api.lib.harvard.edu/v2/items?title=hamlet
```

### PRESTO is for direct record lookup by HOLLIS ID

PRESTO returns raw MARC, MODS, or Dublin Core for a single record by its HOLLIS number. It complements LibraryCloud when you need the original catalog record:

```
MARC: https://webservices.lib.harvard.edu/rest/marc/hollis/{HOLLIS_ID}
MODS: https://webservices.lib.harvard.edu/rest/mods/hollis/{HOLLIS_ID}
DC:   https://webservices.lib.harvard.edu/rest/dc/hollis/{HOLLIS_ID}
```

PRESTO returns XML only and does not support JSON serialization. ISBN/barcode lookups may not work on all records.

### User-Agent header is required

LibraryCloud returns 403 without a User-Agent header. Always include one:

```bash
curl -H 'User-Agent: MyApp/1.0' 'https://api.lib.harvard.edu/v2/items.json?title=hamlet'
```

The Python script includes this automatically.

### Rate limit: max 1 request/second, 300 per 5 minutes

Exceeding this triggers a 5-minute lockout. The Python script handles this automatically.

## Choosing an Access Method

| Need | Method |
|------|--------|
| Search by title, author, subject, date | LibraryCloud Item API (field params) |
| Full-text keyword search | LibraryCloud Item API (`q=` param) |
| Look up by ISBN, LCCN, or other identifier | LibraryCloud `identifier=` or `q=` keyword |
| Browse digital collections | LibraryCloud `collectionTitle=` or Collections API |
| Get raw MARC record for a known HOLLIS ID | PRESTO `/rest/marc/hollis/{id}` |
| Faceted browsing (by language, date, genre) | LibraryCloud `facets=` parameter |

## Typical Workflow: Book Title to Full Bibliography

This is the primary use case — an LLM extracts a book title from a document and needs complete bibliographic data:

```python
from scripts.harvard_api import HarvardLibraryAPI
api = HarvardLibraryAPI()

# 1. Search by title (and optionally author)
results = api.search(title="The Great Gatsby", name="Fitzgerald")

# 2. Get the first match's summary
if results:
    summary = api.summarize(results[0])
    # → title (original script + romanized), author, publisher, date, ISBN, subjects, language, physical description

# 3. For deeper data, get MARC via PRESTO
hollis_id = api.get_record_id(results[0])
if hollis_id:
    marc = api.get_presto_record(hollis_id, format="mods")
```

## Key Search Fields

| Field | What it searches | Exact match? |
|-------|-----------------|-------------|
| `q` | All fields (keyword) | No |
| `title` | Title, subtitle, part name/number | Yes (`title_exact`) |
| `name` | All name fields (author, editor, etc.) | No |
| `subject` | All subject fields (topic, geographic, temporal) | Yes (`subject_exact`) |
| `identifier` | ISBN, LCCN, other system IDs | Yes |
| `languageCode` | ISO language code (e.g., `chi`, `eng`) | Yes |
| `dateIssued` | Publication date (YYYY) | Yes |
| `dates.start` / `dates.end` | Date range filter | — |
| `genre` | Genre/form (e.g., "Drawings", "Maps") | Yes (`genre_exact`) |
| `repository` | Harvard library name | Yes |
| `isOnline` | Has digital version (`true`/`false`) | — |
| `recordIdentifier` | HOLLIS/Alma record ID | Yes |

Combine fields freely: `?title=hamlet&name=shakespeare&languageCode=ger&dates.start=1900`

## Pagination

- `limit=N` (default 10, max 250)
- `start=N` for offset-based pagination (up to ~30K results)
- `cursor=*` then `cursor={nextCursor}` for large result sets (up to 100K)

## Facets

Add `facets=field1,field2` to get value counts. Useful fields: `name`, `subject`, `languageCode`, `genre`, `resourceType`, `repository`, `dateIssued`.

```
?title=china&facets=languageCode,genre
```

## Python Script

Use `scripts/harvard_api.py` for programmatic access (zero dependencies):

```python
from scripts.harvard_api import HarvardLibraryAPI
api = HarvardLibraryAPI()

# Keyword search
results = api.search(q="Chinese porcelain Ming dynasty")

# Field search
results = api.search(title="dream of the red chamber", languageCode="chi")

# With facets
results, facets = api.search_with_facets(subject="astronomy", facets=["genre", "dateIssued"])

# Pagination
all_results = api.search_all(title="peanuts", name="schulz", max_results=500)

# PRESTO lookup
marc_xml = api.get_presto_record("011557057", format="marc")

# Summarize a record
for r in results[:5]:
    print(api.summarize(r))
```

## API Endpoints

| Endpoint | URL |
|----------|-----|
| LibraryCloud Items | `https://api.lib.harvard.edu/v2/items` |
| LibraryCloud Collections | `https://api.lib.harvard.edu/v2/collections` |
| PRESTO (MARC/MODS/DC) | `https://webservices.lib.harvard.edu/rest/{format}/hollis/{id}` |

## Related Skills

- **wikidata-search**: Cross-reference Harvard catalog entries with Wikidata for external identifiers (VIAF, LoC, etc.)
- **cbdb-api**: Look up authors of Chinese historical texts in CBDB for biographical context

## Resources

- `references/api_reference.md` — Complete field reference with all searchable fields, facets, and query examples
- `scripts/harvard_api.py` — Full-featured Python client with rate limiting, pagination, and record summarization
- `tests/test_harvard_api.py` — offline tests

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "harvard-library-catalog"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[harvard-library-catalog] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: harvard-library-catalog* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
