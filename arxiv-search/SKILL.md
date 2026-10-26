---
name: arxiv-search
description: Search arXiv for preprints and scholarly articles across physics, mathematics, computer science, quantitative biology, quantitative finance, statistics, electrical engineering, systems science, and economics. Supports field-specific queries (title, author, abstract, category), boolean logic, date filtering, and bulk retrieval with pagination.
version: 1.0.2
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# arXiv Search Skill

Search and retrieve metadata for preprints on arXiv, the open-access repository for scholarly articles.

## Critical: Things Claude Won't Know Without This Skill

### Response format is Atom XML, not JSON

The arXiv API returns **Atom 1.0 XML** — there is no JSON option. You must parse XML to extract results. The Python script handles this automatically.

### The base URL uses `export.arxiv.org`, not `arxiv.org`

```
https://export.arxiv.org/api/query?search_query=all:transformer&max_results=5
```

Using `arxiv.org` directly will not work for API queries.

### Boolean operators must be UPPERCASE

Use `AND`, `OR`, `ANDNOT` — lowercase will not work:

```
search_query=ti:attention AND ti:transformer
search_query=cat:cs.AI ANDNOT cat:cs.CL
```

### Write queries in plain text; do not URL-encode them

Pass the query to the Python script exactly as you would type it, with real quotes, parentheses and spaces. The script URL-encodes it for you:

```python
api.search('ti:"classical Chinese"')                        # phrase search
api.search('au:bengio AND (cat:cs.LG OR cat:cs.AI)')         # grouping
```

Do **not** write `%22`, `%28` or `+` yourself. If you do, the query is encoded twice and arXiv finds nothing (`ti:%22classical+Chinese%22` returned 0 results, `ti:"classical Chinese"` returned 36, checked 2026-10-26). Since version 1.0.2 the script detects hand-encoded input (`%22`, `%28`, `%29`, `%5B`, `%5D`, `%3A`, `%20`) and decodes it once, but plain text is the clear way.

Only when you build a raw URL yourself (for example with `curl`) must you encode: quotes `%22`, parentheses `%28` `%29`, spaces `+`:

```
https://export.arxiv.org/api/query?search_query=ti:%22large+language+model%22
```

### Date range filtering uses a special syntax

```
search_query=submittedDate:[202401010000+TO+202412312359]
```

Format: `YYYYMMDDHHMM` (12 digits) in GMT, 24-hour. Do not put a `T` between date and time; arXiv returns an error if you do. Combine with other queries using `AND`.

### Rate limiting: 3 seconds between requests

arXiv asks for a minimum 3-second delay between API calls. Results update once daily, so there is no reason to poll frequently.

### Hard limits on results

- `max_results` caps at **2000** per request
- Total retrievable results cap at **30,000** (start + max_results ≤ 30000)
- Exceeding 30,000 returns HTTP 400

## Search Field Prefixes

| Prefix | Field |
|--------|-------|
| `ti` | Title |
| `au` | Author |
| `abs` | Abstract |
| `co` | Comment |
| `jr` | Journal Reference |
| `cat` | Subject Category |
| `rn` | Report Number |
| `id_list` | Specific arXiv IDs (comma-separated, passed as separate param) |
| `all` | All fields simultaneously |

## Python Script

Use `scripts/arxiv_api.py` for programmatic access (zero dependencies).

**Working directory:** `from scripts.arxiv_api import ArxivAPI` only works when Python runs from inside the skill folder (the folder that holds this `SKILL.md`). From anywhere else, add the folder to the path first:

```python
import sys
sys.path.insert(0, "/path/to/arxiv-search")   # the folder with SKILL.md
```

```python
from scripts.arxiv_api import ArxivAPI
api = ArxivAPI()

# Simple keyword search
results = api.search("all:transformer attention mechanism", max_results=10)

# Field-specific search
results = api.search("ti:diffusion AND cat:cs.CV", max_results=5)

# Author search
results = api.search("au:hinton AND cat:cs.LG", max_results=20)

# Humanities example: NLP work on premodern Chinese texts
# (18 results on 2026-10-26)
results = api.search('ti:"ancient Chinese" AND cat:cs.CL', max_results=20)
results = api.search('ti:"classical Chinese" AND (cat:cs.CL OR cat:cs.AI)')  # 35 results

# Date-filtered search
results = api.search(
    "cat:cs.AI AND submittedDate:[202401010000 TO 202412312359]",
    sort_by="submittedDate",
    sort_order="descending",
    max_results=50
)

# Fetch specific papers by arXiv ID
results = api.fetch_by_ids(["2301.07041", "2303.08774", "2305.10601"])

# Paginated retrieval
page1 = api.search("cat:cs.CL", max_results=100, start=0)
page2 = api.search("cat:cs.CL", max_results=100, start=100)

# The search returns a dict: total_results, start_index, items_per_page, entries.
# Each item in results["entries"] is a dict with keys:
# id, title, summary, authors, published, updated,
# categories, primary_category, links, comment, journal_ref, doi
```

## Common Category Codes

| Category | Description |
|----------|-------------|
| `cs.AI` | Artificial Intelligence |
| `cs.CL` | Computation and Language (NLP) |
| `cs.CV` | Computer Vision |
| `cs.LG` | Machine Learning |
| `cs.CR` | Cryptography and Security |
| `cs.DS` | Data Structures and Algorithms |
| `cs.SE` | Software Engineering |
| `math.AG` | Algebraic Geometry |
| `math.CO` | Combinatorics |
| `physics.hep-th` | High Energy Physics - Theory |
| `quant-ph` | Quantum Physics |
| `stat.ML` | Machine Learning (Statistics) |
| `econ.GN` | General Economics |
| `q-bio.GN` | Genomics |

Full list: https://arxiv.org/category_taxonomy

## API Etiquette

- **Rate limit**: 3-second minimum between requests
- **No authentication required**
- **Results update daily** — no need to poll the same query more than once per day
- **Use pagination** for large result sets instead of requesting thousands at once
- **Respect HTTP 429**: Back off if rate-limited

## Related Skills

- **wikidata-search**: Cross-reference arXiv authors with Wikidata entities for authority control identifiers (ORCID, VIAF, etc.)
- **harvard-library-catalog**: Look up published versions of arXiv preprints in Harvard's bibliographic records

## Resources

- `references/api_reference.md` — Complete API specs for query parameters, response fields, and error handling
- `scripts/arxiv_api.py` — Python client with XML parsing, rate limiting, and pagination support

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "arxiv-search"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[arxiv-search] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: arxiv-search* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
